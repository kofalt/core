import pytest

from api.web import errors
from api.site.models import ProviderClass
from api.site.providers import create_provider

def test_provider_factory_error():
    # Non-existent storage
    with pytest.raises(ValueError):
        provider = create_provider(ProviderClass.storage, 'garbage', {})

def test_provider_factory_static_compute():
    config = {'key': 'value'}

    # Static compute
    provider = create_provider(ProviderClass.compute, 'static', config)
    assert provider is not None
    assert provider.config == config

    with pytest.raises(errors.APIValidationException):
        provider.validate_config()

    provider.config = {}
    provider.validate_config()  # Only empty config is valid for static
