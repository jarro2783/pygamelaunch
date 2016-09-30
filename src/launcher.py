#!/usr/bin/python3

"""The pygamelaunch launcher.

This is the main pygamelaunch launcher program. It starts the ncurses game
launcher and allows the user to login and play any games defined in
gamelaunch.yml.
"""

import bcrypt
import curses
import curses.ascii
from gamelaunch import db
import gamelaunch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import os
import signal
import sys
from jinja2 import Template
import time
import tty
import yaml

VERSION = 0.1

def render_template(text, **kwargs):
    """Renders a template with the given arguments."""
    tem = Template(text)
    return tem.render(kwargs)

class InvalidUser(Exception):
    """Thrown as an exception to indicate an invalid user."""
    pass

class GameLauncher:
    """The main game launcher class."""

    LoginLine = 3
    WinStart = 4

    def __init__(self, scr, config):
        menus = config['menus']

        if 'actions' in config:
            self.__actions = config['actions']
        else:
            self.__actions = {}

        self.__scr = scr
        self.__menustack = []
        self.__exiting = False
        self.__user = ""
        self.__menus = menus
        self.__template_args = {}

        self.__database = db.Database()
        self.__session = None

        self.__init_games(config['games'])

        self.__init_curses()

        self.push_menu("main")

    def user(self):
        """Get the logged in user."""
        return self.__user

    def redraw(self):
        """Redraw the window."""
        self.__window.clear()
        self.__menustack[-1].draw(self)
        self.__window.refresh()

    def __init_curses(self):
        """Initialise the screen."""
        scr = self.__scr
        height, width = scr.getmaxyx()
        rowy = self.WinStart

        self.__window = curses.newwin(height - rowy - 1, width, rowy, 0)
        scr.addstr(1, 1, "Pygamelaunch")

        if self.__user != "":
            self.__logged_in("Logged in as {}".format(self.__user))
        else:
            self.__logged_in("Not logged in")
        scr.refresh()


    def __init_games(self, games):
        """Initialise the game numbers."""
        self.__games = games

        i = 0
        for game in self.__games:
            game['number'] = i
            i += 1

    def push_menu(self, menu):
        """Push a menu onto the menu stack, creating a menu from a string
        if necessary."""
        if isinstance(menu, str):
            menu = Menu(self.__menus[menu], self)
        self.__push_menu(menu)

    def __push_menu(self, menu):
        """The real menu push that redraws the window."""
        self.__menustack.append(menu)
        self.__window.clear()
        menu.draw(self)
        self.__window.refresh()

    def __pop_menu(self):
        """Do the actual menu pop."""
        self.__menustack.pop()

    def pop_menu(self, redraw=True):
        """Remove a menu from the stack."""
        self.__pop_menu()

        if len(self.__menustack) > 0 and redraw:
            self.__window.clear()
            self.__top().draw(self)
            self.__window.refresh()

    def game_menu(self, which):
        """Go to a game menu identified by which."""
        menu = self.__games[which]
        self.__push_menu(Menu(menu['menu'], self, game=menu))

    def run(self):
        """Run the game launcher."""
        while not self.__exiting and len(self.__menustack) > 0:
            key = self.__scr.getch()
            self.__top().key(key, self)

    def quit(self):
        """Quit from a menu."""
        #self.__exiting = True
        if len(self.__menustack) > 0:
            self.pop_menu()

    def __top(self):
        """Get the top menu."""
        return self.__menustack[-1]

    def screen(self):
        """Get the screen."""
        return self.__window

    def login(self, user, password):
        """Try to login."""
        sess = self.__database.begin()
        user_record = sess.query(db.User).filter(
            db.User.username == user).first()

        if user_record is not None:
            existing = user_record.password.encode('utf-8')
            hashed = bcrypt.hashpw(password.encode('utf-8'), existing)

            if hashed == existing:
                self.__pop_menu()
                self.__do_login(user)
                return
        else:
            # Hash something anyway to not give away the non-existence
            # of a user
            bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # we get here if not logged in
        self.redraw()

    def __do_login(self, user):
        """Log a user in."""
        self.__user = user
        self.__template_args['user'] = user
        self.__logged_in("Logged in as: {}".format(user))
        self.push_menu("loggedin")

    def message_line(self, message, row):
        """Print a message on a row."""
        scr = self.__scr
        _, width = scr.getmaxyx()
        scr.hline(row, 0, ' ', width)
        scr.addstr(row, 1, message)

    def status(self, message):
        """Print to the status line."""
        height, _ = self.__scr.getmaxyx()
        self.message_line(message, height-1)

    def __logged_in(self, message):
        """Print the logged in message."""
        self.message_line(message, self.LoginLine)

    def generate_menus(self, name):
        """Build items for a menus from a specific type of item."""
        if name == "games":
            games = ["blank"]
            for game in self.__games:
                i = game['number']
                games.append({
                    "key" : chr(ord('0') + i + 1),
                    "title" : game['name'],
                    "action" : "game {}".format(i)
                })

            games.append("blank")
            return games
        elif name == "blank":
            return "blank"

    def render_template(self, to_render, **kwargs):
        """Render a template using the current variables."""
        if isinstance(to_render, list):
            result = []
            for template in to_render:
                result.append(self.render_template(template, **kwargs))
            return result
        else:
            newargs = self.__template_args
            newargs.update(kwargs)
            return render_template(to_render, **newargs)

    def register(self, values):
        """Register a new user."""
        user = values['user']
        user_record = db.create_user(
            user,
            values['password'],
            values['email'])

        try:
            db.add_user(self.__database, user_record)

            self.status("Created new user")
            self.__pop_menu()
            self.__do_login(user)
            if 'register' in self.__actions:
                action = self.render_template(self.__actions['register'])
                pipe = os.popen("bash -c '" + action + "'", "r")
                pipe.read()
                pipe.close()
        except IntegrityError:
            self.status("Username already in use")
            self.__pop_menu()
            self.push_menu('main')

    def __execute(self, binary, args, message=None, custom=None):
        """Execute a program."""
        curses.endwin()

        if custom is not None:
            custom(binary, args)
        else:
            pid = os.fork()
            if pid == 0:
                if message is not None:
                    print(message)
                try:
                    os.execvp(binary, args)
                except OSError as error:
                    print("Error executing {}:{}".format(binary, error))
                sys.exit(1)
            else:
                os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.__init_curses()

    def __docker(self, docker, image, args):
        """Run something in docker."""

        docker = [
            "run",
            "--rm",
            "-it"
        ] + docker

        docker.append(image)
        docker.extend(args)

        binary = "/usr/bin/docker"

        curses.endwin()
        gamelaunch.rungame(
            binary,
            docker,
            "localhost",
            "34234",
            self.__user)
        self.__scr = curses.initscr()
        self.__init_curses()

        #self.__execute(binary, [binary] + run_args, message)

    def play(self, which):
        """Launch a game."""
        game = self.__games[which]

        docker = []
        args = []

        if 'volumes' in game:
            for volumes in game['volumes']:
                docker.append("-v")
                volume = "{}:{}".format(
                    self.render_template(volumes[0]),
                    self.render_template(volumes[1])
                )
                docker.append(volume)

        if 'arguments' in game:
            game_args = game['arguments']
            if isinstance(game_args, list):
                args.extend(self.render_template(game_args))
            else:
                args.append(self.render_template(game_args))

        self.__start_playing()
        self.__docker(docker, game['image'], args)
        self.__stop_playing()

    def __start_playing(self):
        """The current user has started playing."""
        session = self.__database.begin()
        user = session.\
            query(db.User).filter(db.User.username == self.__user).one()
        playing = db.Playing(id=user.id, since=time.time())
        session.add(playing)
        session.commit()

    def __stop_playing(self):
        """The current user has stopped playing."""
        session = self.__database.begin()
        user = session.query(db.User).\
            filter(db.User.username == self.__user).one()

        playing = session.query(db.Playing).filter(db.Playing.id == user.id).one()
        session.delete(playing)
        session.commit()

    def playing(self):
        """Get the playing users."""
        session = self.__database.begin()
        playing = session.query(db.Playing, db.User).join(db.User).all()
        session.commit()
        return playing

    def edit_options(self, path):
        """Edit the options for a game."""
        args = [
            "docker",
            "run",
            "--rm",
            "-it",
            "-v",
            path + ":/.nethackrc",
            "jarro2783/vim",
            "/.nethackrc"
        ]

        curses.endwin()
        pid = os.fork()
        if pid == 0:
            print("Loading editor...")
            print("Mounting: " + path + " as /.nethackrc")

            os.execv("/usr/bin/docker", args)
        else:
            os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.__init_curses()

    def __get_user(self, username):
        """Get the userid for the username."""
        session = self.__begin_session()
        users = session.query(db.User).\
            filter(db.User.username == username).all()

        if len(users) != 0:
            return users[0]
        else:
            raise InvalidUser()

    def __begin_session(self):
        """Begin a database session."""
        self.__session = self.__database.begin()
        return self.__session

    def __commit_session(self):
        """Commit the database session."""
        self.__session.commit()
        self.__session = None

    def change_password(self, password):
        """Change the user's password."""
        user = self.__get_user(self.__user)
        db.update_password(user, password)
        self.status("Password changed")
        self.__commit_session()

    def change_email(self, email):
        """Change the user's email."""
        user = self.__get_user(self.__user)
        user.email = email
        self.status("Email changed")
        self.__commit_session()

    @staticmethod
    def __child(_, frame):
        """Debugging sigchld."""
        print(frame)
        os.waitpid(frame.f_locals['pid'], 0)

    def __playexec(self, binary, args):
        """Execute the game watcher."""
        pid = os.fork()
        signal.signal(signal.SIGCHLD, self.__child)
        if pid == 0:
            sys.stdin.close()
            os.execvp(binary, args)
        else:
            tty.setraw(sys.stdin.fileno())
            while True:
                char = sys.stdin.read(1)
                if char == 'q':
                    break
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            os.kill(pid, signal.SIGTERM)
            #os.waitpid(pid, 0)

    @staticmethod
    def __termplay(user):
        """Watch a game."""
        gamelaunch.watch('localhost', '34234', user)

    def watch(self, userid):
        """Watch the game being played by userid."""
        session = self.__database.begin()
        query = session.query(db.User).filter(db.User.id == userid)

        try:
            playing = query.one()
            # we need to watch the file recorded in playing
            self.__termplay(playing.username)
        except NoResultFound:
            # that player is not actually playing
            # maybe they quit since the menu was shown
            pass

