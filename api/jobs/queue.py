"""
A simple FIFO queue for jobs.
"""

import bson
import copy
import pymongo
import datetime

from pprint import pformat

from .. import config
from .jobs import Job, Logs, JobTicket
from .gears import get_gear, validate_gear_config, fill_gear_default_values
from ..dao.containerutil import (
    create_filereference_from_dictionary, create_containerreference_from_dictionary,
    create_containerreference_from_filereference, FileReference, pluralize
)
from .job_util import resolve_context_inputs
from ..web import errors
from flywheel_common import errors as flywheel_errors
from ..site import providers


log = config.log

JOB_STATES = [
    'pending',  # Job is queued
    'running',  # Job has been handed to an engine and is being processed
    'failed',   # Job has an expired heartbeat (orphaned) or has suffered an error
    'complete', # Job has successfully completed
    'cancelled' # Job has been cancelled (via a bulk job cancellation)
]

# SHADOW: Perimeter JOB_STATES_ALLOWED_MUTATE
# Changes to this constant SHOULD be avoided, however if changes are unavoidable
# then update the corresponding constant above.
JOB_STATES_ALLOWED_MUTATE = [
    'pending',
    'running',
]

JOB_TRANSITIONS = [
    'pending --> running',
    'pending --> cancelled',
    'running --> cancelled',
    'running --> failed',
    'running --> complete',
]

# How many times a job should be retried
def max_attempts():
    return config.get_item('queue', 'max_retries')

# Should a job be retried when explicitly failed.
# Does not affect orphaned jobs.
def retry_on_explicit_fail():
    return config.get_item('queue', 'retry_on_fail')

def valid_transition(from_state, to_state):
    return (from_state + ' --> ' + to_state) in JOB_TRANSITIONS or from_state == to_state

def add_related_containers(dest, container):
    """Add container and parents to dest set"""
    dest.add(str(container['_id']))
    for _, v in  container.get('parents', {}).iteritems():
        dest.add(str(v))

