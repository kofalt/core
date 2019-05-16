"""Provides data mapper for site settings"""
import datetime

from ... import config
from ...dao import dbutil
from .. import models

SITE_SINGLETON_ID = 'site'

class SiteSettings(object):
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

        # We only want to update the providers specified in the object, not overwrite all on patch
        for class_ in doc.get('providers', {}):
            if not update['$set'].get('providers'):
                update['$set']['providers'] = {}
            update['$set']['providers.' + class_] = doc['providers'][class_]
        if doc.get('providers'):
            doc.pop('providers')

        self.dbc.update_one({'_id': SITE_SINGLETON_ID}, update, upsert=True)

    def ensure_provider(self, provider_class, default_provider_id):
        """Ensure that site settings exists and that provider of the given type is set.

        Args:
            provider_class (str): The provider class
            default_provider_id (ObjectId): The default id to set, if it doesn't already exist
        """
        provider_key = 'providers.{}'.format(provider_class)

        query = {
            '_id': SITE_SINGLETON_ID,
            provider_key: None
        }

        now = datetime.datetime.now()
        update = {
            '$set': {
                provider_key: default_provider_id,
                'modified': now
            },
            '$setOnInsert': {
                'center_gears': None,
                'created': now
            }
        }

        # Set the provider singleton, if not set
        dbutil.try_update_one(self.db, 'singletons', query, update, upsert=True)

    def get(self):
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

        return models.SiteSettings.from_dict(doc)

