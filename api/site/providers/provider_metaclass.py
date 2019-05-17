"""Provides self-registering metaclass for providers"""
from abc import ABCMeta

from .factory import PROVIDERS


class ProviderMetaclass(ABCMeta):
    """Metaclass that provides automatic registration of providers"""

    def __init__(cls, name, bases, dct):
        # Init Abstract Base Class
        ABCMeta.__init__(cls, name, bases, dct)

        # Register with providers, if registration info is provided
        provider_key = getattr(cls, "provider_key", None)
        if provider_key is not None:
            PROVIDERS[provider_key] = cls
