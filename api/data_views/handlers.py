from ..auth import require_privilege, Privilege

from .. import config, validators
from ..auth import containerauth
from ..dao import noop
from ..dao.containerstorage import ContainerStorage
from ..web import base, encoder
from ..web.errors import APIStorageException, InputValidationException

from ..files import FileProcessor
from .. import upload
from ..placer import TargetedMultiPlacer
import datetime

from .data_view import DataView
from .storage import DataViewStorage
from .column_aliases import ColumnAliases

log = config.log

# TODO: Update when subjects are real
FILE_CONTAINERS = { 'project', 'session', 'acquisition' }

class DataViewHandler(base.RequestHandler):
    """Provide /views API routes."""
    storage = DataViewStorage()
    parent_projection = {'permissions':1, 'public':1}

    @require_privilege(Privilege.is_user)
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

    @require_privilege(Privilege.is_user)
    @validators.verify_payload_exists
    def execute_and_save(self):
        """Execute the data view specified, and save the results as a file"""

        # Validate payload
        payload = self.request.json
        validators.validate_data(payload, 'save-data-view.json', 'input', 'POST')

        # Ensure that exactly one is set
        if (not payload.get('view') and not payload.get('viewId')) or (payload.get('view') and payload.get('viewId')):
            raise InputValidationException('Must specify one of "view" object or "viewId"')

        # Verify target container type
        if payload['containerType'] not in FILE_CONTAINERS:
            raise InputValidationException('Must one of "{}" for containerType'.format(', '.join(FILE_CONTAINERS)))

        # Verify that the view exists
        if payload.get('viewId'):
            view_id = payload['viewId']
            view = self.storage.get_el(view_id)
            parent_container = self.storage.get_parent(view_id, cont=view, projection=self.parent_projection)
            self.permcheck('GET', container=view, parent_container=parent_container)
        else:
            view = payload.get('view')

        # Verify that the destination container exists and user can post
        storage = ContainerStorage.factory(payload['containerType'])
        target = storage.get_el(payload['containerId'])

        if not self.user_is_admin:
            permchecker = containerauth.default_container(self, target_parent_container=target)
            permchecker(noop)('POST')

        # Execute the data view
        return self.do_execute_view(view, target, payload['containerType'], payload['filename'])

    @require_privilege(Privilege.is_user)
    @validators.verify_payload_exists
    def execute_adhoc(self):
        """Execute the data view specified in body"""
        # Validate payload
        payload = self.request.json

        validators.validate_data(payload, 'data-view-adhoc.json', 'input', 'POST')

        return self.do_execute_view(payload)

    def do_execute_view(self, view_spec, target_container=None, target_container_type=None, target_filename=None):
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
        view.prepare(container_id, data_format, self.uid, pagination=self.pagination, report_progress=bool(target_container))

        def response_handler(environ, start_response): # pylint: disable=unused-argument
            write_progress=None

            if target_container:

                # Saved directly to persistent storage.
                file_processor = FileProcessor(config.primary_storage)

                # If we're saving to container, start SSE event,
                # and write the data to a temp file
                write_progress = start_response('200 OK', [
                    ('Content-Type', 'text/event-stream; charset=utf-8'),
                    ('Connection', 'keep-alive')
                ])

                # Create a new file with a new uuid
                path, fileobj = file_processor.create_new_file(None)
                new_uuid = fileobj.filename
                if target_filename:
                    fileobj.filename = target_filename
                write = fileobj.write

                # Construct the file metadata list
                metadata = []
                metadata.append({'name': fileobj.filename})
                timestamp = datetime.datetime.utcnow()

            else:
                write = start_response('200 OK', [
                    ('Content-Type', view.get_content_type()),
                    ('Content-Disposition', 'attachment; filename="{}"'.format(view.get_filename('view-data'))),
                    ('Connection', 'keep-alive')
                ])

            view.execute(self.request, self.origin, write, write_progress_fn=write_progress)

            if target_container:
                # Process file calcs but close the file first to flush the buffer
                fileobj.close()

                # Create our targeted placer
                placer = TargetedMultiPlacer(target_container_type, target_container, target_container['_id'],
                    metadata, timestamp, self.origin, {'uid': self.uid}, self.log_user_access)

                file_fields = file_processor.create_file_fields(
                    fileobj.filename,
                    path,
                    config.primary_storage.get_file_info(new_uuid, path)['filesize'],
                    config.primary_storage.get_file_hash(new_uuid, path),
                    uuid_=new_uuid,
                    mimetype=None,
                    modified=timestamp
                )

                file_attrs = upload.make_file_attrs(file_fields, self.origin)

                # Place the file
                placer.process_file_field(file_attrs)
                result = placer.finalize()

                # Write final progress
                progress = encoder.json_sse_pack({
                    'event': 'result',
                    'data': result,
                })
                write_progress(progress)

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
