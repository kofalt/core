"""Provide the DownloadTicket class"""
import datetime
import uuid

from ... import models
from .download_target import DownloadTarget


class DownloadTicket(models.Base):
    """Represents a single ticket for a download summary or retrieval."""

    def __init__(self, download_type, ip, origin, filename, targets, size):
        """Create a new download ticket

        Args:
            download_type (str): The type of download
            ip (str): The client ip address
            origin (dict): The client origin
            filename (str): The name of the file for the download response
            targets (list): The list of DownloadTargetS
            size (int): The total size of the download
        """
        super(DownloadTicket, self).__init__()

        self._id = str(uuid.uuid4())
        """str: The unique id of the ticket"""

        self.timestamp = datetime.datetime.now()
        """datetime: The timestamp when the ticket was created"""

        self.download_type = download_type
        """str: The type of download"""

        self.ip = ip
        """str: The ip address of the download initiator"""

        self.origin = origin
        """dict: The origin of the download (e.g. user)"""

        self.filename = filename
        """str: The filename to use when serving the download ticket"""

        self.targets = targets
        """list(DownloadTarget): The list of DownloadTargetS"""

        self.size = size
        """int: The estimated total size of the download (does not include metadata)"""

    @property
    def ticket_id(self):
        """str: The unique id of the ticket"""
        return self._id

    @classmethod
    def from_dict(cls, dct):
        # Perform additional conversion of child attributes
        result = super(DownloadTicket, cls).from_dict(dct)
        result.targets = [DownloadTarget.from_dict(target) for target in dct.get("targets", [])]
        return result
