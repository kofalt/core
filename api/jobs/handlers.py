"""
API request handlers for the jobs module
"""
import bson
import datetime
import StringIO
from jsonschema import ValidationError
from urlparse import urlparse

from . import batch
from . import mappers, models
from .job_util import (
    resolve_context_inputs,
    get_context_for_destination,
    remove_potential_phi_from_job,
    validate_job_compute_provider,
    log_job_access
)
from .. import config
from .. import upload
from .. import files
from ..auth import require_drone, require_login, require_admin, has_access
from ..auth.apikeys import JobApiKey
from ..dao import dbutil
from ..dao.containerstorage import ProjectStorage, SessionStorage, SubjectStorage, AcquisitionStorage, AnalysisStorage, cs_factory
from ..types import Origin
from ..util import set_for_download, add_container_type, mongo_dict, send_or_redirect_file
from ..validators import validate_data, verify_payload_exists
from ..dao.containerutil import pluralize, singularize
from ..web import base
from ..web.encoder import pseudo_consistent_json_encode
from flywheel_common.errors import ResourceNotFound
from ..web.errors import APIPermissionException, APINotFoundException, InputValidationException
from ..web.request import log_access, AccessType
from ..site.providers import get_provider

from .gears import (
    validate_gear_config, get_gears, get_gear, get_latest_gear, confirm_registry_asset,
    get_invocation_schema, remove_gear, insert_gear,
    upsert_gear, check_for_gear_insertion, filter_optional_inputs,
    add_suggest_info_to_files, count_file_inputs, requires_read_write_key
)

from .jobs import Job, JobTicket, Logs
from .batch import check_state, update
from .queue import Queue
from .rules import validate_regexes, validate_auto_update, validate_fixed_inputs

log = config.log

class GearsHandler(base.RequestHandler):

    """Provide /gears API routes."""

    @require_login
    def get(self):
        """List all gears."""

        # NOTE Filtering with `?filter=single_input` or `read_only_key` is not compatible with pagination
        # because filtering after the query invalidates total and count.
        # Ignoring any pagination headers/params for backwards compatibility.
        filters = self.request.GET.getall('filter')
        filtered = False

        gears = get_gears(all_versions=self.is_true('all_versions'))
        if 'single_input' in filters:
            filtered = True
            gears = [gear for gear in gears if count_file_inputs(filter_optional_inputs(gear)) <= 1]
        if 'read_only_key' in filters:
            filtered = True
            gears = [gear for gear in gears if not requires_read_write_key(gear)]

        if filtered:
            return gears

        gear_page = get_gears(all_versions=self.is_true('all_versions'), pagination=self.pagination)
        return self.format_page(gear_page)

    @require_login
    def check(self):
        """Check if a gear upload is likely to succeed."""

        check_for_gear_insertion(self.request.json)
        return None

    @require_admin
    def prepare_add(self):
        """
        Declare a gear that will be uploaded to the Flywheel registry
        """

        geardoc = self.request.json

        if geardoc.get('category') is None:
            geardoc['category'] = 'converter'

        check_for_gear_insertion(geardoc)

        ticket = config.db.gear_tickets.insert_one({
            'origin': self.origin,
            'geardoc': geardoc,
            'timestamp': datetime.datetime.utcnow(),
        })

        return {
            'ticket': ticket.inserted_id
        }

    @require_admin
    def get_ticket(self, _id):
        """
        Retrieve a gear-upload ticket.
        """

        result = config.db.gear_tickets.find_one({
            '_id': bson.ObjectId(_id)
        })

        if result is None:
            raise APINotFoundException('Gear ticket with id {} not found.'.format(_id))
        else:
            return result

    @require_admin
    def get_own_tickets(self):
        """
        Retrieve all gear-upload tickets owned by the current origin.
        """

        # Allow for just a summary of gear names
        gear_names_only = self.is_true('gear_names_only')

        result = config.db.gear_tickets.find({
            'origin': self.origin
        })

        # For now, always send a string array to avoid mutating types. Possibly a new endpoint later.
        if gear_names_only or True:
            return list(set(map(lambda(x): x['geardoc']['gear']['name'], result)))
        else:
            return result

    @require_admin
    def save(self): # pragma: no cover
        """
        Save a gear described by an upload ticket.
        """

        submit = self.request.json

        ticket = config.db.gear_tickets.find_one({
            '_id': bson.ObjectId(submit['ticket'])
        })

        if ticket is None:
            raise APINotFoundException('Gear ticket with id {} not found.'.format(submit['ticket']))

        repo    = submit['repo']
        pointer = submit['pointer']

        try:
            manifest, image = confirm_registry_asset(repo, pointer)
        except Exception as err:
            raise InputValidationException(cause=err)

        import json
        self.log.debug(json.dumps(manifest, indent=4, sort_keys=True))
        self.log.debug(json.dumps(image, indent=4, sort_keys=True))

        geardoc = ticket['geardoc']
        now = datetime.datetime.utcnow()
        geardoc['created'] = now
        geardoc['modified'] = now
        geardoc['exchange'] = {
            'rootfs-url': 'docker://' + image
        }
        result = insert_gear(geardoc)

        config.db.gear_tickets.delete_one({
            '_id': bson.ObjectId(submit['ticket'])
        })

        return {
            'gear': result
        }

