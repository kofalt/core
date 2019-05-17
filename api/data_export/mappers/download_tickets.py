"""Provides data mappers for download tickets"""
from ... import config
from .. import models


class DownloadTickets(object):
    """Data mapper for download tickets.

    NOTE: Given the transient nature of download tickets, there's no desire to
    introduce versioning for the "downloads" collection.
    """

    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.downloads

    def insert(self, ticket):
        """Inserts a new download ticket.

        Args:
            ticket (DownloadTicket): The ticket to insert
        """
        # For mongo, we can simply convert to dict
        self.dbc.insert_one(ticket.to_dict())

    def get(self, ticket_id):
        """Find the ticket for the given ticket_id.

        Args:
            ticket_id (str): The ticket id

        Returns:
            DownloadTicket: The loaded ticket, or None
        """
        result = self.dbc.find_one({"_id": ticket_id})
        return self._load_ticket(result)

    def _load_ticket(self, ticket):
        """Loads a single item from a mongo dictionary"""
        if ticket is None:
            return None

        return models.DownloadTicket.from_dict(ticket)