class Queue(object):

    @staticmethod
    def mutate(job, mutation):
        """
        Validate and save a job mutation

        SHADOW: Perimeter HeartbeatJob, for empty mutations only

        Fundamental changes to the signature or functionality of this function SHOULD be avoided.
        If changes are unavoidable, then update the corresponding function above.
        """

        if job.state not in JOB_STATES_ALLOWED_MUTATE:
            raise errors.InputValidationException('Cannot mutate a job that is ' + job.state + '.')

        # TODO: This should use InputValidationException or similar
        if 'state' in mutation and not valid_transition(job.state, mutation['state']):
            raise Exception('Mutating job from ' + job.state + ' to ' + mutation['state'] + ' not allowed.')

        now = datetime.datetime.utcnow()

        # Special case: when starting a job, actually start it. Should not be called this way.
        if 'state' in mutation:
            if mutation['state'] == 'running':

                # !!!
                # !!! DUPE WITH Queue.run_jobs_with_query
                # !!!

                mutation['request'] = job.generate_request(get_gear(job.gear_id))
            elif mutation['state'] in ('complete', 'failed', 'cancelled') and job.state == 'running':
                if job.transitions and 'running' in job.transitions:
                    mutation['profile.total_time_ms'] = int((now - job.transitions['running']).total_seconds() * 1000)

            # Set transition timestamp
            mutation['transitions.{}'.format(mutation['state'])] = now
            log.info('Transitioning job %s from %s to %s', job.id_, job.state, mutation['state'])

        # Any modification must be a timestamp update
        mutation['modified'] = now

        # Create an object with all the fields that must not have changed concurrently.
        job_query =  {
            '_id': bson.ObjectId(job.id_),
            'state': job.state,
        }

        result = config.db.jobs.update_one(job_query, {'$set': mutation})
        if result.modified_count != 1:
            raise Exception('Job modification not saved')

        # If the job did not succeed, check to see if job should be retried.
        if 'state' in mutation and mutation['state'] == 'failed' and retry_on_explicit_fail():
            job.state = 'failed'
            Queue.retry(job)

    @staticmethod
    def retry(job, force=False, only_failed=True):
        """
        Given a failed job, either retry the job or fail it permanently, based on the attempt number.
        Can override the attempt limit by passing force=True.
        """

        if job.attempt >= max_attempts() and not force:
            log.info('Permanently failed job %s (after %d attempts)', job.id_, job.attempt)
            return

        if job.state in ['cancelled', 'complete']:
            if only_failed:
                raise errors.InputValidationException('Can only retry a job that is failed, please use only_failed parameter')
        elif job.state != 'failed':
            raise errors.InputValidationException('Can not retry running or pending job')


        if job.request is None:
            raise Exception('Cannot retry a job without a request')

        # Race condition: jobs should only be marked as failed once a new job has been spawned for it (if any).
        # No transactions in our database, so we can't do that.
        # Instead, make a best-hope attempt.
        check = config.db.jobs.find_one({'previous_job_id': job.id_ })
        if check is not None:
            found = Job.load(check)
            raise Exception('Job ' + job.id_ + ' has already been retried as ' + str(found.id_))

        new_job_map = job.map()
        new_job_map['config'] = new_job_map['config']['config']
        new_job = Queue.enqueue_job(new_job_map, dict(job.origin))
        new_job.previous_job_id = job.id_
        new_job.attempt += 1
        new_job.request = copy.deepcopy(job.request)
        new_job.id_ = bson.ObjectId()

        # update input uris that reference the old job id
        for i in new_job.request['inputs']+new_job.request['outputs']:
            i['uri'] = i['uri'].replace(str(job.id_), str(new_job.id_))

        if new_job.destination.type == 'analysis':
            config.db.analyses.update_one({'_id': bson.ObjectId(new_job.destination.id)},
                                          {'$set': {'job': str(new_job.id_),
                                                    'modified': new_job.created}})

        result = config.db.jobs.update_one({"_id": bson.ObjectId(job.id_)}, {'$set': {"retried": new_job.created}})
        if result.modified_count != 1:
            log.error('Could not set retried time for job {}'.format(job.id_))

        new_id = new_job.insert(ignore_insertion_block=True)
        log.info('respawned job %s as %s (attempt %d)', job.id_, new_id, new_job.attempt)

        # If job is part of batch job run, update batch jobs list
        batch = config.db.batch.find_one({'jobs': job.id_})
        if batch:
            batch['jobs'].remove(job.id_)
            batch['jobs'].append(new_id)
            config.db.batch.update_one(
                {'jobs': job.id_},
                {'$set': {'jobs': batch['jobs']}}
            )
            log.info('updated batch job list, replacing {} with {}'.format(job.id_, new_id))

        return new_id

    @staticmethod
    def enqueue_job(job_map, origin, perm_check_uid=None):
        """
        Using a payload for a proposed job, creates and returns (but does not insert)
        a Job object. This preperation includes:
          - confirms gear exists
          - validates config against gear manifest
          - creating file reference objects for inputs
            - if given a perm_check_uid, method will check if user has proper access to inputs
          - confirming inputs exist
          - creating container reference object for destination
          - preparing file contexts
          - job api key generation, if requested

        """

        # gear and config manifest check
        gear_id = job_map.get('gear_id')
        if not gear_id:
            raise errors.InputValidationException('Job must specify gear')

        gear = get_gear(gear_id)

        # Invalid disables a gear from running entirely.
        # https://github.com/flywheel-io/gears/tree/master/spec#reserved-custom-keys
        if gear.get('gear', {}).get('custom', {}).get('flywheel', {}).get('invalid', False):
            raise errors.InputValidationException('Gear marked as invalid, will not run!')

        config_ = job_map.get('config', {})
        validate_gear_config(gear, config_)

        # Translate maps to FileReferences
        inputs = {}
        for x in job_map.get('inputs', {}).keys():

            # Ensure input is in gear manifest
            if x not in gear['gear']['inputs']:
                raise errors.InputValidationException('Job input {} is not listed in gear manifest'.format(x))

            input_map = job_map['inputs'][x]

            if gear['gear']['inputs'][x]['base'] == 'file':
                try:
                    inputs[x] = create_filereference_from_dictionary(input_map)
                except KeyError:
                    raise errors.InputValidationException('Input {} does not have a properly formatted file reference.'.format(x))
            else:
                inputs[x] = input_map

        # Add job tags, config, attempt number, and/or previous job ID, if present
        tags            = job_map.get('tags', [])
        attempt         = job_map.get('attempt', 1)
        previous_job_id = job_map.get('previous_job_id', None)
        batch           = job_map.get('batch', None) # A batch id if this job is part of a batch run
        label           = job_map.get('label', "")

        # Add destination container, or select one
        destination = None
        if job_map.get('destination', None) is not None:
            destination = create_containerreference_from_dictionary(job_map['destination'])
        else:
            destination = None
            for key in inputs.keys():
                if isinstance(inputs[key], FileReference):
                    destination = create_containerreference_from_filereference(inputs[key])
                    break

            if not destination:
                raise errors.InputValidationException('Must specify destination if gear has no inputs.')
            elif destination.type == 'analysis':
                raise errors.InputValidationException('Cannot use analysis for destination of a job, container was inferred.')

        # Get parents from destination, also checks that destination exists
        destination_container = destination.get()

        # Permission check
        if perm_check_uid:
            for x in inputs:
                if hasattr(inputs[x], 'check_access'):
                    inputs[x].check_access(perm_check_uid, 'ro')
            destination.check_access(perm_check_uid, 'rw', cont=destination_container)

        # Config options are stored on the job object under the "config" key
        config_ = {
            'config': fill_gear_default_values(gear, config_),
            'inputs': { },
            'destination': {
                'type': destination.type,
                'id': destination.id,
            }
        }

        # Implementation notes: with regard to sending the gear file information, we have two options:
        #
        # 1) Send the file object as it existed when you enqueued the job
        # 2) Send the file object as it existed when the job was started
        #
        # Option #2 is possibly more convenient - it's more up to date - but the only file modifications after a job is enqueued would be from
        #
        # A) a gear finishing, and updating the file object
        # B) a user editing the file object
        #
        # You can count on neither occurring before a job starts, because the queue is not globally FIFO.
        # So option #2 is potentially more convenient, but unintuitive and prone to user confusion.

        input_file_count = 0
        input_file_size_bytes = 0

        related_containers = set()
        add_related_containers(related_containers, destination_container)

        file_inputs = []

        for x in inputs:
            input_type = gear['gear']['inputs'][x]['base']
            if input_type == 'file':

                input_container = inputs[x].get()
                add_related_containers(related_containers, input_container)
                obj = inputs[x].get_file(container=input_container)
                file_inputs.append(obj)
                cr = create_containerreference_from_filereference(inputs[x])

                # Whitelist file fields passed to gear to those that are scientific-relevant
                whitelisted_keys = ['info', 'tags', 'measurements', 'classification', 'mimetype', 'type', 'modality', 'size']
                obj_projection = { key: obj.get(key) for key in whitelisted_keys }

                input_file_count += 1
                input_file_size_bytes += obj.get('size', 0)

                ###
                # recreate `measurements` list on object
                # Can be removed when `classification` key has been adopted everywhere

                if not obj_projection.get('measurements', None):
                    obj_projection['measurements'] = []
                if obj_projection.get('classification'):
                    for v in obj_projection['classification'].itervalues():
                        obj_projection['measurements'].extend(v)
                #
                ###

                config_['inputs'][x] = {
                    'base': 'file',
                    'hierarchy': cr.__dict__,
                    'location': {
                        'name': obj['name'],
                        'path': '/flywheel/v0/input/' + x + '/' + obj['name'],
                    },
                    'object': obj_projection,
                }
            elif input_type == 'context':
                config_['inputs'][x] = inputs[x]
            else:
                # Note: API key inputs should not be passed as input
                raise Exception('Non-file input base type')

        # Populate any context inputs for the gear
        resolve_context_inputs(config_, gear, destination.type, destination.id, perm_check_uid)

        # Populate parents (including destination)
        parents = destination_container.get('parents', {})
        parents[destination.type] = bson.ObjectId(destination.id)

        # Determine compute provider, if not provided
        compute_provider_id = job_map.get('compute_provider_id')
        if compute_provider_id is None:
            compute_provider_id = providers.get_compute_provider_id_for_job(gear, destination_container, file_inputs)
            # If compute provider is still undetermined, then we need to raise
            if compute_provider_id is None:
                raise errors.APIPreconditionFailed('Cannot determine compute provider for job. '
                    'gear={}, destination.id={}'.format(gear['_id'], destination.id))
        else:
            # Validate the provided compute provider
            try:
                providers.validate_provider_class(compute_provider_id, 'compute')
            except flywheel_errors.ResourceNotFound:
                raise flywheel_errors.ValidationError('Provider id is not valid')

        # Initialize profile
        profile = {
            'total_input_files': input_file_count,
            'total_input_size_bytes': input_file_size_bytes
        }

        release_version = config.get_release_version()
        if release_version:
            profile['versions'] = { 'core': release_version }

        gear_name = gear['gear']['name']

        if gear_name not in tags:
            tags.append(gear_name)

        job = Job(gear, inputs, destination=destination, tags=tags, config_=config_, attempt=attempt,
            previous_job_id=previous_job_id, origin=origin, batch=batch, parents=parents, profile=profile,
            related_container_ids=list(related_containers), label=label, compute_provider_id=compute_provider_id)

        return job

    @staticmethod
    def ask(query):
        """
        Ask the queue a question. This can result in starting jobs, statistics, or both.

        {
            "whitelist": {
                "group": [],
                "gear-name": [],
                "tag": [],
                "compute-provider": [],
            },
            "blacklist": {
                "group": [],
                "gear-name": [],
                "tag": [],
                "compute-provider": [],
            },
            "capabilities": [],
            "return": {
                "jobs": int,
                "peek": true,
                "states": true,
            }
        }

        {
            "jobs": [],
            "states": {},
        }
        """

        peek  = query['return'].get('peek',   False)
        jobs  = query['return'].get('jobs',   0)
        stats = query['return'].get('states', False)

        result = {}

        if jobs <= 0 and not stats:
            raise errors.APIValidationException('Not asking for work or stats')

        if jobs > 0:
            result['jobs'] = Queue.start_jobs(jobs, query['whitelist'], query['blacklist'], query['capabilities'], peek)
        if stats:
            result['states'] = Queue.job_states(query['whitelist'], query['blacklist'], query['capabilities'])

        return result

    @staticmethod
    def lists_to_query(whitelist, blacklist, capabilities):
        """
        Translate a whitelist and blacklist to job database query.
        """

        match = {
            'group': {},
            'gear-name': {},
            'tag': {},
            "compute-provider": {},
            'created-by': {},
        }

        # Fill out the request
        for xlist in [whitelist, blacklist]:
            # Mongo operator
            modifier = '$in' if xlist is whitelist else '$nin'

            for key in ['group', 'gear-name', 'tag', 'created-by']:
                if xlist.get(key):
                    match[key][modifier] = xlist[key]

            if xlist.get('compute-provider'):
                match['compute-provider'][modifier] = [bson.ObjectId(provider) for provider in xlist['compute-provider']]


        query = {}

        # Translate to mongo keys
        if match['group']:
            query['parents.group'] = match['group']
        if match['gear-name']:
            query['gear_info.name'] = match['gear-name']
        if match['tag']:
            query['tags'] = match['tag']
        if match['compute-provider']:
            query['compute_provider_id'] = match['compute-provider']
        if match['created-by']:
            query['origin.id'] = match['created-by']

        # Bit unintuitive: match documents that do NOT, have an ELEMENT, that is NOT, in the capabilities.
        # Or, translated:  match documents whose capabilities are a subset of the query.
        query['gear_info.capabilities'] = {
            '$not': {
                '$elemMatch': {
                    '$nin': capabilities
                }
            }
        }

        log.debug('Job query is: %s', pformat(query))
        return query

    @staticmethod
    def start_jobs(max_jobs, whitelist, blacklist, capabilities, peek):
        """
        Atomically change up to N jobs from pending to running.

        Will return empty array if there are no jobs to offer. Searches for jobs in FIFO order.
        """

        query = Queue.lists_to_query(whitelist, blacklist, capabilities)
        return Queue.run_jobs_with_query(max_jobs, query, peek)

    @staticmethod
    def job_states(whitelist, blacklist, capabilities):
        """
        Return job state count for a given set of parameters.

        SHADOW: Perimeter JobStates

        Fundamental changes to the signature or functionality of this function SHOULD be avoided.
        If changes are unavoidable, then update the corresponding function above.
        """

        query = Queue.lists_to_query(whitelist, blacklist, capabilities)

        # Pipeline aggregation
        result = list(config.db.jobs.aggregate([
            {'$match': query },
            {'$group': {
                '_id': '$state',
                'count': {'$sum': 1}}
            }
        ]))

        # Map the mongo result to something useful
        by_state = {s: 0 for s in JOB_STATES}
        by_state.update({r['_id']: r['count'] for r in result})

        return by_state

    @staticmethod
    def run_jobs_with_query(max_jobs, query, peek=False):
        """
        Given a database query, transitions up to N jobs from pending to running.

        Will return empty array if there are no jobs to offer. Searches for jobs in FIFO order.
        """

        if max_jobs > 1:
            raise errors.InputValidationException('Starting multiple jobs not supported')
        if max_jobs < 1:
            raise errors.InputValidationException('Must start at least one job')
        if peek and max_jobs > 1:
            raise errors.InputValidationException('Cannot peek more than one job')

        query['state'] = 'pending'

        now = datetime.datetime.utcnow()
        modification = { '$set': {
            'state': 'running',
            'transitions.running': now,
            'modified': now
        }}

        if peek:
            # placeholder noop
            modification = {'$setOnInsert': {'1': 1}}

        # Search ordering by FIFO
        result = config.db.jobs.find_one_and_update(
            query,
            modification,
            sort=[('modified', 1)],
            return_document=pymongo.collection.ReturnDocument.AFTER
        )

        if result is None:
            return []

        job = Job.load(result)

        if peek:
            gear = get_gear(job.gear_id)
            for key in gear['gear']['inputs']:
                if gear['gear']['inputs'][key] == 'api-key':
                    # API-key gears cannot be peeked
                    return []

        # Return if there is a job request already
        if job.request is not None:
            log.info('Job %s already has a request, so not generating', job.id_)
            return [job]

        # Create a new request formula
        # !!!
        # !!! DUPE WITH Queue.mutate
        # !!!
        gear = get_gear(job.gear_id)
        request = job.generate_request(gear)

        if peek:
            job.request = request
            return [job]

        # Save and return
        result = config.db.jobs.find_one_and_update(
            {
                '_id': bson.ObjectId(job.id_)
            },
            { '$set': {
                'request': request }
            },
            return_document=pymongo.collection.ReturnDocument.AFTER
        )

        if result is None:
            raise Exception('Marked job as running but could not generate and save formula')

        Logs.add_system_logs(job.id_, 'Gear Name: {}, Gear Version: {}\n'.format(gear['gear']['name'], gear['gear']['version']))
        log.info('Starting Job {}. Gear Name: {}, Gear Version: {}'.format(job.id_, gear['gear']['name'], gear['gear']['version']))

        return [Job.load(result)]

    @staticmethod
    def search_containers(containers, states=None, tags=None, limit=100, skip=0, user_id=None):
        """
        Search the queue for jobs that mention at least one of a set of containers and (optionally) match some set of states or tags.

        @param containers: an array of ContainerRefs
        @param states: an array of strings
        @param tags: an array of strings
        @param limit: Limit on search.
        @param skip: number of records to skip. This is a sorted query so skips on large collections will be slow.  Caution!
        @param user_id: Filters jobs to only readable input projects for this user
        """

        conts_by_type = {}
        for cont in containers:
            conts_by_type.setdefault(cont.type, []).append(cont)

        filters = []
        for cont_type, containers in conts_by_type.iteritems():
            filters.extend([
                {'inputs.id': {'$in': [cont.id for cont in containers]}, 'inputs.type': cont_type},
                {'destination.id': {'$in': [cont.id for cont in containers]}, 'destination.type': cont_type},
            ])
        query = {'$or': filters}

        if states is not None and len(states) > 0:
            query['state'] = {"$in": states}

        if tags is not None and len(tags) > 0:
            query['tags'] = {"$in": tags}

        # For now, mandate reverse-crono sort
        jobs = config.db.jobs.aggregate([
            {'$match': query},
            {'$sort': {'modified': pymongo.DESCENDING}},
            {'$skip': skip},
            {'$limit': limit},
        ])

        if user_id is None:
            return jobs


        # Filter bad inputs
        inputs_to_check = {
            'project': set(),
            'subject': set(),
            'session': set(),
            'acquisition': set()
        }

        jobs = list(jobs)

        for j in jobs:
            for i in j['inputs']:
                inputs_to_check[i['type']].add(bson.ObjectId(i['id']))

        bad_inputs = set()
        for type_, inputs in inputs_to_check.iteritems():
            for bad_input in config.db[pluralize(type_)].find({
                    '_id': {'$in': list(inputs)},
                    'permissions': {'$not': {'$elemMatch': {'_id' : user_id}}}
                }, {'_id':1}):

                bad_inputs.add(str(bad_input['_id']))

        for job in jobs:
            tmp_inputs = []
            for i in job['inputs']:
                if i['id'] in bad_inputs:
                    # The config inputs stores the details for the input
                    del job['config']['inputs'][i['input']]
                else:
                    tmp_inputs.append(i)
            job['inputs'] = tmp_inputs
        return jobs

    @staticmethod
    def scan_for_orphans():
        """
        Scan the queue for orphaned jobs, mark them as failed, and possibly retry them.
        Should be called periodically.
        """

        orphaned = 0
        ticketed_jobs = []


        # When the backend is busy / crashing / being upgraded, heartbeats can take a very long time or fail.
        # The default engine heartbeats every 30 seconds. Be careful when lowering this interval.

        query = {
            'state': 'running',
            'modified': {'$lt': datetime.datetime.utcnow() - datetime.timedelta(seconds=300)},
            '_id': { '$nin': ticketed_jobs },
        }

        while True:
            orphan_candidate = config.db.jobs.find_one(query)
            if orphan_candidate is None:
                break

            # If the job is currently attempting to complete, do not orphan.
            ticket = JobTicket.find(orphan_candidate['_id'])
            if ticket is not None and len(ticket) > 0:
                ticketed_jobs.append(orphan_candidate['_id'])
                continue

            # CAS this job, since it does not have a ticket
            select = { '_id': orphan_candidate['_id'] }

            doc = config.db.jobs.find_one_and_update(
                dict(query, **select),
                {
                    '$set': {
                        'state': 'failed', },
                },
                return_document=pymongo.collection.ReturnDocument.AFTER
            )

            if doc is None:
                log.info('Job %s was heartbeat during a ticket lookup and thus not orhpaned', orphan_candidate['_id'])
            else:
                orphaned += 1
                j = Job.load(doc)
                Logs.add_system_logs(j.id_, 'The job did not report in for a long time and was canceled. ')
                new_id = Queue.retry(j)
                Logs.add_system_logs(j.id_, 'Retried job as ' + str(new_id) if new_id else 'Job retries exceeded maximum allowed')

        return orphaned

    #
    # Legacy calls, to be removed later
    #

    @staticmethod
    def legacy_tag_parse(tags=None):
        """
        Translates the old tag  format to the newer whitelist / blacklist format.

        Older job methods used a '!' prefix to denote exclusive (blacklisted) tags.
        """

        if tags is None:
            tags = []

        inclusive_tags = filter(lambda x: not x.startswith('!'), tags)
        exclusive_tags =  map(lambda x: x[1:], filter(lambda x: x.startswith('!'), tags)) # strip the '!' prefix

        whitelist = { }
        blacklist = { }

        if len(inclusive_tags) > 0:
            whitelist['tag'] = inclusive_tags
        if len(exclusive_tags) > 0:
            blacklist['tag'] = exclusive_tags

        return whitelist, blacklist

    @staticmethod
    def start_job_parsing_tags(tags=None, peek=False):
        """
        Calls start_jobs with only 1 job, parsing the old, !-prefixed variant of tag blacklisting.
        Will return None if there are no jobs to offer. Searches for jobs in FIFO order.
        """

        whitelist, blacklist = Queue.legacy_tag_parse(tags)
        capabilities = []

        result = Queue.start_jobs(1, whitelist, blacklist, capabilities, peek)

        if len(result) == 0:
            return None
        elif len(result) != 1:
            raise Exception('Expected start_jobs with max_jobs 1 to return 0 or 1 jobs')
        else:
            return result[0]

    @staticmethod
    def get_statistics(tags=None, last=None, unique=False, all_flag=False):
        """
        Return a variety of interesting information about the job queue.
        """

        if all_flag:
            unique = True
            if last is None:
                last = 3

        whitelist, blacklist = Queue.legacy_tag_parse(tags)
        capabilities = []

        results = { }
        results['states'] = Queue.job_states(whitelist, blacklist, capabilities)

        # List unique tags
        if unique:
            results['unique'] = sorted(config.db.jobs.distinct('tags'))

        # List recently modified jobs for each state
        if last is not None:
            results['recent'] = {s: config.db.jobs.find({
                '$and': [
                    Queue.lists_to_query(whitelist, blacklist, capabilities),
                    {'state': s}
                ]
                }, {
                    'modified':1
                }).sort([('modified', pymongo.DESCENDING)]).limit(last) for s in JOB_STATES}

        return results
