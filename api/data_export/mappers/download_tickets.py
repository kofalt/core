"""Provides data mappers for download tickets"""
from ... import config
from .. import models


class DownloadTickets(object):
    """Data mapper for download tickets.

    NOTE: Targets are separated into their own collection to avoid doc size limit,
    but don't have their own mapper as their insertion/retrieval only ever happens
    within ticket context.

    NOTE: Given the transient nature of download tickets, there's no desire to
    introduce versioning for the "downloads" or "download_targets" collections.
    """
    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.downloads
        self.target_dbc = self.db.download_targets

    def insert(self, ticket):
        """Inserts a new download ticket.

        Args:
            ticket (DownloadTicket): The ticket to insert
        """
        ticket_dict = ticket.to_dict()
        target_dicts = ticket_dict.pop('targets')
        self.dbc.insert_one(ticket_dict)
        for target_dict in target_dicts:
            target_dict.update({
                'ticket_id': ticket.ticket_id,
                'timestamp': ticket.timestamp,
            })
        self.target_dbc.insert_many(target_dicts)

    def get(self, ticket_id):
        """Find the ticket for the given ticket_id.

        Args:
            ticket_id (str): The ticket ids

        Returns:
            DownloadTicket: The loaded ticket, or None
        """
        result = self.dbc.find_one({'_id': ticket_id})
        if result is not None:
            result['targets'] = list(self.target_dbc.find({'ticket_id': ticket_id}))
        return self._load_ticket(result)

    def _load_ticket(self, ticket):
        """Loads a single item from a mongo dictionary"""
        if ticket is None:
            return None

        return models.DownloadTicket.from_dict(ticket)
