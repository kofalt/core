import bson
import datetime
import json
import os
import uuid
import fs.errors

from .auth import require_privilege, Privilege
from flywheel_common import storage
from .web import base
from .web.errors import FileFormException
from . import config
from . import files
from . import placer as pl
from . import util
from .dao import hierarchy
from .site.storage_provider_service import StorageProviderService

Strategy = util.Enum('Strategy', {
    'targeted'       : pl.TargetedPlacer,       # Upload 1 files to a container.
    'targeted_multi' : pl.TargetedMultiPlacer,  # Upload N files to a container.
    'engine'         : pl.EnginePlacer,         # Upload N files from the result of a successful job.
    'token'          : pl.TokenPlacer,          # Upload N files to a saved folder based on a token.
    'packfile'       : pl.PackfilePlacer,       # Upload N files as a new packfile to a container.
    'label'          : pl.LabelPlacer,
    'uid'            : pl.UIDPlacer,
    'uidmatch'       : pl.UIDMatchPlacer,
    'reaper'         : pl.UIDReaperPlacer,
    'analysis'       : pl.AnalysisPlacer,       # Upload N files to an analysis as input and output (no db updates - deprecated)
    'analysis_job'   : pl.AnalysisJobPlacer,    # Upload N files to an analysis as output from job results
    'gear'           : pl.GearPlacer
})


def process_upload(request, strategy, access_logger, container_type=None, id_=None, origin=None, context=None, response=None,
                   metadata=None, file_fields=None, tempdir=None):
    """
    Universal file upload entrypoint.

    Format:
        Multipart form upload with N file fields, each with their desired filename.
        For technical reasons, no form field names can be repeated. Instead, use (file1, file2) and so forth.

        Depending on the type of upload, a non-file form field called "metadata" may/must also be sent.
        If present, it is expected to be a JSON string matching the schema for the upload strategy.

        Currently, the JSON returned may vary by strategy.

        Some examples:
        curl -F file1=@science.png   -F file2=@rules.png url
        curl -F metadata=<stuff.json -F file=@data.zip   url
        http --form POST url metadata=@stuff.json file@data.zip

    Features:
                                               | targeted |  reaper   | engine | packfile
        Must specify a target container        |     X    |           |    X   |
        May create hierarchy on demand         |          |     X     |        |     X

        May  send metadata about the files     |     X    |     X     |    X   |     X
        MUST send metadata about the files     |          |     X     |        |     X

        Creates a packfile from uploaded files |          |           |        |     X
    """
    log = request.logger

    if not isinstance(strategy, Strategy):
        raise Exception('Unknown upload strategy')

    if id_ is not None and container_type == None:
        raise Exception('Unspecified container type')

    allowed_container_types = ('project', 'subject', 'session', 'acquisition',
                               'gear', 'analysis',
                               'collection')
    if container_type is not None and container_type not in allowed_container_types:
        raise Exception('Unknown container type')

    timestamp = datetime.datetime.utcnow()

    container = None
    if container_type and id_:
        container = hierarchy.get_container(container_type, id_)

    # Check if filename should be basename or full path
    filename_path = request.GET.get('filename_path', '').lower() in ('1', 'true')
    if filename_path:
        name_fn = util.sanitize_path
    else:
        name_fn = os.path.basename

    # Gear uploads come in as user origin but we need to be sure they end up in the site storage provider
    force_site_provider = False
    if container_type == 'gear':
        force_site_provider = True

    # The vast majority of this function's wall-clock time is spent here.
    storage_service = StorageProviderService()
    final_storage = storage_service.determine_provider(origin, container, force_site_provider=force_site_provider)
    if not file_fields:
        file_processor = files.FileProcessor(final_storage)
        # The only time we need the tempdir_name is when we use token and packfile.
        form = file_processor.process_form(request, use_filepath=filename_path, tempdir_name=tempdir)

        # Non-file form fields may have an empty string as filename, check for 'falsy' values
        file_fields = extract_file_fields(form)

        if 'metadata' in form:
            try:
                metadata = json.loads(form['metadata'].value)
            except Exception:
                raise FileFormException('wrong format for field "metadata"')
            if isinstance(metadata, dict):
                for f in metadata.get(container_type, {}).get('files', []):
                    f['name'] = name_fn(f['name'])
            elif isinstance(metadata, list):
                for f in metadata:
                    f['name'] = name_fn(f['name'])

    placer_class = strategy.value
    placer = placer_class(container_type, container, id_, metadata, timestamp, origin, context, access_logger, logger=log)

    placer.check()

    # Browsers, when sending a multipart upload, will send files with field name "file" (if sinuglar)
    # or "file1", "file2", etc (if multiple). Following this convention is probably a good idea.
    # Here, we accept any

    # TODO: Change schemas to enabled targeted uploads of more than one file.
    # Ref docs from placer.TargetedPlacer for details.
    if strategy == Strategy.targeted and len(file_fields) > 1:
        raise FileFormException("Targeted uploads can only send one file")

    for field in file_fields:
        if hasattr(field, 'file'):
            field.file.close()
            field.hash = storage.format_hash(files.DEFAULT_HASH_ALG, field.hasher.hexdigest())

        if not hasattr(field, 'hash'):
            field.hash = ''
        # Augment the cgi.FieldStorage with a variety of custom fields.
        # Not the best practice. Open to improvements.
        # These are presumbed to be required by every function later called with field as a parameter.

        #We can trust the filepath on upload is accurate after form processing
        if hasattr(field, 'filepath'):
            #Some placers need this value. Consistent object would be nice
            field.path = field.filepath

        if tempdir:
            # We have to manually clean up anything left in temp_storage
            temp_storage = storage_service.get_local_storage()
            field.size = (temp_storage.storage_plugin.get_file_info(None, field.filepath))['filesize']
        else:
            field.size = (final_storage.storage_plugin.get_file_info(field.uuid, util.path_from_uuid(field.uuid)))['filesize']
            field.provider_id = final_storage.provider_id

        field.mimetype = util.guess_mimetype(field.filename)  # TODO: does not honor metadata's mime type if any
        field.modified = timestamp

        # create a file-attribute map commonly used elsewhere in the codebase.
        # Stands in for a dedicated object... for now.
        field.provider_id = final_storage.provider_id
        file_attrs = make_file_attrs(field, origin)

        placer.process_file_field(file_attrs)

    # Respond either with Server-Sent Events or a standard json map
    if placer.sse and not response:
        raise Exception("Programmer error: response required")
    elif placer.sse:

        # Returning a callable will bypass webapp2 processing and allow
        # full control over the response.
        def sse_handler(environ, start_response): # pylint: disable=unused-argument
            write = start_response('200 OK', [
                ('Content-Type', 'text/event-stream; charset=utf-8'),
                ('Connection', 'keep-alive')
            ])

            # Instead of handing the iterator off to response.app_iter, send it ourselves.
            # This prevents disconnections from leaving the API in a partially-complete state.
            #
            # Timing out between events or throwing an exception will result in undefinied behaviour.
            # Right now, in our environment:
            # - Timeouts may result in nginx-created 500 Bad Gateway HTML being added to the response.
            # - Exceptions add some error json to the response, which is not SSE-sanitized.

            for item in placer.finalize():
                try:
                    write(item)
                except Exception: # pylint: disable=broad-except
                    log.info('SSE upload progress failed to send; continuing')

            return ''

        return sse_handler
    else:
        return placer.finalize()


