import json

from ..auth import require_admin, require_login
from ..web import encoder
from ..web import base
from .. import config
from .. import validators

class Config(base.RequestHandler):

    def get(self):
        """Return public Scitran configuration information."""
        return config.get_public_config()

    def get_js(self):
        """Return scitran config in javascript format."""
        self.response.write(
            'config = ' +
            json.dumps( self.get(), sort_keys=True, indent=4, separators=(',', ': '), default=encoder.custom_json_serializer,) +
            ';'
        )

class Version(base.RequestHandler):

    def get(self):
        """Return database schema version"""
        resp = config.get_version()
        if resp != None:
            return resp
        else:
            self.abort(404, "Version document does not exist")

class SiteSettingsHandler(base.RequestHandler):
    """Handler for admin editable site-wide configuration"""

    @require_login
    def get(self):
        """Return site settings"""
        return config.db.singletons.find_one({'_id': 'site'}, {'_id': 0}) or {}

    @require_admin
    @validators.verify_payload_exists
    def put(self):
        """Patch site setting values"""
        # Validate
        payload = self.request.json
        validators.validate_data(payload, 'site-settings.json', 'input', 'PUT')

        # Update/upsert
        result = config.db.singletons.update_one({'_id': 'site'}, {'$set': payload}, upsert=True)

        return {'modified': result.modified_count}
