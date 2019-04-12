"""Provides the StaticComputeProvider class"""
from flywheel_common.providers import ProviderClass

from ...web import errors
from .base import BaseProvider
from .factory import ProviderKey

class StaticComputeProvider(BaseProvider):
    """The static compute provider object."""

    def validate_config(self):
        # Only empty configuration is valid
        if self.config:
            raise errors.APIValidationException('Static Compute should have NO configuration!')

    def get_redacted_config(self):
        # There is no configuration, always return empty
        return {}