class GearHandler(base.RequestHandler):
    """Provide /gears/x API routes."""

    @require_login
    def get(self, _id):
        result = get_gear(_id)
        add_container_type(self.request, result)
        return result

    @require_login
    def get_invocation(self, _id):
        return get_invocation_schema(get_gear(_id))

    @require_login
    def suggest(self, _id, cont_name, cid):
        """
        Given a container reference, return display information about parents, children and files
        as well as information about which best match each gear input

        Container types acceptable for reference:
          - Groups
          - Projects
          - Collections
          - Subjects
          - Sessions
          - Acquisitions
          - Analyses

        NOTE: Access via this endpoint is not logged. Only information necessary for display should be returned.
        """

        # Do all actions that could result in a 404 first
        gear = get_gear(_id)
        if not gear:
            raise APINotFoundException('Gear with id {} not found.'.format(_id))

        storage = cs_factory(cont_name)
        container = storage.get_container(cid)
        if cont_name == 'analyses':
            container['permissions'] = storage.get_parent(cid, cont=container).get('permissions', [])
        if not self.user_is_admin and not has_access(self.uid, container, 'ro'):
            raise APIPermissionException('User does not have access to container {}.'.format(cid))

        cont_name = pluralize(cont_name)

        response = {
            'cont_type':    singularize(cont_name),
            '_id':          cid,
            'label':        container.get('label', ''),
            'parents':      [],
            'files':        [],
            'children':     {}
        }

        if cont_name != 'analyses':
            analyses = AnalysisStorage().get_analyses(None, cont_name, cid)
            response['children']['analyses'] = [{'cont_type': 'analysis', '_id': a['_id'], 'label': a.get('label', '')} for a in analyses]

        # Get collection context, if any
        collection_id = self.get_param('collection')
        collection = None
        if collection_id:

            if cont_name in ['projects', 'groups']:
                raise InputValidationException('Cannot suggest for {} with a collection context.'.format(cont_name))
            collection = cs_factory('collections').get_container(collection_id)

        # Get children
        if cont_name == 'collections':
            # Grab subjects within the collection context
            children = SubjectStorage().get_all_el({'collections': collection_id}, None, None)
            response['children']['subjects'] = [{'cont_type': 'subject', '_id': c['_id'], 'label': c.get('label', '')} for c in children]

        elif cont_name not in ['analyses', 'acquisitions']:
            query = {}
            if collection_id:
                query['collections'] = bson.ObjectId(collection_id)
            children = storage.get_children(cid, query=query, projection={'files': 0})
            response['children'][pluralize(storage.child_cont_name)] = [{'cont_type': singularize(storage.child_cont_name), '_id': c['_id'], 'label': c.get('label', '')} for c in children]


        # Get parents
        parents = storage.get_parent_tree(cid, cont=container)
        if collection_id and cont_name != 'collections':
            # Remove project and group, replace with collection
            parents = parents[:-2]
            collection['cont_type'] = 'collection'
            parents.append(collection)

        response['parents'] = [{'cont_type': singularize(p['cont_type']), '_id': p['_id'], 'label': p.get('label', '')} for p in parents]

        _files = add_suggest_info_to_files(gear, container.get('files', []))
        response['files'] = [{'name': f['name'], 'suggested': f['suggested']} for f in _files]

        return response

    @require_login
    def get_context(self, _id, cont_name, cid):
        """
        Given a container reference, return the set of context values that are found,
        along with container type and label.
        """

        # Do all actions that could result in a 404 first
        gear = get_gear(_id)
        if not gear:
            raise APINotFoundException('Gear with id {} not found.'.format(_id))

        storage = cs_factory(cont_name)
        container = storage.get_container(cid)
        if cont_name == 'analyses':
            container['permissions'] = storage.get_parent(cid, cont=container).get('permissions', [])
        if not self.user_is_admin and not has_access(self.uid, container, 'ro'):
            raise APIPermissionException('User does not have access to container {}.'.format(cid))

        # Only check permissions if the user is not admin
        check_uid = None if self.user_is_admin else self.uid
        context = get_context_for_destination(cont_name, cid, check_uid, storage=storage, cont=container)

        result = {}
        for name, inp in gear['gear']['inputs'].iteritems():
            if inp['base'] == 'context':
                if name in context:
                    result[name] = context[name]
                    result[name].update({'found': True})
                else:
                    result[name] = {'found': False}

        return result

    @require_admin
    def upload(self): # pragma: no cover
        r = upload.process_upload(self.request, upload.Strategy.gear, self.log_user_access, container_type='gear', origin=self.origin, metadata=self.request.headers.get('metadata'))
        gear_id = upsert_gear(r[1])

        config.db.gears.update_one({'_id': gear_id}, {'$set': {
            'exchange.rootfs-url': '/api/gears/temp/' + str(gear_id)}
        })

        return {'_id': str(gear_id)}

    def download(self, **kwargs): # pragma: no cover
        """Download gear tarball file"""
        dl_id = kwargs.pop('cid')
        gear = get_gear(dl_id)

        file_id = gear['exchange'].get('rootfs-id')
        provider_id = gear['exchange'].get('rootfs-provider-id')
        provider = get_provider(provider_id)
        file_path = files.get_file_path({'_id': file_id})
        send_or_redirect_file(self, provider, file_id, file_path, 'gear.tar')

    @require_admin
    def post(self, _id):
        payload = self.request.json

        if _id != payload.get('gear', {}).get('name', ''):
            self.abort(400, 'Name key must be present and match URL')

        try:
            result = upsert_gear(payload)
            return { '_id': str(result) }

        except ValidationError as err:
            raise InputValidationException(cause=err)

    @require_admin
    def delete(self, _id):
        return remove_gear(_id)

