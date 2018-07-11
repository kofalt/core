from ..auth import require_login

from .. import config, validators
from ..auth import containerauth
from ..dao import noop
from ..web import base
from ..web.errors import APIStorageException, InputValidationException

from .data_view import DataView
from .storage import DataViewStorage
from .column_aliases import ColumnAliases

log = config.log

class DataViewHandler(base.RequestHandler):
    """Provide /views API routes."""
    storage = DataViewStorage()
    parent_projection = {'permissions':1, 'public':1}

    @require_login
    def get_columns(self):
        """Return all known column aliases with description and type"""
        return ColumnAliases.get_columns()

    def list_views(self, parent):
        """List all views belonging to the parent container"""
        # Permission check is different here
        # If the parent container is public or the user has ro (or better) permission on parent, then we can list all data views
        # Otherwise, we can only list public data views
        public_only = True
        parent_container = self.storage.find_parent_by_id(parent, projection=self.parent_projection)

        if containerauth.has_any_referer_access(self, 'GET', {}, parent_container):
            public_only = False

        return self.storage.get_data_views(parent, public_only=public_only)

    @validators.verify_payload_exists
    def post(self, parent):
        """Create a new view on the parent container"""
        parent_container = self.storage.find_parent_by_id(parent, projection=self.parent_projection)
        self.permcheck('POST', parent_container=parent_container)
        
        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'data-view-new.json', 'input', 'POST')

        # Validate columns
        DataView(payload).validate_config()

        # Create
        result = self.storage.create_el(payload, parent)
        if result.acknowledged:
            return {'_id': result.inserted_id}
        else:
            self.abort(404, 'View {} not inserted'.format(result.inserted_id))

    def delete(self, _id):
        """Delete the view identified by _id"""
        parent_container = self.storage.get_parent(_id, projection=self.parent_projection)
        self.permcheck('DELETE', parent_container=parent_container)

        try:
            result = self.storage.delete_el(_id)
        except APIStorageException as e:
            self.abort(400, e.message)

        if result.deleted_count == 1:
            return {'deleted': result.deleted_count}

        self.abort(404, 'Data view {} not deleted'.format(_id))

    def get(self, _id):
        """Get the view identified by _id"""
        cont = self.storage.get_el(_id)
        parent_container = self.storage.get_parent(_id, cont=cont, projection=self.parent_projection)
        self.permcheck('GET', container=cont, parent_container=parent_container)

        return cont

    @validators.verify_payload_exists
    def put(self, _id):
        """Update the view identified by _id"""
        parent_container = self.storage.get_parent(_id, projection=self.parent_projection)
        self.permcheck('PUT', parent_container=parent_container)
        
        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'data-view-update.json', 'input', 'POST')

        result = self.storage.update_el(_id, payload)

        if result.modified_count == 1:
            return {'modified': result.modified_count}
        self.abort(404, 'Data view {} not updated'.format(_id))

    def execute_saved(self, _id):
        """Execute the data view specified by id"""
        cont = self.storage.get_el(_id)
        parent_container = self.storage.get_parent(_id, cont=cont, projection=self.parent_projection)
        self.permcheck('GET', container=cont, parent_container=parent_container)

        return self.do_execute_view(cont)

    @require_login
    @validators.verify_payload_exists
    def execute_adhoc(self):
        """Execute the data view specified in body"""
        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'data-view-adhoc.json', 'input', 'POST')

        return self.do_execute_view(payload)

    def do_execute_view(self, view_spec):
        """ Complete view execution for the given view definition """
        # Find destination container and validate permissions 
        container_id = self.request.GET.get('containerId')
        data_format = self.request.GET.get('format', 'json')

        if not container_id:
            raise InputValidationException('containerId is required!')

        # Create the initial view
        view = DataView(view_spec)

        # Validate the view columns
        view.validate_config()

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

    def permcheck(self, method, container=None, parent_container=None):
        """Perform permission check for data view storage operations
        
        Arguments:
            container (dict): The optional data view
            parent_container (dict,str): The parent container, one of "site", user, group or container
        """
        if container is None:
            container = {}
        permchecker = containerauth.any_referer(self, container=container, parent_container=parent_container)
        permchecker(noop)(method)

