from ..auth import require_login

from .. import config, validators
from ..web import base
from ..web.errors import InputValidationException

from .data_view import DataView
from .column_aliases import ColumnAliases

log = config.log

class DataViewHandler(base.RequestHandler):

    """Provide /views API routes."""

    @require_login
    def get_columns(self):
        """Return all known column aliases with description and type"""
        return ColumnAliases.get_columns()

    @require_login
    def execute_adhoc(self):
        """Execute the data view specified in body"""
        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'data-view-adhoc.json', 'input', 'POST')

        # Find destination container and validate permissions 
        container_id = self.request.GET.get('containerId')
        data_format = self.request.GET.get('format', 'json')

        if not container_id:
            raise InputValidationException('containerId is required!')

        # Create the initial view
        view = DataView(payload)

        # Prepare by searching for container_id and checking permissions
        view.prepare(container_id, data_format, self.uid)

        def response_handler(environ, start_response): # pylint: disable=unused-argument
            write = start_response('200 OK', [
                ('Content-Type', view.get_content_type()),
                ('Content-Disposition', 'attachment; filename="{}"'.format(view.get_filename('view-data'))),
                ('Connection', 'keep-alive')
            ])

            view.execute(self.request, self.origin, write)

            return ''


        return response_handler 




