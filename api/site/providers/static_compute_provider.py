"""Provides the StaticComputeProvider class"""
from ...web import errors
from .base import BaseProvider
from .factory import ProviderKey
from ..models import ProviderClass


class StaticComputeProvider(BaseProvider):
    """The static compute provider object."""

    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(ProviderClass.compute, "static")

    def validate_config(self):
        # Only empty configuration is valid
        if self.config:
            raise errors.APIValidationException("Static Compute should have NO configuration!")

    def get_redacted_config(self):
        # There is no configuration, always return empty
        return {}
