"""API Handlers for providers"""
from flywheel_common.providers import create_provider

from ... import validators
from ...web import base
from ...auth import require_admin, require_login
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
            results.append(provider._schema.dump(provider).data)

        return results

    @require_login
    def get(self, _id):
        provider = get_provider(_id)
        return provider._schema.dump(provider).data

    @require_admin
    def get_config(self, _id):
        # Extra authorization: Ensure that device type is a dispatcher, before
        # returning full configuration

        # self.device only exists if this is a device request
        device = getattr(self, 'device', None)
        full = device is not None and is_compute_dispatcher(device.get('type'))
        return get_provider_config(_id, full=full)

    @require_admin
    @validators.verify_payload_exists
    def post(self):
        # Creating a new new provider
        payload = self.request.json
        validators.validate_data(payload, 'provider.json', 'input', 'POST')

        provider = create_provider(
            class_=payload['provider_class'],
            type_=payload['provider_type'],
            label=payload['label'],
            config=payload['config'],
            creds=payload['creds'])
        provider.origin = self.origin

        provider_id = insert_provider(provider)
        return {'_id': provider_id}

    @require_admin
    @validators.verify_payload_exists
    def put(self, _id):
        payload = self.request.json
        validators.validate_data(payload, 'provider-update.json', 'input', 'POST')

        update_provider(_id, payload)
