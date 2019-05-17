"""Provide the DownloadTarget class"""
from ... import models
import os.path


class DownloadTarget(models.Base):
    """Represents a single target for a download summary or retrieval."""

    def __init__(self, download_type, dst_path, container_type, container_id, modified, size, filetype, file_id=None, filename=None, file_group=None, src_path=None):
        """Create a new download target

        Args:
            download_type (str): The type of download, used for sub-class instantiation
            dst_path (str): The output path of the file
            container_type (str): The singular container type (e.g. subject)
            container_id (str): The id of the container
            modified (datetime): When this file was last modified
            size (int): The size of the file, in bytes
            filetype (str): The filetype of the file (e.g. dicom or json)
            file_id (str): The optional file id, if applicable
            filename (str): The optional filename, if applicable
            file_group (str): The optional file_group, if applicable
            src_path (str): The optional source file path, if applicable
        """
        super(DownloadTarget, self).__init__()

        self.download_type = download_type
        """str: The type of download, one of file, metadata, bids_sidecar"""

        self.dst_path = dst_path
        """str: The path to the file on disk"""

        self.container_type = container_type
        """str: The singularized source container type"""

        self.container_id = container_id
        """str: The source container id"""

        self.modified = modified
        """datetime: The last modified time of the file"""

        self.size = size
        """int: The size of the file, in bytes"""

        self.filetype = filetype
        """str: The optional source file type"""

        self.file_id = file_id
        """str: The optional source file uuid"""

        self.filename = filename
        """str: The name of the source file"""

        self.file_group = file_group
        """str: The group that the source file belongs to (e.g. input/files)"""

        self.src_path = src_path
        """str: The optional source file path"""

    @property
    def dst_name(self):
        """The destination filename"""
        if self.dst_path is not None:
            return os.path.basename(self.dst_path)
        return None
