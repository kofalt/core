"""Provides data mapper for site settings"""
import datetime

from ... import config
from ..models import SiteSettings

SITE_SINGLETON_ID = 'site'

class SiteSettingsMapper(object):
    """Data mapper for site settings"""
    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.singletons

    def patch(self, doc):
        """Update the site settings, with the given update fields in doc.

        The modified time will be set automatically. If the site settings doesn't
        exist, it will be created.

        Args:
            doc (dict): The set of updates to apply
        """
        # Create the upsert document
        now = datetime.datetime.now()
        update = {
            '$set': doc,
            '$setOnInsert': {
                'created': now
            }
        }
        update['$set']['modified'] = now

        self.dbc.update_one({'_id': SITE_SINGLETON_ID}, update, upsert=True)

    def find(self):
        """Find the current site config.

        Returns:
            SiteSettings: The loaded site settings, or None
        """
        result = self.dbc.find_one({'_id': SITE_SINGLETON_ID})
        return self._load_site_settings(result)

    def _load_site_settings(self, doc):
        """Loads a single item from a mongo dictionary"""
        if doc is None:
            return None

        # Pop the singleton id field, not required
        doc.pop('_id', None)

        return SiteSettings.from_dict(doc)

