#!/usr/bin/python3

import curses
import sys
import time
import yaml
import db
import hashlib

version = 0.1

class GameLauncher:
    def __init__(self, scr):
        self.__scr = scr
        self.__menus = []
        self.__exiting = False
        self.__user = ""

        self.__database = db.Database()

        y,x = scr.getmaxyx()
        ry = 4

        self.__window = curses.newwin(y - ry, x, ry, 0)
        scr.addstr(1, 1, "Pygamelaunch v{}".format(version))
        scr.refresh()

    def push_menu(self, menu):
        self.__menus.append(menu)
        self.__window.clear()
        menu.draw()
        self.__window.refresh()

    def pop_menu(self):
        self.__menus.pop()
        self.__window.clear()
        self.__top().draw()
        self.__window.refresh()

    def run(self):
        while not self.__exiting:
            c = self.__scr.getch()
            self.__top().key(c)

    def quit(self):
        self.__exiting = True

    def __top(self):
        return self.__menus[-1]

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
                self.__scr.addstr(3, 1, user)
        
class KeyInput:
    def __init__(self, echo):
        self.__text = ""
        self.__echo = echo

    def key(self, c):
        if c == ord('\n'):
            self.finished(self.text)
        else:
            ch = chr(c)
            self.text += ch

            if self.echo:
                scr = self.app.screen()
                scr.addstr(ch)
                scr.refresh()

class UserNameMenu(KeyInput):
    def __init__(self, app):
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
        self.app = app
        self.__user = user
        self.text = ""
        self.echo = False

    def finished(self, text):
        scr = self.app.screen()
        y, x = scr.getyx()
        scr.hline(1,1, ' ', x)
        scr.addstr(1, 1, "Login successful")
        scr.refresh()
        self.app.pop_menu()
        self.app.login(self.__user, text)

    def draw(self):
        scr = self.app.screen()
        scr.addstr(1, 1, "Enter your password: ")

class ChoiceRunner:
    def __init__(self, app):
        self.__app = app

    def run(self, command):
        parts = command.split(' ')
        self.__commands[parts[0]](self, parts[1:])

    def login(self, args):
        self.__app.push_menu(UserNameMenu(self.__app))

    def quit(self, args):
        self.__app.quit()

    __commands = {
        "login" : login,
        "quit" : quit
    }

class Menu:
    def __init__(self, y, app):
        self.__runner = ChoiceRunner(app)
        self.__app = app
        self.__order = y
        self.__keys = {}
        for f in y:
            self.__keys[ord(f['key'])] = f

    def draw(self):
        i = 4
        scr = self.__app.screen()
        for f in self.__order:
            scr.addstr(i, 2, "({}) {}".format(f['key'], f['title']))
            i += 1

    def key(self, c):
        if c in self.__keys:
            a = self.__keys[c]
            self.__runner.run(a['action'])

    def action(self, key):
        return self.__keys[key]['action']


def run(scr):
    game = GameLauncher(scr)

    f = open("menus.yaml")
    m = yaml.load(f)

    main = m['main']
    
    menu = Menu(main, game)
    game.push_menu(menu)

    game.run()

def main():
    curses.wrapper(run)

if __name__ == "__main__":
    main()
