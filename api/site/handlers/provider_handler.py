"""API Handlers for providers"""
from ... import validators
from ...web import base, errors
from ...auth import require_admin, require_login, require_drone

from ..models import Provider
from ..providers import (get_provider, get_provider_config,
    get_providers, insert_provider, update_provider,
    is_compute_dispatcher)


class ProviderHandler(base.RequestHandler):
    """Provides endpoints for Providers.

    Provider configuration is protected information,
    and MUST only be exposed in the case that an
    authorized compute dispatcher instance requests it.
    It is a Security Vulnerability to expose config in ANY
    other scenario.

    This should be handled by the domain layer in all cases.
    """
    @require_login
    def get_all(self):
        """List all providers, optionally of the given class"""
        provider_class = self.get_param('class')

        results = []
        for provider in get_providers(provider_class=provider_class):
            results.append(provider.to_dict())

        return results

    @require_login
    def get(self, _id):
        provider = get_provider(_id)
        return provider.to_dict()

    @require_drone
    def get_config(self, _id):
        # Extra authorization: Ensure that device type is a dispatcher
        if not is_compute_dispatcher(self.device.get('type')):
            raise errors.APIPermissionException()
        return get_provider_config(_id)

    @require_admin
    @validators.verify_payload_exists
    def post(self):
        # Creating a new new provider
        payload = self.request.json
        validators.validate_data(payload, 'provider.json', 'input', 'POST')

        provider = Provider(payload['provider_class'], payload['provider_type'],
            payload['label'], self.origin, payload['config'])

        provider_id = insert_provider(provider)
        return {'_id': provider_id}

    @require_admin
    @validators.verify_payload_exists
    def put(self, _id):
        payload = self.request.json
        validators.validate_data(payload, 'provider-update.json', 'input', 'POST')

        update_provider(_id, payload)
