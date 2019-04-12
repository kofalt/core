import pymongo.errors

from .. import models
from ... import config
from ...web import errors


class MasterSubjectCodes(object):
    """Data mapper for master subject codes."""

    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.master_subject_codes

    def insert(self, msc):
        """Insert a new master subject code.

        Arguments:
            msc (MasterSubjectCode) -- The msc to insert

        Raises:
            errors.APIConflictException -- Raises when insert_one raised a pymongo DuplicateKeyError
        """

        try:
            insert_payload = msc.to_dict()
            # remove None fields
            for key in insert_payload.keys():
                if insert_payload.get(key) is None:
                    insert_payload.pop(key)
            self.dbc.insert_one(insert_payload)
        except pymongo.errors.DuplicateKeyError:
            raise errors.APIConflictException("Couldn't insert master subject code.")

    def update(self, msc_id, **kwargs):
        """Update the given master subject code

        Arguments:
            msc_id (string) -- Id of the msc to update
            **kwargs -- Fields to update/set
        """

        self.dbc.update_one({'_id': msc_id}, {'$set': kwargs})

    def get_by_id(self, msc_id):
        """Get msc by id.

        Arguments:
            msc_id (string) -- Id of the msc

        Returns:
            MasterSubjectCode -- The loaded msc or None
        """

        return self._load_msc(self.dbc.find_one({'_id': msc_id}))

    def find(self, **kwargs):
        """Find master subject codes.

        Arguments:
            **kwargs -- search fields
        """

        for msc in self.dbc.find(kwargs):
            yield self._load_msc(msc)

    def _load_msc(self, msc):
        """Loads a single item from a mongo dictionary"""
        if msc is None:
            return None

        return models.MasterSubjectCode.from_dict(msc)
