"""Provides a simple wrapper around a write function"""


class ResponseWriter(object):
    """Utility class to provide file-like write & close functions"""

    def __init__(self, write):
        self.write = write

    def close(self):
        pass
