"""Provides functionality for creating files on a container"""
import datetime
import uuid

from . import config, files, util, upload
from .placer import TargetedMultiPlacer

class PendingFile(object):
    def __init__(self, filename, path, fileobj, metadata):
        self.filename = filename
        self.path = path
        self.fileobj = fileobj
        
        if metadata is not None:
            self.metadata = metadata.copy()
        else:
            self.metadata = {}
        self.metadata['name'] = filename

class FileCreator(object):
    """Helper class for creating file(s) on target container"""
    def __init__(self, handler, container_type, container):
        """Initialize the file creator, setting the destination container"""
        self.handler = handler
        self.file_processor = None

        self.container_type = container_type
        self.container = container

        self._files = []

    def create_file(self, filename, metadata=None):
        """Open a file for writing, and add it to the pending file list.

        Arguments:
            filename (str): The name of the file to create
            metadata (dict): The optional metadata to set
        """
        if not self.file_processor:
            self.file_processor = files.FileProcessor(config.fs)

        path, fileobj = self.file_processor.make_temp_file()
        self._files.append(PendingFile(filename, path, fileobj, metadata))
        return fileobj

    def finalize(self):
        """Finalize the the file creation.
        
        This moves the temp files that were created into place, and updates the container.

        Returns:
            list: The list of files that were saved
        """
        timestamp = datetime.datetime.utcnow()
        context = { 'uid': self.handler.uid }
        origin = self.handler.origin

        # Construct the file metadata list
        metadata = [ pending_file.metadata for pending_file in self._files ]

        # Create our targeted placer
        placer = TargetedMultiPlacer(self.container_type, self.container, self.container['_id'],
            metadata, timestamp, origin, {'uid': self.handler.uid}, self.file_processor, self.handler.log_user_access)

        for pending_file in self._files:
            # Not a great practice. See process_upload() for details.
            cgi_field = util.obj_from_map({
                'filename': pending_file.filename,
                'path': pending_file.path,
                'size': pending_file.fileobj.size,
                'hash': pending_file.fileobj.hash,
                'uuid': str(uuid.uuid4()),
                'mimetype': util.guess_mimetype(pending_file.filename),
                'modified': timestamp
            })
            file_attrs = upload.make_file_attrs(cgi_field, origin)

            # Place the file
            placer.process_file_field(cgi_field, file_attrs)

        # And return the result
        return placer.finalize()
       
    def close(self):
        """Close all opened tempfiles, and delete the temp filesystem"""
        for pending_file in self._files:
            pending_file.fileobj.close()

    def __enter__(self):
        return self

    def __exit__(self, exc, value, tb):
        self.close()
