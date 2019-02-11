"""Provides the StaticComputeProvider class"""
from ...web import errors
from .compute_provider import ComputeProvider
from .factory import ProviderKey
from ..models import ProviderClass

class StaticComputeProvider(ComputeProvider):
    """The static compute provider object."""

    # Must set provider_key as (provider_class, provider_type)
    provider_key = ProviderKey(ProviderClass.compute, 'static')

    def validate_config(self):
        # Only empty configuration is valid
        if self.config:
            raise errors.APIValidationException('Static Compute should have NO configuration!')
