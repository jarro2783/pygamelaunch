#!/usr/bin/python3

import curses
import db
import hashlib
from jinja2 import Template
import os
import sys
import time
import yaml

version = 0.1

def render_template(t, **kwargs):
    tem = Template(t)
    return tem.render(kwargs)

class GameLauncher:
    def __init__(self, scr, config):
        menus = config['menus']
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

    def init_curses(self):
        scr = self.__scr
        y,x = scr.getmaxyx()
        ry = 4

        self.__window = curses.newwin(y - ry, x, ry, 0)
        scr.addstr(1, 1, "Pygamelaunch v{}".format(version))
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

    def pop_menu(self):
        self.__menustack.pop()

        if len(self.__menustack) > 0:
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
            sha = hashlib.sha256(u.salt)
            sha.update(pw.encode('utf-8'))

            if sha.digest() == u.password:
                self.pop_menu()
                self.__user = user
                self.__template_args['user'] = user
                self.__scr.addstr(3, 1, "Logged in as: {}".format(user))
                self.push_menu("loggedin")

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
        u = db.create_user(values['user'],
            values['password'],
            values['email']
        )
        db.add_user(self.__database, u)

    def __docker(self, message, args):
        curses.endwin()
        pid = os.fork()

        docker = [
            "docker",
            "run",
            "--rm",
            "-it"
        ]

        if pid == 0:
            print(message)
            os.execv("/usr/bin/docker", docker + args)
        else:
            os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.init_curses()

    def play(self, n):
        g = self.__games[n]

        args = []

        if 'volumes' in g:
            for v in g['volumes']:
                args.append("-v")
                volume = "{}:{}".format(
                  self.render_template(v[0]),
                  self.render_template(v[1])
                )
                args.append(volume)

        args.append(g['image'])
        if 'arguments' in g:
            a = g['arguments']
            if isinstance(a, list):
                args.extend(self.render_template(a))
            else:
                args.append(self.render_template(a))

        self.__docker("Loading...", args)

    def edit_options(self, path):
        args = ["docker",
            "run",
            "--rm",
            "-it",
            "-v",
            path + ":/file",
            "jarro2783/vim",
            "/file"
        ]

        curses.endwin()
        pid = os.fork()
        if pid == 0:
            print("Loading editor...")
            print("Mounting: " + path + " as /file")
            os.execv("/usr/bin/docker", args)
        else:
            os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.init_curses()
        
class KeyInput:
    def __init__(self, echo, key, message, nextmenu):
        self.__text = ""
        self.__echo = echo
        self.__next = nextmenu
        self.__values = {}
        self.__key = key
        self.__message = message

    def key(self, c, app):
        if c == ord('\n'):
            self.__do_next(app)
        else:
            ch = chr(c)
            self.__text += ch

            if self.__echo:
                scr = app.screen()
                scr.addstr(ch)
                scr.refresh()

    def __do_next(self, app):
        app.pop_menu()
        values = self.__values.copy()
        values[self.__key] = self.__text
        self.__next.start(app, values)

    def start(self, app, values):
        self.__values = values
        app.push_menu(self)

    def draw(self, app):
        app.screen().addstr(1,1, self.__message + ": ")


class UserNameMenu(KeyInput):
    def __init__(self, n):
        super().__init__(True, "user", "Enter your username", n)

class PasswordMenu(KeyInput):
    def __init__(self, n):
        super().__init__(False, "password", "Enter your password", n)

class DoLoginMenu:
    def start(self, app, values):
        app.login(values['user'], values['password'])

class DoRegisterMenu:
    def start(self, app, values):
        app.register(values)

class EmailMenu(KeyInput):
    def __init__(self, n):
        super().__init__(True, "email", "Enter your email address", n)

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

    __commands = {
        "login" : login,
        "game" : game,
        "play" : play,
        "quit" : quit,
        "register" : register,
        "edit" : edit
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
