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

def watch(server, port, watch_user):
    """Watch a running game."""
    watcher = pyterm.ExecWatcher(
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
    watcher.watch()
