from fs import open_fs
import hashlib
import fs
import six
import os

from flywheel_common.storage import Interface, format_hash

DEFAULT_HASH_ALG = 'sha384'
DEFAULT_BUFFER_SIZE = 2 ** 20

class PyFsStorage(Interface):

    def __init__(self, url):
        super(PyFsStorage, self).__init__()
        self._fs = open_fs(url)
        self._has_signed_url = hasattr(self._fs, 'get_signed_url')

        self._default_hash_alg = DEFAULT_HASH_ALG
        self._buffer_size = DEFAULT_BUFFER_SIZE

    def open(self, uuid, mode, file_hash=None, **kwargs):

        if file_hash:
            file_path = self.path_from_hash(file_hash)
        else:
            file_path = self.path_from_uuid(uuid)
                # the legacy PyFs files will always make use of the file_hash when open for writing. Future file types may not

        # local fs is the only provider that takes file_path.
        # Used when placing packfile in a temp file to maintain directory structure
        if kwargs.get('file_path'):
            file_path = kwargs.get('file_path')

        if not isinstance(file_path, unicode):
            file_path = six.u(file_path)

        if 'w' in mode:
            dirname = fs.path.dirname(file_path)
            if dirname and not self._fs.isdir(dirname):
                self._fs.makedirs(fs.path.dirname(file_path))

        # Allow error to bubble up
        return self._fs.open(file_path, mode)

    def remove_file(self, uuid, file_hash=None):
        if file_hash:
            file_path = self.path_from_hash(file_hash)
        else:
            file_path = self.path_from_uuid(uuid)

        self._fs.remove(file_path)
        return True

    def is_signed_url(self):
        return self._has_signed_url

    def get_signed_url(self,
                       uuid,
                       purpose='download',
                       filename=None,
                       attachment=True,
                       response_type=None,
                       file_hash=None):
        """
        Generate signed URL for upload/download purposes. It makes possible to set the filename when downloading the
        file as an attachment and set the Content-Type header of the response. The latter is useful for example we
        want to show a html file instead of downloading it.
        :param uuid: file uuid
        :param purpose: download/upload
        :param filename: Name of the downloaded file, used in the content-disposition header
        :param attachment: True/False, attachment or not
        :param response_type: Content-Type header of the response
        :param file_hash: File hash for legacy files
        :return: string, Signed URL
        :raises: ResourceNotFound, FileExpected, NoURL
        """

        if not self._has_signed_url:
            raise OSError('Current FS does not support signed URLs')

        # This implementation will require file_path

        if file_hash:
            file_path = self.path_from_hash(file_hash)
        else:
            file_path = self.path_from_uuid(uuid)
            
        return self._fs.get_signed_url(file_hash, purpose=purpose, filename=filename, attachment=attachment, response_type=response_type)

    def can_redirect_request(self, headers):
        # Legacy implementation is just GC storage, which can redirect
        # regardless of headers
        return self._has_signed_url


    def get_file_hash(self, uuid, file_path=None):

        hash_alg = self._default_hash_alg
        hasher = hashlib.new(hash_alg)
        
        if not file_path:
            file_path = self.path_from_uuid(uuid)

        if not isinstance(file_path, unicode):
            file_path = six.u(file_path)

        with self._fs.open(file_path, 'rb') as f:
            while True:
                data = f.read(self._buffer_size)
                if not data:
                    break
                hasher.update(data)

        return format_hash(hash_alg, hasher.hexdigest())

    def get_file_info(self, uuid, file_hash=None):

        data = {}

        if file_hash:
            file_path = self.path_from_hash(file_hash)
        else:
            file_path = self.path_from_uuid(uuid)
        
        if not self._fs.exists(file_path):
            return None
 
        data['filesize'] = int(self._fs.getsize(file_path))
        return data


    def path_from_uuid(self, uuid_):
        """
        create a filepath from a UUID
        e.g.
        uuid_ = cbb33a87-6754-4dfd-abd3-7466d4463ebc
        will return
        cb/b3/cbb33a87-6754-4dfd-abd3-7466d4463ebc
        """
        uuid_1 = uuid_.split('-')[0]
        first_stanza = uuid_1[0:2]
        second_stanza = uuid_1[2:4]
        path = (first_stanza, second_stanza, uuid_)
        return fs.path.join(*path)

    def path_from_hash(self, hash_):
        """
        create a filepath from a hash
        e.g.
        hash_ = v0-sha384-01b395a1cbc0f218
        will return
        v0/sha384/01/b3/v0-sha384-01b395a1cbc0f218
        """
        hash_version, hash_alg, actual_hash = hash_.split('-')
        first_stanza = actual_hash[0:2]
        second_stanza = actual_hash[2:4]
        path = (hash_version, hash_alg, first_stanza, second_stanza, hash_)
        return os.path.join(*path)
    
    def get_fs(self):
        """
            Returns the local file system OSFS object for local file maniulation/processing
        """
        return self._fs


