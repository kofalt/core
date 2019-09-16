"""Provides functionality for writing targets as JSON from a download ticket"""
import json

from requests_toolbelt.multipart.encoder import MultipartEncoder

from ..web.encoder import custom_json_serializer


class JsonTargetWriter(object):
    """Class that writes targets to the given tar file"""

    # The size of file chunks to read/write
    CHUNKSIZE = 2 ** 20

    def __init__(self, fileobj, boundary):
        """Create a new JsonTargetWriter.

        Args:
            fileobj (file): The file-like object to write to.
            boundary (str): The boundary to use when multipart-encoding.
        """
        self.fileobj = fileobj
        self.boundary = boundary

    def write(self, file_source):
        """Given a DownloadFileSource, write each target doc as JSON.

        Args:
            file_source (DownloadFileSource): The file source
        """

        def target_to_field(target):
            if target.download_type == 'metadata_sidecar':
                target.metadata = file_source.get_metadata(target)
            data = json.dumps(target.to_dict(), indent=2, default=custom_json_serializer)
            return (target.filename, (target.filename, data, 'application/json'))

        fields = (target_to_field(target) for target in file_source)
        multipart_encoder = MultipartEncoder(fields, boundary=self.boundary)
        while True:
            chunk = multipart_encoder.read(self.CHUNKSIZE)
            if not chunk:
                break
            self.fileobj.write(chunk)

    def close(self):
        """Closes the underlying file object."""
        if self.fileobj:
            self.fileobj.close()
            self.fileobj = None