class RulesHandler(base.RequestHandler):

    def get(self, cid):
        """List rules"""

        projection = None

        if cid == 'site':
            if self.public_request:
                raise APIPermissionException('Viewing site-level rules requires login.')
            projection = {'project_id': 0}
        else:
            project = ProjectStorage().get_container(cid, projection={'permissions': 1})
            if not self.user_is_admin and not has_access(self.uid, project, 'ro'):
                raise APIPermissionException('User does not have access to project {} rules'.format(cid))

        find_kwargs = dict(filter={'project_id': cid}, projection=projection)
        page = dbutil.paginate_find(config.db.project_rules, find_kwargs, self.pagination)
        return self.format_page(page)

    @verify_payload_exists
    def post(self, cid):
        """Add a rule"""

        if cid == 'site':
            if not self.user_is_admin:
                raise APIPermissionException('Adding site-level rules can only be done by a site admin.')
        else:
            project = ProjectStorage().get_container(cid, projection={'permissions': 1})
            if not self.user_is_admin and not has_access(self.uid, project, 'admin'):
                raise APIPermissionException('Adding rules to a project can only be done by a project admin.')

        payload = self.request.json


        validate_data(payload, 'rule-new.json', 'input', 'POST', optional=True)
        validate_regexes(payload)

        gear = get_gear(payload['gear_id'])
        validate_gear_config(gear, payload.get('config'))
        validate_fixed_inputs(gear, payload.get('fixed_inputs'))

        # Check that the rule has at least one rule-item
        if not (payload.get('any') or payload.get('all') or payload.get('not')):
            raise InputValidationException('Cannot create rule without any conditions')

        if requires_read_write_key(get_gear(payload['gear_id'])):
            raise InputValidationException("Cannot create rule with a gear that requires a read-write api-key.")

        # Site rules can't have fixed_inputs
        if payload.get('fixed_inputs') and cid == 'site':
            raise InputValidationException("Cannot create a site rule with a fixed input.")

        if payload.get('auto_update'):
            gear_name = get_gear(payload['gear_id'])['gear']['name']
            gear_id_latest_version = str(get_latest_gear(gear_name)['_id'])

            gear_id = payload.get('gear_id')
            update_gear_is_latest = gear_id == gear_id_latest_version

            rule_config = payload.get('config')

            validate_auto_update(rule_config, gear_id, update_gear_is_latest, True, payload.get('fixed_inputs'))

        # Check and raise if non-admin user attempts to override compute provider
        validate_job_compute_provider(payload, self, validate_provider=True)

        payload['project_id'] = cid
        rule = models.Rule.from_dict(payload)
        rules_mapper = mappers.RulesMapper()

        inserted_id = rules_mapper.insert(rule)
        return { '_id': inserted_id }