class WatchMenu:
    """The menu to watch other games."""
    offset = 2
    def __init__(self):
        self.__playing = []

    def draw_row(self, app, player, row):
        """Draw a single row in the watch menu."""
        user = player[1]
        screen = app.screen()
        screen.addstr(
            1, self.offset + row,
            "{})  {}".format(chr(row + ord('a')), user.username))

    def update_playing(self, app):
        """Update the playing users."""
        playing = app.playing()
        self.__playing = playing

        row = 0
        for player in playing:
            self.draw_row(app, player, row)

    def draw(self, app):
        """Draw the watch menu."""
        self.update_playing(app)

    def key(self, key, app):
        """Handle a key press."""
        if key == ord('q'):
            app.pop_menu()
        elif key >= ord('a') and key <= ord('z'):
            which = key - ord('a')
            if which < len(self.__playing):
                app.watch(self.__playing[which][0].id)

class KeyInput:
    """Base class for handling key input."""
    def __init__(self, echo, key, message, nextmenu):
        self.__text = ""
        self.__echo = echo
        self.__next = nextmenu
        self.__values = {}
        self.__key = key
        self.__message = message + " Empty input cancels."

    def key(self, key, app):
        """Handle a key press."""
        scr = app.screen()
        chcode = chr(key)
        if key == ord('\n'):
            if self.__text == "":
                app.pop_menu()
            else:
                self.__do_next(app)
        elif key == curses.KEY_BACKSPACE or key == 127:
            if len(self.__text) > 0:
                self.__text = self.__text[0: -1]

                if self.__echo:
                    ypos, xpos = scr.getyx()
                    scr.move(ypos, xpos-1)
                    scr.delch()
                    scr.refresh()

        elif curses.ascii.isgraph(chcode):
            self.__text += chcode

            if self.__echo:
                scr.addstr(chcode)
                scr.refresh()

    def __do_next(self, app):
        """Do the next menu after taking input."""
        app.pop_menu(False)
        values = self.__values.copy()
        values[self.__key] = self.__text
        self.__next.start(app, values)

    def start(self, app, values):
        """Set up the menu."""
        self.__values = values
        app.push_menu(self)

    def draw(self, app):
        """Draw the actual key input menu."""
        app.screen().addstr(1, 1, self.__message)
        app.screen().move(3, 1)


