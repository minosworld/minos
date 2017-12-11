import subprocess as sp
from threading import Thread


# http://stackoverflow.com/questions/35488927/send-subprocess-popen-stdout-stderr-to-logging-module
class BackgroundPopen(sp.Popen):
    @staticmethod
    def _proxy_lines(pipe, line_handler, exit_handler=None):
        with pipe:
            while True:
                line = pipe.readline()
                if line:
                    if line_handler is not None:
                        line_handler(line.rstrip())
                else:
                    break
            if exit_handler is not None:
                exit_handler()

    def __init__(self, name, logger, out_handler, err_handler, *args, **kwargs):
        kwargs['stdout'] = sp.PIPE
        kwargs['stderr'] = sp.PIPE
        super(self.__class__, self).__init__(*args, **kwargs)
        self.name = name
        self._logger = logger

        out_exit_handler = None
        err_exit_handler = None
        if logger is not None:
            out_exit_handler = lambda: logger.info('Finished %s stdout' % self.name)
            if out_handler is None:
                out_handler = lambda line: logger.info(line)
            err_exit_handler = lambda: logger.info('Finished %s stderr' % self.name)
            if err_handler is None:
                err_handler = lambda line: logger.error(line)

        t = Thread(name=name + '_out', target=self._proxy_lines, args=[self.stdout, out_handler, out_exit_handler])
        t.daemon = True
        t.start()
        self._thread_out = t

        t2 = Thread(name=name + '_err', target=self._proxy_lines, args=[self.stderr, err_handler, err_exit_handler])
        t2.daemon = True
        t2.start()
        self._thread_err = t2

    def flush(self):
        # flush logger

        # TODO: this hangs, how to flush stdout and stderr?
        # try:
        #     self.stdout.flush()
        # except:
        #     # pretend nothing happened
        #     pass
        #
        # try:
        #     self.stderr.flush()
        # except:
        #     # pretend nothing happened
        #     pass

        if self._logger is not None:
            for handler in self._logger.handlers:
                handler.flush()

    def close(self):
        if self._thread_out is not None:
            if self._logger is not None:
                self._logger.info('Waiting for %s stdout to finish' % self.name)
            self._thread_out.join()
            self._thread_out = None
        if self._thread_err is not None:
            if self._logger is not None:
                self._logger.info('Waiting for %s stderr to finish' % self.name)
            self._thread_err.join()
            self._thread_err = None
        self.flush()


    def __del__(self):
        self.close()
        super(self.__class__, self).__del__(self)