class RuleHandler(base.RequestHandler):

    def get(self, cid, rid):
        """Get rule"""
        rules_mapper = mappers.RulesMapper()

        projection = None
        if cid == 'site':
            if self.public_request:
                raise APIPermissionException('Viewing site-level rules requires login.')
            projection = {'project_id': 0}
        else:
            project = ProjectStorage().get_container(cid, projection={'permissions': 1})
            if not self.user_is_admin and not has_access(self.uid, project, 'ro'):
                raise APIPermissionException('User does not have access to project {} rules'.format(cid))

        rule = rules_mapper.get(rid, projection=projection)

        if not rule:
            raise APINotFoundException('Rule not found.')

        return rule


    @verify_payload_exists
    def put(self, cid, rid):
        """Change a rule"""
        rules_mapper = mappers.RulesMapper()

        if cid == 'site':
            if not self.user_is_admin:
                raise APIPermissionException('Modifying site-level rules can only be done by a site admin.')
        else:
            project = ProjectStorage().get_container(cid, projection={'permissions': 1})
            if not self.user_is_admin and not has_access(self.uid, project, 'admin'):
                raise APIPermissionException('Modifying project rules can only be done by a project admin.')

        rule = rules_mapper.get(rid)

        if not rule:
            raise APINotFoundException('Rule not found.')

        updates = self.request.json
        validate_data(updates, 'rule-update.json', 'input', 'POST', optional=True)

        current_auto_update = rule.auto_update
        auto_update = updates.get('auto_update', current_auto_update)


        if auto_update:
            gear_name = get_gear(rule.gear_id)['gear']['name']
            gear_id_latest_version = str(get_latest_gear(gear_name)['_id'])
            update_gear_id = updates.get('gear_id')

            update_gear_is_latest = update_gear_id == gear_id_latest_version
            current_gear_is_latest = rule.gear_id == gear_id_latest_version

            rule_config = updates.get('config')
            rule_fixed_inputs = updates.get('fixed_inputs')

            validate_auto_update(rule_config, update_gear_id, update_gear_is_latest, current_gear_is_latest, rule_fixed_inputs)
            updates['config'] = {}

        validate_regexes(updates)
        gear_id = updates.get('gear_id', rule.gear_id)
        config_ = updates.get('config', rule.config)
        fixed_inputs = updates.get('fixed_inputs', rule.fixed_inputs)
        gear = get_gear(gear_id)
        validate_gear_config(gear, config_)
        validate_fixed_inputs(gear, fixed_inputs)
        if requires_read_write_key(get_gear(gear_id)):
            raise InputValidationException("Rule cannot use a gear that requires a read-write api-key.")

        # Check and raise if non-admin user attempts to override compute provider
        validate_job_compute_provider(updates, self, validate_provider=True)

        rule_updates = models.Rule.from_dict(updates)
        rule.update(rule_updates)
        if not (rule.any_ or rule.all_ or rule.not_):
            raise InputValidationException('Rule must have at least one condition')
        rules_mapper.patch(rid, updates)

    def delete(self, cid, rid):
        """Remove a rule"""
        rules_mapper = mappers.RulesMapper()

        if cid == 'site':
            if not self.user_is_admin:
                raise APIPermissionException('Modifying site-level rules can only be done by a site admin.')
        else:
            project = ProjectStorage().get_container(cid, projection={'permissions': 1})
            if not self.user_is_admin and not has_access(self.uid, project, 'admin'):
                raise APIPermissionException('Modifying project rules can only be done by a project admin.')


        deleted_count = rules_mapper.delete(rid)
        if deleted_count != 1:
            raise APINotFoundException('Rule not found.')

class JobsHandler(base.RequestHandler):

    @require_admin
    def get(self):
        """List all jobs."""
        page = dbutil.paginate_find(config.db.jobs, {}, self.pagination)
        cleaned_results = []
        if page.get('results'):
            for job_map in page.get('results'):
                cleaned_results.append(remove_potential_phi_from_job(job_map))
            page['results'] = cleaned_results

        return self.format_page(page)

    @require_login
    def add(self):
        """Add a job to the queue."""
        payload = self.request.json

        if payload.get('destination') and payload['destination']['type'] == 'analysis':
            raise InputValidationException('Cannot use analysis as destination for a job')

        # Check and raise if non-admin user attempts to override compute provider
        validate_job_compute_provider(payload, self)

        uid = None
        if not self.user_is_admin:
            uid = self.uid

        job = Queue.enqueue_job(payload, self.origin, perm_check_uid=uid)
        job.insert()

        return { '_id': job.id_ }

    @require_login
    def determine_provider(self):
        """Determine the effective provider for a job"""
        payload = self.request.json

        if payload.get('destination') and payload['destination']['type'] == 'analysis':
            raise InputValidationException('Cannot use analysis as destination for a job')

        # Remove any existing provider
        payload.pop('compute_provider_id', None)

        # Raises precondition failed if provider could not be determined
        job = Queue.enqueue_job(payload, self.origin, perm_check_uid=None)

        # Retrieve the provider
        provider = get_provider(job.compute_provider_id)
        return provider._schema.dump(provider).data

    @require_admin
    def stats(self):
        all_flag = self.is_true('all')
        unique = self.is_true('unique')
        tags = self.request.GET.getall('tags')
        last = self.request.GET.get('last')

        # Allow for tags to be specified multiple times, or just comma-deliminated
        if len(tags) == 1:
            tags = tags[0].split(',')

        if last is not None:
            last = int(last)

        return Queue.get_statistics(tags=tags, last=last, unique=unique, all_flag=all_flag)

    @require_admin
    def next(self):
        peek = self.is_true('peek')
        tags = self.request.GET.getall('tags')

        # Allow for tags to be specified multiple times, or just comma-deliminated
        if len(tags) == 1:
            tags = tags[0].split(',')

        job = Queue.start_job_parsing_tags(tags=tags, peek=peek)

        if job is None:
            raise InputValidationException('No jobs to process')
        else:
            return job

    @require_admin
    def ask(self):
        """
        Ask for job work or statistics. An upgrade over next & stats that unifies request format.
        """

        payload = self.request.json
        validate_data(payload, 'job-ask.json', 'input', 'PUT')

        return Queue.ask(payload)

    @require_admin
    def reap_stale(self):
        count = Queue.scan_for_orphans()
        return { 'orphaned': count }

