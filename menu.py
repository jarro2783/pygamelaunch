import curses
import time
import yaml

version = 0.1

class GameLauncher:
    def __init__(self, scr):
        self.__scr = scr

    def push_menu(self, menu):
        pass

    def pop_menu(self):
        pass

    def run(self):
        while not exiting:
            getch()

class LoginMenu:
    def __init__(self, app):
        pass

    def key(self, c):
        pass

class ChoiceRunner:
    def __init__(self, app):
        self.__app = app

    def run(self, command):
        parts = command.split(' ')
        self.__commands[parts[0]](parts[1:]])

    def login(self, args):
        self.__app.push_menu(LoginMenu(self.__app))

    __commands = {
        "login" : login
    }

class Menu:
    def __init__(self, y):
        self.__order = y
        self.__keys = {}
        for f in y:
            self.__keys[f['key']] = f

    def draw(self):
        strings = []
        for f in self.__order:
            strings.append("({}) {}".format(f['key'], f['title']))
        return strings

    def action(self, key):
        return self.__keys[key]['action']


def run(scr):
    game = GameLauncher(scr)

    scr.addstr(1, 1, "Python Game Launcher: v{}".format(version))

    f = open("menus.yaml")
    m = yaml.load(f)

    main = m['main']
    
    menu = Menu(main)
    s = menu.draw()

    row = 3
    for f in s:
        scr.addstr(row, 2, f)
        row += 1

    scr.refresh()
    time.sleep(5)

def main():
    curses.wrapper(run)

if __name__ == "__main__":
    main()
