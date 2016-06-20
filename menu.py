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

def render_template(t, args):
    tem = Template(t)
    return tem.render(args)

class GameLauncher:
    def __init__(self, scr, config):
        menus = config['menus']
        self.__scr = scr
        self.__menustack = []
        self.__exiting = False
        self.__user = ""
        self.__menus = menus

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
        menu.draw()
        self.__window.refresh()

    def pop_menu(self):
        self.__menustack.pop()
        self.__window.clear()
        self.__top().draw()
        self.__window.refresh()

    def game_menu(self, n):
        g = self.__games[n]
        self.__push_menu(Menu(g['menu'], self, game=g))

    def run(self):
        while not self.__exiting:
            c = self.__scr.getch()
            self.__top().key(c)

    def quit(self):
        self.__exiting = True

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
                self.__user = user
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

    def replace_params(self, s):
        if isinstance(s, list):
            result = []
            for t in s:
                result.append(self.replace_params(t))
            return result
        else:
            return render_template(s, {'user': self.__user})

    def play(self, n):
        g = self.__games[n]

        args = ["docker", "run", "--rm", "-it"]

        if 'volumes' in g:
            for v in g['volumes']:
                args.append("-v")
                volume = "{}:{}".format(
                  self.replace_params(v[0]),
                  self.replace_params(v[1])
                )
                args.append(volume)

        args.append(g['image'])
        if 'arguments' in g:
            a = g['arguments']
            if isinstance(a, list):
                args.extend(self.replace_params(a))
            else:
                args.append(self.replace_params(a))

        curses.endwin()
        pid = os.fork()

        if pid == 0:
            os.execv("/usr/bin/docker", args)
        else:
            os.waitpid(pid, 0)

        self.__scr = curses.initscr()
        self.init_curses()

        
class KeyInput:
    def __init__(self, echo):
        self.__text = ""
        self.__echo = echo

    def key(self, c):
        if c == ord('\n'):
            self.finished(self.__text)
        else:
            ch = chr(c)
            self.__text += ch

            if self.echo:
                scr = self.app.screen()
                scr.addstr(ch)
                scr.refresh()

class UserNameMenu(KeyInput):
    def __init__(self, app):
        super().__init__(True)
        self.app = app
        self.__user = ""
        self.text = ""
        self.echo = True

    def finished(self, text):
        self.app.pop_menu()
        self.app.push_menu(PasswordMenu(self.app, text))

    def draw(self):
        self.app.screen().addstr(1, 1, "Enter your username: ")

class PasswordMenu(KeyInput):
    def __init__(self, app, user):
        super().__init__(False)
        self.app = app
        self.__user = user
        self.text = ""
        self.echo = False

    def finished(self, text):
        scr = self.app.screen()
        y, x = scr.getyx()
        scr.hline(1,1, ' ', x)
        self.app.pop_menu()
        self.app.login(self.__user, text)

    def draw(self):
        scr = self.app.screen()
        scr.addstr(1, 1, "Enter your password: ")

class ChoiceRunner:
    def __init__(self, app, **kwargs):
        self.__app = app
        self.__args = kwargs

    def run(self, command):
        parts = render_template(command, self.__args).split(' ')
        self.__commands[parts[0]](self, parts[1:])

    def login(self, args):
        self.__app.push_menu(UserNameMenu(self.__app))

    def game(self, args):
        self.__app.game_menu(int(args[0]))

    def quit(self, args):
        self.__app.quit()

    def play(self, args):
        self.__app.play(int(args[0]))

    __commands = {
        "login" : login,
        "play" : play,
        "game" : game,
        "quit" : quit
    }

class Menu:
    def __init__(self, y, app, **kwargs):
        self.__runner = ChoiceRunner(app, **kwargs)
        self.__app = app
        self.__lines = []
        self.__keys = {}
        self.__args = kwargs
        # menus can either be an array describing the menu,
        # or a string that the engine expands to some menu items
        for f in y:
            if f is not "blank" and isinstance(f, str):
                menus = app.generate_menus(f)
                for i in menus:
                    self.__add_item(i)
            else:
                self.__add_item(f)

    def __add_item(self, f):
        if f == "blank":
            self.__lines.append("")
        else:
            text = render_template(f['title'], self.__args)
            self.__keys[ord(f['key'])] = f
            self.__lines.append("{}) {}".format(f['key'], text))

    def draw(self):
        i = 1
        scr = self.__app.screen()
        for f in self.__lines:
            scr.addstr(i, 1, f)
            i += 1

    def key(self, c):
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
