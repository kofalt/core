from ...web import base
from ...auth import require_admin, require_login
from ... import validators

from ..mappers import SiteSettingsMapper

class SiteSettingsHandler(base.RequestHandler):
    """Handler for admin editable site-wide configuration"""

    @require_login
    def get(self):
        """Return site settings"""
        mapper = SiteSettingsMapper()
        settings = mapper.find()
        return settings.to_dict() if settings else {}

    @require_admin
    @validators.verify_payload_exists
    def put(self):
        """Patch site setting values"""
        # Validate
        payload = self.request.json
        validators.validate_data(payload, 'site-settings.json', 'input', 'PUT')

        # Update/upsert
        mapper = SiteSettingsMapper()
        mapper.patch(payload)
