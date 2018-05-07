import os
import zipfile
import gzip

from .. import files

# TODO: Should we support tarfiles?
class FileOpener(object):
    """Context manager that will open a (possibly compressed) filesystem file.

    FileOpener will close any open files when the context is exited.
    """
    def __init__(self, file_entry, zip_filter):
        """Create a new FileOpener

        Arguments:
            file_entry (dict): The file entry as retrieved from the database
            zip_filter (regex): The regular expression to match zip entries, if applicable
        """
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
        """str: The name of the opened file"""
        return self._name.lower()

    @property
    def fd(self):
        """file: The currently opened file"""
        return self._fd

    def is_gzip(self):
        """Check if the file described by file_entry is a gzip file"""
        _, ext = os.path.splitext(self.file_entry['name'])
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

                self._fd = self._zipfile.open(matched_file, 'r')
                self._name = matched_file 
            elif gz:
                # Open as gzip
                self._fd = gzip.GzipFile(fileobj=self._system_fd, mode='r')
                self._name, _ = os.path.splitext(self._name)
            else:
                # Read file directly
                self._fd = self._system_fd

            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, exception_type, exception_value, traceback):
        self.close()

    def close(self):
        """Close any open files"""
        # NOTE: This function should be re-entrant
        if self._zipfile:
            self._zipfile.close()
            self._zipfile = None

        if self._system_fd:
            self._system_fd.close()
            self._system_fd = None

