"""Provides data mapper for providers"""
import dateutil.parser
import bson

from flywheel_common.providers import create_provider, ProviderClass
from ... import config

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
        # pylint: disable=W0212
        provider._id = result.inserted_id
        # And return the resulting id
        return result.inserted_id

    def patch(self, provider_id, provider):
        """Update the provider, with the given update fields in the object.

        The modified time will be set automatically.

        Args:
            provider_id (str|ObjectId): The id of the provider to update
            provider (Provider): The set of updates to apply
        """
        # Create the upsert document
        raw = self._parse_raw(provider)
        del raw['_id']
        update = {'$set': raw}
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
        provider.origin = doc['origin']
        provider.modified = doc['modified']
        provider.created = doc['created']

        provider.validate()

        return provider

    def _parse_raw(self, provider):

        """ Parse out the unneeded field for the provider to raw doc mapping """
        # pylint: disable=W0212
        raw = provider._schema.dump(provider).data

        # Pymongo expects the datatime to be valid datetime object to format the type correctly
        raw['created'] = dateutil.parser.parse(raw['created'])
        raw['modified'] = dateutil.parser.parse(raw['modified'])
        del raw['provider_id']

        return raw
