"""Provides data mapper for providers"""
import datetime

import bson
import pymongo

from flywheel_common.providers import create_provider, ProviderClass
from ... import config
from .. import models

class Providers(object):
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

        raw = self._parse_raw(provider)
        # It should be empty anyway
        del raw['_id']

        result = self.dbc.insert_one(raw)
        # Update the instance id
        provider.provider_id = result.inserted_id
        provider._id = result.inserted_id
        # And return the resulting id
        return result.inserted_id

    def patch(self, provider_id, provider):
        """Update the provider, with the given update fields in the doc.

        The modified time will be set automatically.

        Args:
            provider_id (str|ObjectId): The id of the provider to update
            doc (dict): The set of updates to apply
        """
        # Create the upsert document
        raw = self._parse_raw(provider)
        raw['label'] = provider.provider_label
        del raw['_id']
        update = {'$set': raw}
        update['$set']['modified'] = datetime.datetime.now()
        self.dbc.update_one({'_id': bson.ObjectId(provider_id)}, update)

    def get(self, provider_id):
        """Get the provider that matches the given id.

        Args:
            provider_id (str|ObjectId): The id of the provider to find

        Returns:
            Provider: The loaded provider or None
        """
        result = self.dbc.find_one({'_id': bson.ObjectId(provider_id)})
        return self._load_provider(result)

    def find_all(self, provider_class=None):
        """Find all providers of the given class.

        Args:
            provider_class (str|ProviderClass) The provider class, or None for all classes

        Yields:
            Provider: The next provider matching the given class
        """
        if provider_class:
            if isinstance(provider_class, ProviderClass):
                provider_class = provider_class.value
            query = {'provider_class': provider_class}
        else:
            query = {}
        return self._find_all(query)

    def get_or_create_site_provider(self, provider):
        """Upsert a site provider for the given class.

        Args:
            provider (Provider): The provider to upsert

        Returns:
            ObjectId: The provider id
        """
        cls = provider.provider_class.value

        doc = provider.to_dict()
        doc['_site'] = cls

        result = self.dbc.find_one_and_update({'_site': cls}, {'$setOnInsert': doc}, upsert=True,
                projection={'_id':1}, return_document=pymongo.collection.ReturnDocument.AFTER)
        return result['_id']

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

        # Remove site key
        doc.pop('_site', None)

        provider = create_provider(
            class_=doc['provider_class'],
            type_=doc['provider_type'],
            label=doc['label'],
            config=doc['config'],
            creds=doc.get('creds'), #Creds is not required in local or gc currently,
            id_=doc['_id'])
        return provider

    def _parse_raw(self, provider):

        """ Parse out the unneeded field for the provider to raw doc mapping """
        raw = provider._schema.dump(provider).data
        raw['label'] = provider.provider_label

        del raw['provider_label']
        del raw['provider_id']
        return raw
