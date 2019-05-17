"""Provides DownloadStrategy hierarchy"""
import datetime
from abc import ABCMeta, abstractmethod

from .. import models, mappers
from ...web import errors

BYTES_IN_MEGABYTE = float(1 << 20)


class AbstractDownloadStrategy(object):
    __metaclass__ = ABCMeta

    # The default archive prefix, if not specified
    default_archive_prefix = "flywheel"

    def __init__(self, log, params):
        """Create a download strategy.

        Args:
            log (Logger): The context logger instance to use for logging.
            params (dict): The optional set of parameters for this strategy.
                May include 'prefix', which sets the archive path prefix.
        """
        self.log = log
        self.archive_prefix = params.get("prefix", self.default_archive_prefix)

    @abstractmethod
    def validate_spec(self, spec, summary):
        """Validate the input specification for a download.

        Args:
            spec (dict): The input specification for this download
            summary (bool): Whether or not this is generating a summary document

        Raises:
            InputValidationError: If the spec is invalid
        """

    @abstractmethod
    def identify_targets(self, spec, uid, summary):
        """Identifies the targets to add to the download.

        Args:
            spec (dict): The input specification for this download
            uid (str): The user id for authorization, otherwise None
            summary (bool): Whether or not this is generating a summary document

        Yields:
            DownloadTarget: The download targets to include
        """

    def create_ticket(self, spec, uid, client_addr, origin):
        """Identifies targets and creates a download ticket.

        Args:
            spec (dict): The input specification for this download
            uid (str): The user id for authorization, otherwise None
            client_addr (str): The client ip address for the download ticket
            origin (dict): The origin of the request

        Returns:
            dict: The download ticket details
        """
        targets = []
        count = 0
        total_size = 0

        # Walk our targets to generate a summary for the ticket
        for target in self.identify_targets(spec, uid, summary=False):
            count += 1
            total_size += target.size
            targets.append(target)

        if len(targets) > 0:
            filename = self.create_archive_filename()

            tickets = mappers.DownloadTickets()
            ticket = models.DownloadTicket("batch", client_addr, origin, filename, targets, total_size)
            tickets.insert(ticket)

            return {"ticket": ticket.ticket_id, "file_cnt": count, "size": total_size, "filename": filename}
        else:
            raise errors.APINotFoundException("No files matching the given filter could be found")

    def create_summary(self, spec, uid):
        """Provide summary data by filetype for a download specification.

        The default implementation is to run identify_targets, then roll up the results.
        This behavior can be overridden for optimization, as needed.

        Args:
            spec (dict): The input specification for this download
            uid (str): The user id for authorization, otherwise None

        Returns:
            dict: A download summary document that maps filetype to count and size (in MB)
        """
        totals = {}

        for target in self.identify_targets(spec, uid, summary=True):
            if target.filetype not in totals:
                totals[target.filetype] = {"_id": target.filetype, "count": 0, "mb_total": 0}

            sub_total = totals[target.filetype]
            sub_total["count"] += 1
            sub_total["mb_total"] += target.size / BYTES_IN_MEGABYTE

        return totals

    def create_archive_filename(self):
        """Create a filename for this archive.

        Returns:
            str: The archive filename
        """
        return self.archive_prefix + "_" + datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".tar"