class UserNameMenu(KeyInput):
    """A menu that takes a username as input."""
    def __init__(self, nextmenu):
        super().__init__(True, "user", "Enter your username.", nextmenu)

class PasswordMenu(KeyInput):
    """A menu that takes a password as input."""
    def __init__(self, nextmenu):
        super().__init__(False, "password", "Enter your password.", nextmenu)

class DoLoginMenu:
    """A fake menu that does the actual login."""
    @staticmethod
    def start(app, values):
        """Do the actual login."""
        app.login(values['user'], values['password'])

class DoRegisterMenu:
    """A fake menu that does the user registration."""
    @staticmethod
    def start(app, values):
        """Do the user register."""
        app.register(values)

class EmailMenu(KeyInput):
    """A menu that takes an email address."""
    def __init__(self, nextmenu):
        super().__init__(True, "email", "Enter your email address.", nextmenu)

class ChangePasswordMenu:
    """Fake menu to do the actual change password."""
    @staticmethod
    def start(app, values):
        """Run the change password."""
        app.change_password(values['password'])
        app.redraw()

class ChangeEmailMenu:
    """Fake menu to do the actual change email."""
    @staticmethod
    def start(app, values):
        """Run the change email."""
        app.change_email(values['email'])
        app.redraw()

class ChoiceRunner:
    """The choice runner runs actions that are specified in the config."""
    def __init__(self, app, **kwargs):
        self.__app = app
        self.__args = kwargs

    def run(self, command):
        """Run an action."""
        parts = self.__app.render_template(command, **self.__args).split(' ')
        self.__commands[parts[0]](self, parts[1:])

    def login(self, _):
        """Login."""
        menu = UserNameMenu(PasswordMenu(DoLoginMenu()))
        self.__app.push_menu(menu)

    def game(self, args):
        """Go to a game menu."""
        self.__app.game_menu(int(args[0]))

    def quit(self, _):
        """Quit the current menu."""
        self.__app.quit()

    def play(self, args):
        """Play a game."""
        self.__app.play(int(args[0]))

    def register(self, _):
        """Register a user."""
        menu = UserNameMenu(PasswordMenu(EmailMenu(DoRegisterMenu())))
        self.__app.push_menu(menu)

    def edit(self, args):
        """Run the edit command."""
        self.__app.edit_options(self.__render(args[0]))

    def __render(self, text):
        """Render the menu."""
        return self.__app.render_template(text, **self.__args)

    def changepass(self, _):
        """Go to the change password menu."""
        if self.__app.user() == "":
            pass
            # TODO fix this once change pass is implemented
            #self.status("You are not logged in")
        else:
            self.__app.push_menu(PasswordMenu(ChangePasswordMenu()))

    def changeemail(self, _):
        """Go to the change email menu."""
        if self.__app.user() == "":
            pass
            # TODO fix this once change email is implemented
            #self.status("You are not logged in")
        else:
            self.__app.push_menu(EmailMenu(ChangeEmailMenu()))

    def watch(self, _):
        """Change to the watch menu."""
        self.__app.push_menu(WatchMenu())

    __commands = {
        "login" : login,
        "game" : game,
        "play" : play,
        "quit" : quit,
        "register" : register,
        "edit" : edit,
        "changepass" : changepass,
        "changeemail" : changeemail,
        "watch" : watch
    }

