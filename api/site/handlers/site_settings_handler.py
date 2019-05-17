"""Provides handler for site settings endpoint"""
from ...web import base
from ...auth import require_admin, require_login
from ... import validators

from ..site_settings import get_site_settings, update_site_settings


class SiteSettingsHandler(base.RequestHandler):
    """Handler for admin editable site-wide configuration"""

    @require_login
    def get(self):
        """Return site settings"""
        return get_site_settings()

    @require_admin
    @validators.verify_payload_exists
    def put(self):
        """Patch site setting values"""
        # Validate Input
        payload = self.request.json
        validators.validate_data(payload, "site-settings.json", "input", "PUT")

        # Update/upsert
        update_site_settings(payload, self.log)
