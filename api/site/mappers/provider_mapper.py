"""Provides data mapper for providers"""
import datetime

import bson

from ... import config
from ..models import Provider, ProviderClass

class ProviderMapper(object):
    """Data mapper for providers"""
    def __init__(self, db=None):
        self.db = db or config.db
        self.dbc = self.db.providers

    def insert(self, provider):
        """Insert a new provider.

        Args:
            provider (Provider): The provider to insert

        Returns:
            ObjectId: The inserted provider id
        """
        result = self.dbc.insert_one(provider.to_dict())
        # Update the instance id
        provider.provider_id = result.inserted_id
        # And return the resulting id
        return result.inserted_id

    def patch(self, provider_id, doc):
        """Update the provider, with the given update fields in doc.

        The modified time will be set automatically.

        Args:
            provider_id (str|ObjectId): The id of the provider to update
            doc (dict): The set of updates to apply
        """
        # Create the upsert document
        update = { '$set': doc }
        update['$set']['modified'] = datetime.datetime.now()
        self.dbc.update_one({'_id': bson.ObjectId(provider_id)}, update)

    def find(self, provider_id):
        """Find the provider that matches the given id.

        Args:
            provider_id (str|ObjectId): The id of the provider to find

        Returns:
            Provider: The loaded provider or None
        """
        result = self.dbc.find_one({'_id': bson.ObjectId(provider_id)})
        return self._load_provider(result)

    def find_by_class(self, provider_class):
        """Find all providers of the given class.

        Args:
            provider_class (str|ProviderClass) The provider class

        Yields:
            Provider: The next provider matching the given class
        """
        if isinstance(provider_class, ProviderClass):
            provider_class = provider_class.value
        return self._find_all({'provider_class': provider_class})

    def _find_all(self, query, **kwargs):
        """Find all providers matching the given query.

        Args:
            query (dict): The query structure
            **kwargs: Additional args to pass to the find function

        Yields:
            Provider: The next provider matching the query
        """
        for doc in self.dbc.find(query, **kwargs):
            yield self._load_provider(doc)

    def _load_provider(self, doc):
        """Loads a single item from a mongo dictionary"""
        if doc is None:
            return None

        return Provider.from_dict(doc)