class Upload(base.RequestHandler):

    def _create_upload_ticket(self, container=None):
        payload = self.request.json_body
        metadata = payload.get('metadata', None)
        filenames = payload.get('filenames', None)

        if metadata is None or not filenames:
            self.abort(400, 'metadata and at least one filename are required')

        storage_service = StorageProviderService()
        final_storage = storage_service.determine_provider(self.origin, container)

        if not final_storage.storage_plugin.is_signed_url():
            return None


        signed_urls = {}
        filedata = []
        for filename in filenames:
            new_uuid = str(uuid.uuid4())
            signed_url = final_storage.storage_plugin.get_signed_url(new_uuid, util.path_from_uuid(new_uuid), purpose='upload')
            signed_urls[filename] = signed_url
            filedata.append({
                'filename': filename,
                'url': signed_url,
                'uuid': new_uuid,
                'filepath': util.path_from_uuid(new_uuid),
                'provider_id': final_storage.provider_id
            })
        ticket = util.upload_ticket(self.request.client_addr, self.origin, None, filedata, metadata)

        return {'ticket': config.db.uploads.insert_one(ticket).inserted_id,
                'urls': signed_urls}

    def _check_upload_ticket(self, ticket_id):
        ticket = config.db.uploads.find_one({'_id': ticket_id})
        if not ticket:
            self.abort(404, 'no such ticket')
        if ticket['ip'] != self.request.client_addr:
            self.abort(403, 'ticket not for this resource or source IP')
        return ticket

    @require_privilege(Privilege.is_drone)
    def upload(self, strategy):
        """Receive a sortable reaper upload only from devices."""

        if strategy in ['label', 'uid', 'uid-match', 'reaper']:
            strategy = strategy.replace('-', '')
            strategy = getattr(Strategy, strategy)

        context = {'uid': None}

        # Request for upload ticket
        if self.get_param('ticket') == '':
            return self._create_upload_ticket(None)

        # Check ticket id and skip permissions check if it clears
        ticket_id = self.get_param('ticket')
        if ticket_id:
            ticket = self._check_upload_ticket(ticket_id)
            file_fields = [util.dotdict(file_field) for file_field in ticket['filedata']]
            # In this case we saved the files to the uuid location they are assigned on signed url storage
            return process_upload(self.request, strategy, self.log_user_access, metadata=ticket['metadata'], origin=self.origin,
                                  context=context, file_fields=file_fields,
                                  tempdir=None)
        else:
            # In this case we are going to save the files to direct locations from the reqeust post.
            return process_upload(self.request, strategy, self.log_user_access, origin=self.origin, context=context)

    def engine(self):
        """Handles file uploads from the engine"""

        if not self.user_is_admin:
            self.abort(402, 'uploads must be from an authorized drone')
        level = self.get_param('level')
        if level is None:
            self.abort(400, 'container level is required')
        if level not in ['analysis', 'acquisition', 'session', 'subject', 'project']:
            self.abort(400, 'container level must be analysis, acquisition, session, subject or project.')
        cid = self.get_param('id')
        if not cid:
            self.abort(400, 'container id is required')
        else:
            cid = bson.ObjectId(cid)

        context = {
            'job_id': self.get_param('job'),
            'job_ticket_id': self.get_param('job_ticket'),
        }

        # Request for upload ticket will validate we have a provider before we do the actual upload
        if self.get_param('upload_ticket') == '':
            container = hierarchy.get_container(level, cid)
            return self._create_upload_ticket(container)


        # Check ticket id and skip permissions check if it clears
        ticket_id = self.get_param('upload_ticket')
        if ticket_id:
            ticket = self._check_upload_ticket(ticket_id)
            file_fields = [util.dotdict(file_field) for file_field in ticket['filedata']]

            strategy = Strategy.analysis_job if level == 'analysis' else Strategy.engine
            return process_upload(self.request, strategy, self.log_user_access, metadata=ticket['metadata'], origin=self.origin,
                                  context=context, file_fields=file_fields, tempdir=ticket['tempdir'],
                                  container_type=level, id_=cid)

        else:
            strategy = Strategy.analysis_job if level == 'analysis' else Strategy.engine
            return process_upload(self.request, strategy, self.log_user_access, container_type=level, id_=cid,
                                  origin=self.origin, context=context)

    def clean_packfile_tokens(self):
        """Clean up expired upload tokens and invalid token directories.
        Ref placer.TokenPlacer and FileListHandler.packfile_start for context.
        """

        if not self.user_is_admin:
            self.abort(402, 'uploads must be from an authorized drone')

        # Race condition: we could delete tokens & directories that are currently processing.
        # For this reason, the modified timeout is long.

        result = config.db['tokens'].find({
            'type': 'packfile',
            'modified': {'$lt': datetime.datetime.utcnow() - datetime.timedelta(hours=1)},
        })
        tokens_removed = 0
        dirs_cleaned = 0

        storage_service = StorageProviderService()
        # We have to manually remove files when finished
        temp_storage = storage_service.get_local_storage()

        for token in result:
            # the token id is the folder.
            try:
                temp_storage.storage_plugin.get_fs().removetree(token['_id'])
                dirs_cleaned += 1
            except fs.errors.ResourceNotFound:
                pass
            except IOError:
                self.log.error('Error removing token directory %s', token['_id'])
                continue

            #We remove the token last so the tokens will always map to current directories
            result = config.db['tokens'].delete_one({
                '_id': token['_id']
            })
            tokens_removed += 1

        if tokens_removed > 0:
            self.log.info('Removed %s expired packfile tokens', tokens_removed)

        # Because we only create directories after we issue a token and we remove directories
        # before we delete the token directories should always map to the current tokens in the DB.

        return {
            'removed': {
                'tokens': tokens_removed,
                'directories': dirs_cleaned,
            }
        }

def extract_file_fields(form):
    """Returns a list of file fields in the form, handling multiple values"""
    result = []
    for fieldname in form:
        field = form[fieldname]
        if isinstance(field, list):
            for field_entry in field:
                if field_entry.filename:
                    result.append(field_entry)

        elif field.filename:
            result.append(field)

    return result

def make_file_attrs(field, origin):
    # create a file-attribute map commonly used elsewhere in the codebase.
    # Stands in for a dedicated object... for now.

    # Not all placers need the path attribute and if they are using UUID it can be inferred
    # Once this get strandardized into a model class we can clean up the specifics
    path = None
    if hasattr(field, 'path'):
        path = field.path

    file_attrs = {
        '_id': field.uuid,
        'provider_id': field.provider_id,
        'name': field.filename,
        'created': getattr(field, 'created', field.modified),
        'modified': field.modified,
        'size': field.size,
        'mimetype': field.mimetype,
        'hash': field.hash,
        'origin': origin,

        'path': path,
        'type': None,
        'modality': None,
        'classification': {},
        'tags': [],
        'info': {}
    }

    file_attrs['type'] = files.guess_type_from_filename(file_attrs['name'])
    return file_attrs
