"""Provides a file-like wrapper around a URL"""
import io

class URLFileWrapper(object):
    """Wraps a request to a signed url as a file-like object (with read and close)"""

    buffer_size = 2 ** 20

    def __init__(self, url, http):
        """Initialize the URLFileWrapper.

        Args:
            url (str): The signed url
            http (PoolManager): The shared pool manager instance
        """
        self.url = url
        self.http = http

        self._response = None
        self._reader = None

    def __enter__(self):
        self._response = self.http.request('GET', self.url, preload_content=False)

        if self._response.status < 200 or self._response.status > 299:
            raise IOError('Unable to open URL: status={}, reason={}'.format(self._response.status,
                self._response.reason))

        self._reader = io.BufferedReader(self._response, buffer_size=self.buffer_size)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def read(self, length=None):
        if self._reader is None:
            raise IOError('URL is not opened for reading')

        return self._reader.read(length)

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None

        if self._response:
            self._response.release_conn()
            self._response = None