class JobHandler(base.RequestHandler):
    """Provides /Jobs/<jid> routes."""

    @require_admin
    def get(self, _id):
        job = Job.get(_id)
        log_job_access(self, job)
        return job

    @require_login
    def get_detail(self, _id):
        # Get the job instance
        job = Job.get(_id)

        result = job.map()
        result.pop('inputs', {})
        parents = result.pop('parents', {})
        saved_files = result.pop('saved_files', [])

        # Cached lookup for containers, returns None if not found
        _parent_projection = {'label': 1}
        _container_cache = {}
        def get_container(ref):
            """Helper for cached retrieval of container"""
            # Normalize id
            if not ref or not ref.id:
                return None
            strid = str(ref.id)
            if strid in _container_cache:
                result = _container_cache[strid]
            else:
                try:
                    result = ref.get()
                except APINotFoundException:
                    log.debug('Unable to retrieve container: type=%s, id=%s',
                        ref.type, ref.id)
                    result = None

                _container_cache[strid] = result
            return result

        # Read inputs while checking permission
        authorized = self.user_is_admin
        result['inputs'] = {}
        if job.inputs is not None:
            for key, ref in job.inputs.items():
                if not hasattr(ref, 'map'):
                    continue

                rec = {
                    'ref': ref.map()
                }
                result['inputs'][key] = rec

                # Duck-typing, we're only dealing with references from here
                if not hasattr(ref, 'check_access'):
                    continue

                # Retrieve the container
                cont = get_container(ref)
                if cont is None:
                    continue

                if not self.user_is_admin:
                    # Check access, (Raises APIPermissionException)
                    ref.check_access(self.uid, 'ro', cont=cont)
                    authorized = True

                if hasattr(ref, 'get_file'):
                    # Raises APINotFoundException
                    try:
                        rec['object'] = ref.get_file(container=cont)
                        rec['object'].pop('info', None)  # Remove info, if present
                    except APINotFoundException:
                        log.debug('Unable to retrieve file on container: type=%s, id=%s, name=%s',
                            ref.type, ref.id, ref.name)
                else:
                    rec['object'] = cont

        # Log the access of all inputs
        log_job_access(self, job)

        # If we're still not authorized, check the destination
        dest_cont = get_container(job.destination)
        if dest_cont and not self.user_is_admin:
            # Raises APIPermissionException
            job.destination.check_access(self.uid, 'ro', cont=dest_cont)
        elif not authorized:
            # Couldn't find destination container, and cannot check access
            raise APIPermissionException('User {} does not have access to job {}'.format(self.uid, _id))

        # Resolve parent container (labels)
        result['parent_info'] = {}
        for ctype, cid in parents.items():
            if cid is None:
                continue

            # Retrieve (cached if possible) parents
            strid = str(cid)
            cont = _container_cache.get(strid)
            if cont is None:
                storage = cs_factory(ctype)
                cont = storage.get_el(cid, projection=_parent_projection)

            if cont:
                result['parent_info'][ctype] = {
                    '_id': cont['_id'],
                    'label': cont.get('label')
                }
            else:
                result['parent_info'][ctype] = {'_id': cid}

        # Resolve outputs (saved_files)
        result['outputs'] = []
        for name in saved_files:
            rec = {
                'ref': {
                    'name': name
                }
            }

            if job.destination:
                rec['ref']['type'] = job.destination.type
                rec['ref']['id'] = job.destination.id

            if dest_cont:
                obj = job.destination.find_file(name, cont=dest_cont)
                if obj:
                    rec['object'] = obj
                    obj.pop('info', None)  # Remove info, if present

            result['outputs'].append(rec)

        return result


    @require_admin
    def get_config(self, _id):
        """Get a job's config"""
        j = Job.get(_id)
        c = j.config
        if c is None:
            c = {}

        # Detect if config is old- or new-style.
        # TODO: remove this logic with a DB upgrade, ref database.py's reserved upgrade section.

        encoded = None
        if 'config' in c and c.get('inputs') is not None:
            # New behavior

            # API keys are only returned in-flight, when the job is running, and not persisted to the job object.
            if j.state == 'running':
                gear = get_gear(j.gear_id)

                for key in gear['gear']['inputs']:
                    the_input = gear['gear']['inputs'][key]

                    if the_input['base'] == 'api-key':
                        if j.origin['type'] == 'user':
                            uid = j.origin['id']
                            api_key = JobApiKey.generate(uid, j.id_)
                        elif 'auto' in j.tags:
                            project_id = cs_factory(pluralize(j.destination.type)).get_parent_id(j.destination.id, 'project')
                            api_key = JobApiKey.generate(None, j.id_, scope={'level': 'project', 'id': project_id, 'access': 'ro'})
                        else:
                            raise Exception('Cannot provide an API key to a job not launched by a user')

                        url = urlparse(config.get_item('site', 'api_url'))

                        if url.port is None or url.port == 443:
                            api_key = url.hostname + ':' + api_key
                        else:
                            api_key = url.hostname + ':' + str(url.port) + ':' + api_key

                        if c.get('inputs') is None:
                            c['inputs'] = {}

                        c['inputs'][key] = {
                            'base': 'api-key',
                            'key': api_key
                        }

            encoded = pseudo_consistent_json_encode(c)

        else: # Legacy behavior
            encoded = pseudo_consistent_json_encode({"config": c})

        stream = StringIO.StringIO(encoded)
        length = len(encoded.encode('utf-8'))

        set_for_download(self.response, stream=stream, filename='config.json', length=length)

    @require_login
    def put(self, _id):
        """
        Update a job. Updates timestamp.
        Enforces a valid state machine transition, if any.
        Rejects any change to a job that is not currently in 'pending' or 'running' state.
        """
        j = Job.get(_id)
        mutation = self.request.json

        if 'state' in mutation and mutation['state'] == 'running':
            if self.origin.get('type', '') != Origin.device:
                raise APIPermissionException('Only a drone can start a job with this endpoint')

        # If user is not site admin, can only cancel jobs they spawned
        if not self.user_is_admin:
            if j.origin.get('id') != self.uid:
                raise APIPermissionException('User does not have permission to access job {}'.format(_id))
            if mutation != {'state': 'cancelled'}:
                raise APIPermissionException('User can only cancel jobs.')

        Queue.mutate(j, mutation)

        # If the job failed or succeeded, check state of the batch
        if 'state' in mutation and mutation['state'] in ['complete', 'failed']:
            # Remove any API keys for this job
            JobApiKey.remove(_id)
            if j.batch:
                batch_id = j.batch
                new_state = check_state(batch_id)
                if new_state:
                    update(batch_id, {'state': new_state})

    @require_admin
    @verify_payload_exists
    def update_profile(self, _id):
        # Updates job.profile with the given input doc
        payload = self.request.json
        validate_data(payload, 'job-profile-update.json', 'input', 'PUT')

        update_doc = mongo_dict(payload, prefix='profile')
        result = config.db.jobs.update_one({'_id': bson.ObjectId(_id)}, {'$set': update_doc})
        if not result.matched_count:
            raise APINotFoundException('Job {} was not found!'.format(_id))
        return { 'modified': result.modified_count }

    def _log_read_check(self, _id):
        try:
            job = Job.get(_id)
        except Exception: # pylint: disable=broad-except
            self.abort(404, 'Job not found')

        # Permission check
        if not self.user_is_admin:
            if job.inputs is not None:
                for x in job.inputs:
                    if hasattr(job.inputs[x], 'check_access'):
                        job.inputs[x].check_access(self.uid, 'ro')
                # Unlike jobs-add, explicitly not checking write access to destination.

    @log_access(AccessType.view_job_logs)
    def get_logs(self, _id):
        """Get a job's logs"""

        self._log_read_check(_id)
        return Logs.get(_id)

    @log_access(AccessType.view_job_logs)
    def get_logs_text(self, _id):
        """Get a job's logs in raw text"""

        self._log_read_check(_id)
        filename = 'job-' + _id + '-logs.txt'

        set_for_download(self.response, filename=filename)
        for output in Logs.get_text_generator(_id):
            self.response.write(output)

    @log_access(AccessType.view_job_logs)
    def get_logs_html(self, _id):
        """Get a job's logs in html"""

        self._log_read_check(_id)

        for output in Logs.get_html_generator(_id):
            self.response.write(output)

        return

    @require_admin
    def add_logs(self, _id):
        doc = self.request.json

        j = Job.get(_id)
        Queue.mutate(j, {}) # Unconditionally heartbeat

        return Logs.add(_id, doc)

    def retry(self, _id):
        """ Retry a job.

        The job must have a state of 'failed', and must not have already been retried.
        Returns the id of the new, generated job.
        """
        j = Job.get(_id)

        # Permission check
        if not self.user_is_admin:

            if j.inputs is not None:
                for x in j.inputs:
                    if hasattr(j.inputs[x], 'check_access'):
                        j.inputs[x].check_access(self.uid, 'ro')

            j.destination.check_access(self.uid, 'rw')
            if j.destination.type == 'analysis':
                if len(j.destination.get().get('files', [])):
                    raise APIPermissionException('Requires superuser to retry job if analysis has outputs')

        # API key gear permission check
        gear = get_gear(j.gear_id)
        for x in gear['gear'].get('inputs', {}).keys():
            input_ = gear['gear']['inputs'][x]
            if input_.get('base') == 'api-key':
                if not self.user_is_admin and self.uid != j.origin['id']:
                    raise APIPermissionException('Only original scheduler or root user can retry a gear requiring an api key input')

        compute_provider_id = self.get_param('computeProviderId')
        if compute_provider_id:
            # Check and raise if non-admin user attempts to override compute provider
            validate_job_compute_provider({'compute_provider_id': compute_provider_id},
                    self, validate_provider=True)
            j.compute_provider_id = compute_provider_id

        new_id = Queue.retry(j, force=True, only_failed=not self.is_true('ignoreState'))
        return { "_id": new_id }

    @require_drone
    def prepare_complete(self, _id):
        # Create the ticket
        return {
            'ticket': JobTicket.create(_id)
        }

    @require_drone
    def complete(self, _id):
        payload = self.request.json
        success = payload['success']
        failure_reason = payload.get('failure_reason') if not success else None

        update_doc = {
            'state': 'complete' if success else 'failed'
        }

        # Optional failure reason
        if failure_reason:
            update_doc['failure_reason'] = failure_reason

        # Profile updates
        profile = payload.get('profile')
        if profile:
            validate_data(profile, 'job-profile-update.json', 'input', 'POST')
            update_doc.update(mongo_dict(profile, prefix='profile'))

        # Retrieve and update the job
        job = Job.get(_id)
        self.log.info('Update job %s with %s', _id, update_doc)
        Queue.mutate(job, update_doc)

        # Update job logs if there were outputs
        if job.saved_files:
            lines = [ 'The following outputs have been saved:\n' ]
            for name in job.saved_files:
                lines.append('  - {}\n'.format(name))
            Logs.add_system_logs(_id, lines)

        # Finally, remove the ticket
        ticket_id = self.get_param('job_ticket_id')
        if ticket_id:
            JobTicket.remove(ticket_id)

