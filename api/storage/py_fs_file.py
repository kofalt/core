from .storage import Storage
from fs import open_fs
import fs

#This is OSFS only.   Which is legacy only

class PyFsFile(Storage):

    def __init__(self, url):
        super (PyFsFile, self).__init__()
        self._fs = open_fs(url)
        self._has_signed_url = hasattr(self._fs, 'get_signed_url')
        
    def open(self, id, path_hint, mode, options):

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

    def is_signed_url(self):
        return self._has_signed_url

    def get_signed_url(self, 
                       id, 
                       path_hint,
                       purpose='download',
                       filename=None,
                       attachment=True,
                       response_type=None):
        """
        Generate signed URL for upload/download purposes. It makes possible to set the filename when downloading the
        file as an attachment and set the Content-Type header of the response. The latter is useful for example we
        want to show a html file instead of downloading it.
        :param id: file uuid
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

    def get_file_hash(self, id, path_hint):
        return None
