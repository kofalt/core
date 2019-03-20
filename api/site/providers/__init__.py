"""Provides provider base-classes"""
# Import concrete provider classes for registration
from .base import BaseProvider

# You must explicitly define the provider classes here so that 
# they are registered In the PROVIDERS array
from .gc_compute_provider import GCComputeProvider
from .static_compute_provider import StaticComputeProvider
from .local_storage_provider import LocalStorageProvider
from .aws_storage_provider import AWSStorageProvider

from .factory import create_provider

# Import repository functions directly
from .repository import (get_provider, get_provider_config, validate_provider_class,
    get_provider_instance, get_providers, insert_provider, update_provider, is_compute_dispatcher,
    validate_provider_updates, get_provider_id_for_container,
    get_compute_provider_id_for_job)