class BatchHandler(base.RequestHandler):

    @require_login
    def get_all(self):
        """
        Get a list of batch jobs user has created.
        Site admins see all batch jobs.
        """

        if self.user_is_admin:
            # Don't enforce permissions for site admin requests or drone requests
            query = {}
        else:
            query = {'origin.id': self.uid}
        page = batch.get_all(query, {'proposal': 0}, pagination=self.pagination)
        return self.format_page(page)

    @require_login
    def get(self, _id):
        """
        Get a batch job by id.
        Use param jobs=true to replace job id list with job objects.
        """

        get_jobs = self.is_true('jobs')
        batch_job = batch.get(_id, projection={'proposal':0}, get_jobs=get_jobs)
        self._check_permission(batch_job)
        return batch_job

    @require_login
    def post(self):
        """
        Create a batch job proposal, insert as 'pending' if there are matched containers
        """

        payload = self.request.json
        gear_id = payload.get('gear_id')
        targets = payload.get('targets')
        config_ = payload.get('config', {})
        analysis_data = payload.get('analysis', {})
        tags = payload.get('tags', [])
        optional_input_policy = payload.get('optional_input_policy')

        # Request might specify a collection context
        collection_id = payload.get('target_context', {}).get('id', None)
        if collection_id:
            collection_id = bson.ObjectId(collection_id)

        # Validate the config against the gear manifest
        if not gear_id or not targets:
            self.abort(400, 'A gear name and list of target containers is required.')
        gear = get_gear(gear_id)
        if gear.get('gear', {}).get('custom', {}).get('flywheel', {}).get('invalid', False):
            self.abort(400, 'Gear marked as invalid, will not run!')
        has_optional_input = any([input_.get('optional', False) for input_ in gear['gear']['inputs'].itervalues()])
        if has_optional_input and optional_input_policy not in ['ignored', 'flexible', 'required']:
            self.abort(400, 'Gear has optional inputs but no policy on optional inputs was given, will not run!')
        validate_gear_config(gear, config_)

        # Ensure that user is admin if compute_provider_id is set
        compute_provider_id = validate_job_compute_provider(payload, self, validate_provider=True)

        container_ids = []
        container_type = None

        # Get list of container ids from target list
        for t in targets:
            if not container_type:
                container_type = t.get('type')
            else:
                # Ensure all targets are of same type, may change in future
                if container_type != t.get('type'):
                    self.abort(400, 'targets must all be of same type.')
            container_ids.append(t.get('id'))

        objectIds = [bson.ObjectId(x) for x in container_ids]

        # Determine if gear is no-input gear
        file_inputs = False
        context_inputs = False
        for input_ in gear['gear'].get('inputs', {}).itervalues():
            if input_['base'] == 'file':
                file_inputs = True
            if input_['base'] == 'context':
                context_inputs = True

        if not file_inputs:
            # Grab sessions rather than acquisitions
            containers = SessionStorage().get_all_for_targets(container_type, objectIds)

        else:
            # Get acquisitions associated with targets
            containers = AcquisitionStorage().get_all_for_targets(container_type, objectIds, collection_id=collection_id)

        if not containers:
            self.abort(404, 'Could not find necessary containers from targets.')

        improper_permissions = []
        perm_checked_conts = []

        # Make sure user has read-write access, add those to acquisition list
        for c in containers:
            if self.user_is_admin or has_access(self.uid, c, 'rw'):
                c.pop('permissions')
                perm_checked_conts.append(c)
            else:
                improper_permissions.append(c['_id'])

        if not perm_checked_conts:
            self.abort(403, 'User does not have write access to targets.')

        # For site admin requests, don't check permissions when building context
        if self.user_is_admin:
            context_uid = None
        else:
            context_uid = self.uid

        if not file_inputs:
            # All containers become matched destinations

            results = {
                'matched': [{'id': str(x['_id']), 'type': 'session'} for x in containers]
            }

        else:
            # Look for file matches in each acquisition
            results = batch.find_matching_conts(gear, perm_checked_conts, 'acquisition',
                                                optional_input_policy, context_inputs=context_inputs,
                                                uid=context_uid)

        matched = results['matched']
        batch_proposal = {}

        # If there are matches, create a batch job object and insert it
        if matched:

            batch_proposal = {
                '_id': bson.ObjectId(),
                'gear_id': gear_id,
                'config': config_,
                'state': 'pending',
                'origin': self.origin,
                'proposal': {
                    'analysis': analysis_data,
                    'tags': tags,
                    'jobs': []
                }
            }

            if not file_inputs:
                # Resolve context inputs for container
                for match in matched:
                    job_map = {
                        'inputs': {},
                        'destination': match
                    }

                    if context_inputs:
                        resolve_context_inputs(job_map, gear, match['type'], match['id'], context_uid)

                    batch_proposal['proposal']['jobs'].append(job_map)
            else:
                # Convert from container + inputs to proposed job
                for match in matched:
                    batch_proposal['proposal']['jobs'].append({
                        'inputs': match.pop('inputs'),
                        'destination': { 'id': str(match['_id']), 'type': 'acquisition' }
                    })

            # Override compute_provider_id if provided
            if compute_provider_id is not None:
                for job_map in batch_proposal['proposal']['jobs']:
                    job_map['compute_provider_id'] = compute_provider_id

            batch.insert(batch_proposal)
            batch_proposal.pop('proposal')

        # Either way, return information about the status of the containers
        if has_optional_input:
            batch_proposal['optional_input_policy'] = optional_input_policy
        batch_proposal['not_matched'] = results.get('not_matched', [])
        batch_proposal['ambiguous'] = results.get('ambiguous', [])
        batch_proposal['matched'] = matched
        batch_proposal['improper_permissions'] = improper_permissions

        return batch_proposal

    @require_login
    def post_with_jobs(self):
        """
        Creates a batch from preconstructed jobs
        """
        payload = self.request.json
        jobs_ = payload.get('jobs', [])

        uid = None
        if not self.user_is_admin:
            uid = self.uid

        batch_id = bson.ObjectId()

        for job_number, job_ in enumerate(jobs_):
            try:
                # Ensure that user is admin if compute_provider_id is set
                validate_job_compute_provider(job_, self)

                job_['batch'] = str(batch_id)
                Queue.enqueue_job(job_, self.origin, perm_check_uid=uid)
            except InputValidationException as e:
                raise InputValidationException("Job {}: {}".format(job_number, str(e)))
            except APIPermissionException as e:
                raise APIPermissionException("Job {}: {}".format(job_number, str(e)))

        batch_proposal = {
            'proposal': {
                'preconstructed_jobs': jobs_
            },
            'origin': self.origin,
            'state': 'pending',
            '_id': batch_id
        }
        batch.insert(batch_proposal)

        return batch_proposal

    @require_login
    def run(self, _id):
        """
        Creates jobs from proposed inputs, returns jobs enqueued.
        Moves 'pending' batch job to 'running'.
        """

        batch_job = batch.get(_id)
        self._check_permission(batch_job)
        if batch_job.get('state') != 'pending':
            self.abort(400, 'Can only run pending batch jobs.')
        return batch.run(batch_job)

    @require_login
    def cancel(self, _id):
        """
        Cancels jobs that are still pending, returns number of jobs cancelled.
        Moves a 'running' batch job to 'cancelled'.
        """

        batch_job = batch.get(_id)
        self._check_permission(batch_job)
        if batch_job.get('state') != 'running':
            self.abort(400, 'Can only cancel started batch jobs.')
        return {'number_cancelled': batch.cancel(batch_job)}

    def _check_permission(self, batch_job):
        if not self.user_is_admin:
            if batch_job['origin'].get('id') != self.uid:
                raise APIPermissionException('User does not have permission to access batch {}'.format(batch_job.get('_id')))
