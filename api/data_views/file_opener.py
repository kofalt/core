import os
import gzip
import time
import zipfile

from .. import files
from ..site.providers import get_provider_instance
from .util import filtered_container_list

# TODO: Should we support tarfiles?
class FileOpener(object):
    """Context manager that will open a (possibly compressed) filesystem file.

    FileOpener will close any open files when the context is exited.
    """
    def __init__(self, file_entry, zip_filter, match_type='first'):
        """Create a new FileOpener

        Arguments:
            file_entry (dict): The file entry as retrieved from the database
            zip_filter (regex): The regular expression to match zip entries, if applicable
            match_type (str): The optional match type if multiple zip entries are matched (default is first)
        """
        self.file_entry = file_entry
        self.zip_filter = zip_filter
        self.match_type = match_type

        # This is the opened file_entry file
        self._system_fd = None

        # This is the optional ZipFile instance
        self._zipfile = None

        # This is the optional set of zipfile entries
        self._zip_entries = []

        # This is the final _fd for reading
        self._fd = None

        # The final filename
        self._name = file_entry['name']

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
            file_system = get_provider_instance(self.file_entry['provider_id']).storage_plugin
            file_path = files.get_file_path(self.file_entry)

            self._system_fd = file_system.open(self.file_entry.get('_id'), file_path, open_mode)

            if self.zip_filter:
                # Open zipfile
                self._zipfile = zipfile.ZipFile(self._system_fd)

                # Find zip entry
                zip_entries = []
                for zipinf in self._zipfile.infolist():
                    zip_entries.append({
                        'path': zipinf.filename,
                        'timestamp': time.mktime(zipinf.date_time + (0, 0, -1))
                    })

                self._zip_entries = filtered_container_list(zip_entries, [('path', self.zip_filter)],
                        match_type=self.match_type, date_key='timestamp')

                if not self._zip_entries:
                    raise RuntimeError('Could not find matching zip entry in zip file: {}'.format(self.file_entry['name']))

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

    def files(self):
        """Iterator for each of the files opened by this file opener"""
        if self._fd:
            yield self._name, self._fd
        elif self._zipfile:
            for entry in self._zip_entries:
                fd = self._zipfile.open(entry['path'], 'r')
                yield entry['path'], fd

    def close(self):
        """Close any open files"""
        # NOTE: This function should be re-entrant
        if self._zipfile:
            self._zipfile.close()
            self._zipfile = None

        if self._system_fd:
            self._system_fd.close()
            self._system_fd = None


