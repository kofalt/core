"""Provides a file-like wrapper around a URL"""
class URLFileWrapper(object):
    """Wraps a request to a signed url as a file-like object (with read and close)"""

    def __init__(self, url, http):
        """Initialize the URLFileWrapper.

        Args:
            url (str): The signed url
            http (PoolManager): The shared pool manager instance
        """
        self.url = url
        self.http = http

        self._response = None

    def open(self):
        self._response = self.http.request('GET', self.url, preload_content=False)

        if self._response.status < 200 or self._response.status > 299:
            raise IOError('Unable to open URL: status={}, reason={}'.format(self._response.status,
                self._response.reason))

        return self

    def read(self, length=None):
        if self._response is None:
            raise IOError('URL is not opened for reading')

        return self._response.read(length)

    def close(self):
        if self._response:
            self._response.release_conn()
            self._response = None
