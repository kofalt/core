import collections

from timeit import default_timer

from . import values
from .. import config

log = config.log


class RequestWrapper(object):
    def __init__(self, request, response):
        """Wrap a pending request/response in a context manager that will collect stats.

        Arguments:
            request: The request object
            response: The response object
        """
        self._start = 0
        self._bytes_sent = 0
        self._request = request
        self._response = response
        self._status = 200
        self._write_on_exit = True

        if response and hasattr(response, "write"):
            response.write = self.__instrument_write_fn(response.write)

    def __enter__(self):
        self._start = default_timer()
        return self

    def __exit__(self, exception_type_dummy, exception_value_dummy, traceback_dummy):
        # Write metrics
        if self._write_on_exit:
            self.__write_metrics()

    def set_status(self, status):
        """Set the status code of the response, if not 200
        
        Arguments:
            status (int): The response code
        """
        self._status = status

    def wrap_handler(self, fn):
        """Wrap the handler function fn, such that stats will be written on return.

        Arguments:
            fn (function): The function to wrap

        Returns:
            function: The wrapped function
        """
        self._write_on_exit = False

        # We wrap the handler function, so that we can instrument
        # the write function in order to get a total number of bytes
        def handler(environ, start_response):
            # Add instrumentation to start_response
            def start_response_wrapper(*args, **kwargs):
                write_fn = start_response(*args, **kwargs)
                return self.__instrument_write_fn(write_fn)

            try:
                return fn(environ, start_response_wrapper)
            finally:
                self.__write_metrics()

        return handler

    def __instrument_write_fn(self, write):
        """Adds instrumentation to the given write function to collect # of bytes written.

        Arguments:
            write (function): The write function to instrument
        
        Returns:
            function: The instrumented write function
        """

        def write_fn(*args, **kwargs):
            # Just check if the first item of args has a length
            if args and isinstance(args[0], collections.Sized):
                self._bytes_sent = self._bytes_sent + len(args[0])

            return write(*args, **kwargs)

        return write_fn

    def __write_metrics(self):
        """Collects the metrics for this request"""
        try:
            response_time = max(default_timer() - self._start, 0)

            template = "UNKNOWN"
            if hasattr(self._request, "route") and hasattr(self._request.route, "template"):
                template = self._request.route.template

            method = getattr(self._request, "method", "UNKNOWN")

            labels = [method, template, str(self._status)]
            values.RESPONSE_TIME.labels(*labels).inc(response_time)
            values.RESPONSE_SIZE.labels(*labels).inc(self._bytes_sent)
            values.RESPONSE_COUNT.labels(*labels).inc(1)

        except:  # pylint: disable=bare-except
            log.exception("Error recording metrics")
