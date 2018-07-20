import datetime
import uuid

from . import config, files, util, upload
from .placer import TargetedPlacer

class FileCreator(object):
    """Handle creation of a single file on target container"""
    def __init__(self, handler):
        self.handler = handler
        self.file_processor = None
        self.filepath = None
        self.fileobj = None
        self.filename = None

    def create_file(self, filename):
        self.filename = filename
        if not self.file_processor:
            self.file_processor = files.FileProcessor(config.fs)

        self.filepath, self.fileobj = self.file_processor.make_temp_file()
        return self.fileobj

    def finalize(self, target_container_type, target_container):
        self.fileobj.close()

        timestamp = datetime.datetime.utcnow()
        metadata = { 'name': self.filename }
        context = { 'uid': self.handler.uid }

        # Create our targeted placer
        placer = TargetedPlacer(target_container_type, target_container, target_container['_id'],
            metadata, timestamp, self.handler.origin, context, self.file_processor, self.handler.log_user_access)

        # Not a great practice. See process_upload() for details.
        cgi_field = util.obj_from_map({
            'filename': self.filename,
            'path': self.filepath,
            'size': self.fileobj.size,
            'hash': self.fileobj.hash,
            'uuid': str(uuid.uuid4()),
            'mimetype': util.guess_mimetype(self.filename),
            'modified': timestamp
        })
        file_attrs = upload.make_file_attrs(cgi_field, self.handler.origin)

        # Place the file
        placer.process_file_field(cgi_field, file_attrs)

        # And return the result
        return placer.finalize()
       
    def close(self):
        if self.fileobj:
            self.fileobj.close()


