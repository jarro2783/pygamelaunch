"""A game launcher module."""

import pyterm

def rungame(
        program,
        arguments,
        record_host,
        record_port,
        record_user):
    """Run a game."""

    executor = pyterm.ExecProgram(program, *arguments)
    net_writer = pyterm.ExecWriter(
        "termrecord_client",
        "-host", record_host, "-port", record_port,
        "-user", record_user, "-send")
    capture = pyterm.Capture(executor, writers=[net_writer])
    capture.run()

class Watcher:
    """Watch a running game."""
    def __init__(self, server, port, watch_user):
        self.__server = server
        self.__port = port
        self.__user = watch_user
        self.__watcher = pyterm.ExecWatcher(
            "termrecord_client",
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
        """Do the actual watching."""
        self.__watcher.watch()
