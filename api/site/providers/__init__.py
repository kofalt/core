"""Provides provider base-classes"""
# Import concrete provider classes for registration
from .base import BaseProvider
from .static_compute_provider import StaticComputeProvider

from .factory import create_provider

# Import repository functions directly
from .repository import (get_provider, get_provider_config,
    get_providers, insert_provider, update_provider, is_compute_dispatcher,
    validate_provider_updates, get_provider_id_for_container,
    get_compute_provider_id_for_job)
