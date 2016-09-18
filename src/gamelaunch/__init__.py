import pyterm

class Game:
    def __init__(self,
                 program,
                 arguments,
                 record_host,
                 record_port,
                 record_user):
        self.__program = pyterm.ExecProgram(program, *arguments)
        net_writer = pyterm.ExecWriter("termrecord_client",
            "-host", record_host, "-port", record_port,
            "-user", record_user, "-send")
        self.__capture = pyterm.Capture(program, writers=[net_writer])

    def run(self):
        self.__capture.run()
