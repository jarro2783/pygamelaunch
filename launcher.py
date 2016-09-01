#!/usr/bin/python3

import bcrypt
import curses
import curses.ascii
from gamelaunch import db
import hashlib
from jinja2 import Template
import os
import signal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import sys
import time
import tty
import yaml

import pprint

version = 0.1

def render_template(t, **kwargs):
    tem = Template(t)
    return tem.render(kwargs)

class InvalidUser:
    pass

class TTYRecord:
    def __init__(self, directory):
        self.__directory = directory

        now = time.localtime()

        self.__record = "{}-{:02}-{:02}-{:02}-{:02}-{:02}.ttyrec".\
            format(now.tm_year,
          now.tm_mon,
          now.tm_mday,
          now.tm_hour,
          now.tm_min,
          now.tm_sec)

    def binary(self):
        return "termrec"

    def args(self, a):
        return ["-e", ' '.join(a), self.__directory + "/" + self.__record]

    def file(self):
        return self.__directory + "/" + self.__record

class GameLauncher:

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

        self.__init_games(config['games'])

        self.init_curses()

        self.push_menu("main")

    def user(self):
        return self.__user

    def redraw(self):
        self.__window.clear()
        self.__menustack[-1].draw(self)
        self.__window.refresh()

    def init_curses(self):
        scr = self.__scr
        y,x = scr.getmaxyx()
        ry = self.WinStart

        self.__window = curses.newwin(y - ry - 1, x, ry, 0)
        scr.addstr(1, 1, "Pygamelaunch")

        if self.__user != "":
            self.logged_in("Logged in as {}".format(self.__user))
        else:
            self.logged_in("Not logged in")
        scr.refresh()


    def __init_games(self, games):
        self.__games = games

        i = 0
        for f in self.__games:
            f['number'] = i
            i += 1

    def push_menu(self, menu):
        if isinstance(menu, str):
            menu = Menu(self.__menus[menu], self)
        self.__push_menu(menu)

    def __push_menu(self, menu):
        self.__menustack.append(menu)
        self.__window.clear()
        menu.draw(self)
        self.__window.refresh()

    def __pop_menu(self):
        self.__menustack.pop()

    def pop_menu(self, redraw=True):
        self.__pop_menu()

        if len(self.__menustack) > 0 and redraw:
            self.__window.clear()
            self.__top().draw(self)
            self.__window.refresh()

    def game_menu(self, n):
        g = self.__games[n]
        self.__push_menu(Menu(g['menu'], self, game=g))

    def run(self):
        while not self.__exiting and len(self.__menustack) > 0:
            c = self.__scr.getch()
            self.__top().key(c, self)

    def quit(self):
        #self.__exiting = True
        if len(self.__menustack) > 0:
            self.pop_menu()

    def __top(self):
        return self.__menustack[-1]

    def screen(self):
        return self.__window

    def login(self, user, pw):
        sess = self.__database.begin()
        u = sess.query(db.User).filter(db.User.username == user).first()

        if u is not None:
            existing = u.password.encode('utf-8')
            hashed = bcrypt.hashpw(pw.encode('utf-8'), existing)

            if hashed == existing:
                self.__pop_menu()
                self.__do_login(user)
                return

        # we get here if not logged in
        self.redraw()

    def __do_login(self, user):
        self.__user = user
        self.__template_args['user'] = user
        self.logged_in("Logged in as: {}".format(user))
        self.push_menu("loggedin")

    def message_line(self, message, row):
        scr = self.__scr
        _, x = scr.getmaxyx()
        scr.hline(row, 0, ' ', x)
        scr.addstr(row, 1, message)

    def status(self, message):
        y, _ = self.__scr.getmaxyx()
        self.message_line(message, y-1)

    def logged_in(self, message):
        self.message_line(message, self.LoginLine)

    def generate_menus(self, name):
        if name == "games":
            games = ["blank"]
            for f in self.__games:
                i = f['number']
                games.append({
                    "key" : chr(ord('0') + i + 1),
                    "title" : f['name'],
                    "action" : "game {}".format(i)
                })

            games.append("blank")
            return games
        elif name == "blank":
            return "blank"

    def render_template(self, s, **kwargs):
        if isinstance(s, list):
            result = []
            for t in s:
                result.append(self.render_template(t, **kwargs))
            return result
        else:
            newargs = self.__template_args
            newargs.update(kwargs)
            return render_template(s, **newargs)

    def register(self, values):
        user = values['user']
        u = db.create_user(user,
            values['password'],
            values['email']
        )

        try:
            db.add_user(self.__database, u)

            self.status("Created new user")
            self.__pop_menu()
            self.__do_login(user)
            if 'register' in self.__actions:
                action = self.render_template(self.__actions['register'])
                p = os.popen("bash -c '" + action + "'", "r")
                p.read()
                p.close()
        except IntegrityError:
            self.status("Username already in use")
            self.__pop_menu()
            self.push_menu('main')

    def __execute(self, binary, args, message = None, custom = None):
        curses.endwin()

        if custom is not None:
            custom(binary, args)
        else:
            pid = os.fork()
            if pid == 0:
                if message is not None:
                    print(message)
                os.execvp(binary, args)
                os.exit(1)
            else:
                p, status = os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.init_curses()

    def __docker(self, message, docker, image, args, record=None):

        docker = [
            "docker",
            "run",
            "--rm",
            "-it"
        ] + docker

        docker.append(image)
        docker.extend(args)

        if record is not None:
            binary = record.binary()
            run_args = record.args(docker)
        else:
            binary = "/usr/bin/docker"
            run_args = docker

        self.__execute(binary, [binary] + run_args, message)

    def play(self, n):
        g = self.__games[n]

        docker = []
        args = []

        if 'volumes' in g:
            for v in g['volumes']:
                docker.append("-v")
                volume = "{}:{}".format(
                  self.render_template(v[0]),
                  self.render_template(v[1])
                )
                docker.append(volume)

        if 'arguments' in g:
            a = g['arguments']
            if isinstance(a, list):
                args.extend(self.render_template(a))
            else:
                args.append(self.render_template(a))

        tty = TTYRecord(self.render_template(g['recordings']))
        self.__start_playing(tty.file())
        self.__docker("Loading...", docker, g['image'], args,
            tty)
        self.__stop_playing()

    def __start_playing(self, tty):
        session = self.__database.begin()
        user = session.\
            query(db.User).filter(db.User.username == self.__user).one()
        playing = db.Playing(id = user.id, record = tty, since = time.time())
        session.add(playing)
        session.commit()

    def __stop_playing(self):
        session = self.__database.begin()
        user = session.query(db.User).\
            filter(db.User.username == self.__user).one()

        playing = session.query(db.Playing).filter(db.Playing.id == user.id).one()
        session.delete(playing)
        session.commit()

    def playing(self):
        s = self.__database.begin()
        playing = s.query(db.Playing, db.User).join(db.User).all()
        s.commit()
        return playing

    def edit_options(self, path):
        args = ["docker",
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
        self.init_curses()

    def __get_user(self, username):
        session = self.__begin_session()
        users = session.query(db.User).\
            filter(db.User.username == self.__user).all()

        if len(users) != 0:
            return users[0]
        else:
            raise InvalidUser()

    def __begin_session(self):
        self.__session = self.__database.begin()
        return self.__session

    def __get_session(self):
        return self.__session

    def __commit_session(self):
        self.__session.commit()
        self.__session = None

    def change_password(self, password):
        user = self.__get_user(self.__user)
        db.update_password(user, password)
        self.status("Password changed")
        self.__commit_session()

    def change_email(self, email):
        user = self.__get_user(self.__user)
        user.email = email
        self.status("Email changed")
        self.__commit_session()

    def __child(self, num, frame):
        print(frame)
        os.waitpid(frame.f_locals['pid'], 0)

    def __playexec(self, binary, args):
        pid = os.fork()
        signal.signal(signal.SIGCHLD, self.__child)
        if pid == 0:
            sys.stdin.close()
            os.execvp(binary, args)
        else:
            tty.setraw(sys.stdin.fileno())
            while True:
                c = sys.stdin.read(1)
                if c == 'q':
                    break
                else:
                    print(c)
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            os.kill(pid, signal.SIGTERM)
            #os.waitpid(pid, 0)

    def __termplay(self, record):
        self.__execute("ttyplay", ["ttyplay", "-p", "-n", record],
            custom = self.__playexec)

    def watch(self, id):
        session = self.__database.begin()
        q = session.query(db.Playing).join(db.User).filter(db.User.id == id)

        try:
            playing = q.one()
            # we need to watch the file recorded in playing
            self.__termplay(playing.record)
        except NoResultFound:
            # that player is not actually playing
            # maybe they quit since the menu was shown
            pass

class WatchMenu:
    offset = 2
    def draw_row(self, app, player, row):
        playing = player[0]
        user = player[1];
        screen = app.screen()
        screen.addstr(1, self.offset + row,
          "{})  {}".format(chr(row + ord('a')), user.username))

    def update_playing(self, app):
        playing = app.playing()
        self.__playing = playing

        row = 0
        for player in playing:
            self.draw_row(app, player, row)

    def draw(self, app):
        self.update_playing(app)

    def key(self, c, app):
        if c == ord('q'):
            app.pop_menu()
        elif c >= ord('a') and c <= ord('z'):
            which = c - ord('a')
            if which < len(self.__playing):
                app.watch(self.__playing[which][0].id)

class KeyInput:
    def __init__(self, echo, key, message, nextmenu):
        self.__text = ""
        self.__echo = echo
        self.__next = nextmenu
        self.__values = {}
        self.__key = key
        self.__message = message + " Empty input cancels."

    def key(self, c, app):
        scr = app.screen()
        ch = chr(c)
        if c == ord('\n'):
            if self.__text == "":
                app.pop_menu()
            else:
                self.__do_next(app)
        elif c == curses.KEY_BACKSPACE or c == 127:
            if len(self.__text) > 0:
                self.__text = self.__text[0: -1]

                if self.__echo:
                    y, x = scr.getyx()
                    scr.move(y, x-1)
                    scr.delch()
                    scr.refresh()

        elif curses.ascii.isgraph(ch):
            self.__text += ch

            if self.__echo:
                scr.addstr(ch)
                scr.refresh()

    def __do_next(self, app):
        app.pop_menu(False)
        values = self.__values.copy()
        values[self.__key] = self.__text
        self.__next.start(app, values)

    def start(self, app, values):
        self.__values = values
        app.push_menu(self)

    def draw(self, app):
        app.screen().addstr(1,1, self.__message)
        app.screen().move(3, 1)


class UserNameMenu(KeyInput):
    def __init__(self, n):
        super().__init__(True, "user", "Enter your username.", n)

class PasswordMenu(KeyInput):
    def __init__(self, n):
        super().__init__(False, "password", "Enter your password.", n)

class DoLoginMenu:
    def start(self, app, values):
        app.login(values['user'], values['password'])

class DoRegisterMenu:
    def start(self, app, values):
        app.register(values)

class EmailMenu(KeyInput):
    def __init__(self, n):
        super().__init__(True, "email", "Enter your email address.", n)

class ChangePasswordMenu:
    def start(self, app, values):
        app.change_password(values['password'])
        app.redraw()

class ChangeEmailMenu:
    def start(self, app, values):
        app.change_email(values['email'])
        app.redraw()

class ChoiceRunner:
    def __init__(self, app, **kwargs):
        self.__app = app
        self.__args = kwargs

    def run(self, command):
        parts = self.__app.render_template(command, **self.__args).split(' ')
        self.__commands[parts[0]](self, parts[1:])

    def login(self, args):
        menu = UserNameMenu(PasswordMenu(DoLoginMenu()))
        self.__app.push_menu(menu)

    def game(self, args):
        self.__app.game_menu(int(args[0]))

    def quit(self, args):
        self.__app.quit()

    def play(self, args):
        self.__app.play(int(args[0]))

    def register(self, args):
        menu = UserNameMenu(PasswordMenu(EmailMenu(DoRegisterMenu())))
        self.__app.push_menu(menu)

    def edit(self, args):
        self.__app.edit_options(self.__render(args[0]))

    def __render(self, s):
        return self.__app.render_template(s, **self.__args)

    def changepass(self, args):
        if self.__app.user() == "":
            self.status("You are not logged in")
        else:
            self.__app.push_menu(PasswordMenu(ChangePasswordMenu()))

    def changeemail(self, args):
        if self.__app.user() == "":
            self.status("You are not logged in")
        else:
            self.__app.push_menu(EmailMenu(ChangeEmailMenu()))

    def watch(self, args):
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
    def __init__(self, y, app, **kwargs):
        self.__runner = ChoiceRunner(app, **kwargs)
        self.__lines = []
        self.__keys = {}
        self.__args = kwargs
        # menus can either be an array describing the menu,
        # or a string that the engine expands to some menu items
        for f in y:
            if f is not "blank" and isinstance(f, str):
                menus = app.generate_menus(f)
                for i in menus:
                    self.__add_item(i, app)
            else:
                self.__add_item(f, app)

    def __add_item(self, f, app):
        if f == "blank":
            self.__lines.append("")
        else:
            text = app.render_template(f['title'], **self.__args)
            self.__keys[ord(f['key'])] = f
            self.__lines.append("{}) {}".format(f['key'], text))

    def draw(self, app):
        i = 1
        scr = app.screen()
        for f in self.__lines:
            scr.addstr(i, 1, f)
            i += 1

    def key(self, c, app):
        if c in self.__keys:
            a = self.__keys[c]
            self.__runner.run(a['action'])

    def action(self, key):
        return self.__keys[key]['action']


def run(scr):

    f = open("gamelaunch.yml")
    m = yaml.load(f)

    game = GameLauncher(scr, m)

    game.run()

def main():
    curses.wrapper(run)

if __name__ == "__main__":
    main()
