"""Provide the provider class"""
import copy
import datetime

from enum import Enum


class ProviderClass(Enum):
    """Enumeration of provider classes"""
    compute = 'compute'  # Compute resource provider
    storage = 'storage'  # Storage resource provider


class Provider(object):
    """Represents an abstract service (compute or storage) provider in the database"""
    def __init__(self, provider_class, provider_type, label, origin, config):
        """Create a new provider.

        Args:
            provider_class (ProviderClass): The class of provider
            provider_type (str): The type (or host) of the provider. (e.g. static, gcloud, etc)
            label (str): The human-readable provider label
            origin (dict): The origin (e.g. user) of the provider
            config (dict): The provider-specific configuration
        """
        self._doc = {
            'created': datetime.datetime.now(),
            'modified': datetime.datetime.now(),
            'provider_class': ProviderClass(provider_class),
            'provider_type': provider_type,
            'label': label,
            'origin': origin,
            'config': config
        }

    @property
    def provider_id(self):
        """Returns the unique ID of this document"""
        return self._doc.get('_id')  # ID may not be set if this is a new provider

    @provider_id.setter
    def provider_id(self, _id):
        if self._doc.get('_id') is not None:
            raise ValueError('Cannot set _id if it has already been set!')
        self._doc['_id'] = _id

    @property
    def created(self):
        """Returns the creation time of this document"""
        return self._doc['created']

    @property
    def modified(self):
        """Returns the last modified time of this document"""
        return self._doc['modified']

    @property
    def provider_class(self):
        """Returns the provider class"""
        return self._doc['provider_class']

    @property
    def provider_type(self):
        """Returns the provider type"""
        return self._doc['provider_type']

    @property
    def label(self):
        """Returns the human-readable label"""
        return self._doc['label']

    @property
    def origin(self):
        """Returns the origin"""
        return self._doc['origin']

    @property
    def config(self):
        """Returns the provider configuration"""
        return self._doc.get('config')

    @config.deleter
    def config(self):
        if 'config' in self._doc:
            del self._doc['config']

    def to_dict(self):
        """Return the dictionary representation of this object."""
        result = copy.copy(self._doc)
        result['provider_class'] = self.provider_class.value
        return result

    @classmethod
    def from_dict(cls, doc):
        """Create a Provider from an imported object.

        Args:
            doc (str): The source document.

        Returns:
            Provider: The provider instance
        """
        self = cls.__new__(cls)
        # Convert ProviderClass
        doc['provider_class'] = ProviderClass(doc['provider_class'])
        self._doc = doc  # pylint: disable=protected-access
        return self
