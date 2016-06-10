import curses
import time
import yaml

version = 0.1

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
