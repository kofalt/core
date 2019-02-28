#from ..storage import Storage
from fs import open_fs
import hashlib
import fs
import six

from flywheel_common import storage
#from util import path_from_uuid, format_hash
from flywheel_common.storage import path_from_uuid, format_hash
from flywheel_common.storage import Interface

DEFAULT_HASH_ALG = 'sha384'
DEFAULT_BUFFER_SIZE = 2 ** 20

class PyFsStorage(Interface):

    def __init__(self, url):
        super(PyFsStorage, self).__init__()
        self._fs = open_fs(url)
        self._has_signed_url = hasattr(self._fs, 'get_signed_url')

        self._default_hash_alg = DEFAULT_HASH_ALG
        self._buffer_size = DEFAULT_BUFFER_SIZE

    def open(self, uuid, path_hint, mode, **kwargs):

        if 'w' in mode:
            if path_hint:
                dirname = fs.path.dirname(path_hint)
                if dirname and not self._fs.isdir(dirname):
                    self._fs.makedirs(fs.path.dirname(path_hint))
            else:
                # the legacy PyFs files will always make use of the path_hint when open for writing. Future file types may not
                pass

        # Allow error to bubble up
        return self._fs.open(path_hint, mode)
    
    def remove_file(self, uuid, path_hint):
        if path_hint:
            self._fs.remove(path_hint)
        else:
            pass

        return True

    def remove_file(self, uuid, path_hint):
        if path_hint:
            self._fs.remove(path_hint)
        else:
            pass

        return True

    def is_signed_url(self):
        return self._has_signed_url

    def get_signed_url(self,
                       uuid,
                       path_hint,
                       purpose='download',
                       filename=None,
                       attachment=True,
                       response_type=None):
        """
        Generate signed URL for upload/download purposes. It makes possible to set the filename when downloading the
        file as an attachment and set the Content-Type header of the response. The latter is useful for example we
        want to show a html file instead of downloading it.
        :param uuid: file uuid
        :param path_hint: File path
        :param purpose: download/upload
        :param filename: Name of the downloaded file, used in the content-disposition header
        :param attachment: True/False, attachment or not
        :param response_type: Content-Type header of the response
        :return: string, Signed URL
        :raises: ResourceNotFound, FileExpected, NoURL
        """

        if not self._has_signed_url:
            raise OSError('Current FS does not support signed URLs')

        # This implementation will require path_hint
        return self._fs.get_signed_url(path_hint, purpose=purpose, filename=filename, attachment=attachment, response_type=response_type)

    def can_redirect_request(self, headers):
        # Legacy implementation is just GC storage, which can redirect
        # regardless of headers
        return self._has_signed_url

    def get_file_hash(self, uuid, path_hint):

        hash_alg = self._default_hash_alg
        hasher = hashlib.new(hash_alg)

        if path_hint:
            filepath = path_hint
        else:
            filepath = path_from_uuid(uuid)

        if not isinstance(filepath, unicode):
            filepath = six.u(filepath)

        with self._fs.open(filepath, 'rb') as f:
            while True:
                data = f.read(self._buffer_size)
                if not data:
                    break
                hasher.update(data)

        return format_hash(hash_alg, hasher.hexdigest())

    def get_file_info(self, uuid, path_hint):

        data = {}

        if path_hint:
            if not self._fs.exists(path_hint):
                return None
            data['filesize'] = int(self._fs.getsize(path_hint))
        else:
            path = path_from_uuid(uuid)
            if not self._fs.exists(path):
                return None
            data['filesize'] = int(self._fs.getsize(path))

        return data

    def get_fs(self):
        """
            Returns the local file system OSFS object for local file maniulation/processing
        """
        return self._fs
