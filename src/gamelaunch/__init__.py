"""A game launcher module."""

import os
import pyterm

#pylint: disable=too-many-arguments
def rungame(
        program,
        arguments,
        record_host,
        record_port,
        record_user,
        idle_time):
    """Run a game."""

    executor = pyterm.ExecProgram(program, *arguments)
    net_writer = pyterm.ExecWriter(
        "termrecord_client",
        "-host", record_host, "-port", record_port,
        "-user", record_user, "-send")
    capture = pyterm.Capture(executor, idle_time, [net_writer])
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

def execwait(prog, *args):
    pid = os.fork()

    if pid == 0:
        os.close(0)
        os.close(1)
        os.close(2)

        os.execlp(prog, *args)
        os.exit(1)
    else:
        os.waitpid(pid, 0)