class Menu:
    """The main game menu class."""
    def __init__(self, items, app, **kwargs):
        self.__runner = ChoiceRunner(app, **kwargs)
        self.__lines = []
        self.__keys = {}
        self.__args = kwargs
        # menus can either be an array describing the menu,
        # or a string that the engine expands to some menu items
        for line in items:
            if line is not "blank" and isinstance(line, str):
                menus = app.generate_menus(line)
                for i in menus:
                    self.__add_item(i, app)
            else:
                self.__add_item(line, app)

    def __add_item(self, line, app):
        """Add a menu item to the menu."""
        if line == "blank":
            self.__lines.append("")
        else:
            text = app.render_template(line['title'], **self.__args)
            self.__keys[ord(line['key'])] = line
            self.__lines.append("{}) {}".format(line['key'], text))

    def draw(self, app):
        """Draw all the lines in a menu."""
        i = 1
        scr = app.screen()
        for line in self.__lines:
            scr.addstr(i, 1, line)
            i += 1

    def key(self, pressed, _):
        """Called on a key press."""
        if pressed in self.__keys:
            keydata = self.__keys[pressed]
            self.__runner.run(keydata['action'])

    def action(self, key):
        """Return the action for the specified key."""
        return self.__keys[key]['action']


def run(scr):
    """The main game runner. Intended to be run inside a curses wrapper."""
    file = open("gamelaunch.yml")
    config = yaml.load(file)

    game = GameLauncher(scr, config)

    game.run()

def main():
    """The main function which calls the curses wrapper."""
    curses.wrapper(run)

if __name__ == "__main__":
    main()
