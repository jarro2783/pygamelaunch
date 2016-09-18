import pyterm

class Game:
    def __init__(self,
                 program,
                 arguments,
                 record_host,
                 record_port,
                 record_user):
        self.__program = program
        self.__args = arguments
        self.__record_host = record_host
        self.__record_port = record_port
        self.__record_user = record_user

    def run(self):
        executor = pyterm.ExecProgram(self.__program, *self.__args)
        net_writer = pyterm.ExecWriter("termrecord_client",
            "-host", self.__record_host, "-port", self.__record_port,
            "-user", self.__record_user, "-send")
        capture = pyterm.Capture(executor, writers=[net_writer])
        capture.run()

class Watcher:
    def __init__(self, server, port, watch_user):
        self.__server = server
        self.__port = port
        self.__user = watch_user
        self.__watcher = pyterm.ExecWatcher("termrecord_client",
            [
                "-host",
                server,
                "-port",
                port,
                "-user",
                watch_user,
                "-watch"
            ])

    def watch(self):
        self.__watcher.watch()
