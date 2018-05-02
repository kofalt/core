import os
import zipfile
import gzip

from .. import files

# TODO: Should we support tarfiles?
class FileOpener(object):
    def __init__(self, file_entry, zip_filter):
        self.file_entry = file_entry
        self.zip_filter = zip_filter

        # This is the opened file_entry file
        self._system_fd = None

        # This is the optional ZipFile instance
        self._zipfile = None

        # This is the final _fd for reading
        self._fd = None

        # The final filename
        self._name = file_entry['name']

    @property
    def name(self):
        return self._name.lower()

    @property
    def fd(self):
        return self._fd

    def is_gzip(self):
        _root, ext = os.path.splitext(self.file_entry['name'])
        return ext == '.gz'

    def __enter__(self):
        # Try to open the file
        open_mode = 'r'
        gz = self.is_gzip()

        if self.zip_filter or gz:
            open_mode = 'rb'
        try:
            # Open the file using file_system
            file_path, file_system = files.get_valid_file(self.file_entry)
            self._system_fd = file_system.open(file_path, open_mode)

            if self.zip_filter:
                # Open zipfile
                self._zipfile = zipfile.ZipFile(self._system_fd)

                # Find zip entry
                matched_file = None
                for path in self._zipfile.namelist():
                    if self.zip_filter.match(path):
                        matched_file = path
                        break
                        
                if not matched_file:
                    raise RuntimeError('Could not find matching zip entry in zip file: {}'.format(self.file_entry['name']))

                self._fd = self._zipfile.open(path, 'r')
                self._name = path
            elif gz:
                # Open as gzip
                self._fd = gzip.GzipFile(fileobj=self._system_fd, mode='r')
                self._name, _ext = os.path.splitext(self._name)
            else:
                # Read file directly
                self._fd = self._system_fd

            return self
        except Exception:
            self.cleanup()
            raise

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def cleanup(self):
        # NOTE: This function should be re-entrant
        if self._zipfile:
            self._zipfile.close()
            self._zipfile = None

        if self._system_fd:
            self._system_fd.close()
            self._system_fd = None

