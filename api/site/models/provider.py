"""Provide the provider class"""
import datetime

from enum import Enum

from ... import models


class ProviderClass(Enum):
    """Enumeration of provider classes"""

    compute = "compute"  # Compute resource provider
    storage = "storage"  # Storage resource provider


class Provider(models.Base):
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
        super(Provider, self).__init__()

        self.created = datetime.datetime.now()
        """datetime: The creation time of this document"""

        self.modified = datetime.datetime.now()
        """datetime: The last modified time of this document"""

        self.provider_class = ProviderClass(provider_class)
        """ProviderClass: The class of provider, either compute or storage"""

        self.provider_type = provider_type
        """str: The type (or host) of the provider. (e.g. static, gcloud, etc)"""

        self.label = label
        """str: The human-readable provider label"""

        self.origin = origin
        """dict: The origin (e.g. user) of the provider"""

        self.config = config
        """dict: The provider-specific configuration"""

    @property
    def provider_id(self):
        """Returns the unique ID of this document"""
        return self.get("_id")

    @provider_id.setter
    def provider_id(self, _id):
        if self.get("_id") is not None:
            raise ValueError("Cannot set _id if it has already been set!")
        self["_id"] = _id

    def to_dict(self):
        """Return the dictionary representation of this object."""
        result = super(Provider, self).to_dict()
        result["provider_class"] = self.provider_class.value
        return result

    @classmethod
    def from_dict(cls, dct):
        result = super(Provider, cls).from_dict(dct)
        # Convert ProviderClass
        result.provider_class = ProviderClass(result.provider_class)
        return result
