"""Provides provider base-classes"""
# Import concrete provider classes for registration
from .static_compute_provider import StaticComputeProvider

from .factory import create_provider

# Import repository functions directly
from .repository import (get_provider, get_provider_config,
    get_providers_by_class, insert_provider, update_provider)
