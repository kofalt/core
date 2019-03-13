"""
Batch
"""
import bson
import copy
import datetime

from .. import config
from ..dao import dbutil
from ..dao.containerstorage import AcquisitionStorage, AnalysisStorage
from .jobs import Job
from .queue import Queue
from ..web.errors import APINotFoundException, APIStorageException
from . import gears
from . import job_util

log = config.log

BATCH_JOB_TRANSITIONS = {
    # To  <-------  #From
    'failed':       'running',
    'complete':     'running',
    'running':      'pending',
    'cancelled':    'running'
}


def get_all(query, projection=None, pagination=None):
    """
    Fetch batch objects from the database
    """
    find_kwargs = dict(filter=query, projection=projection)
    page = dbutil.paginate_find(config.db.batch, find_kwargs, pagination)
    return page['results'] if pagination is None else page

def get(batch_id, projection=None, get_jobs=False):
    """
    Fetch batch object by id, include stats and job objects as requested
    """

    if isinstance(batch_id, str):
        batch_id = bson.ObjectId(batch_id)
    batch_job = config.db.batch.find_one({'_id': batch_id}, projection)

    if batch_job is None:
        raise APINotFoundException('Batch job {} not found.'.format(batch_id))

    if get_jobs:
        jobs = []
        for jid in batch_job.get('jobs', []):
            job = Job.get(jid)
            jobs.append(job)
        batch_job['jobs'] = jobs

    return batch_job

def find_matching_conts(gear, containers, container_type, optional_input_policy,
                        context_inputs=False, uid=None):
    """
    Give a gear and a list of containers, find files that:
      - have no solution to the gear's input schema (not matched)
      - have multiple solutions to the gear's input schema (ambiguous)
      - match the gear's input schema 1 to 1 (matched)
    Containers are placed in one of the three categories in order.
    A container with 2 possible files for one input and none for the other
    will be marked as 'not matched', not ambiguous.
    """

    matched_conts = []
    not_matched_conts = []
    ambiguous_conts = []
    context = None

    for c in containers:
        if context_inputs:
            context = job_util.get_context_for_destination(container_type, str(c['_id']), uid)

        files = c.get('files')
        if files:
            suggestions = gears.suggest_for_files(gear, files, context=context)

            # Determine if any of the inputs are ambiguous or not satisfied
            ambiguous = False  # Are any of the inputs ambiguous?
            not_matched = False
            for input_name, files in suggestions.iteritems():
                is_optional_input = gear['gear']['inputs'][input_name].get('optional', False)
                opt_ignore = optional_input_policy == 'ignored' and is_optional_input
                opt_required = optional_input_policy == 'required' or not is_optional_input

                # Skip ambiguity check for this input if the policy is to ignore and the input is optional
                if len(files) > 1 and not opt_ignore:
                    ambiguous = True
                # Skip the not_matched check for this input if the policy is to ignore or to be flexible
                # and the input is an optional input
                elif opt_required and len(files) == 0:
                    not_matched = True
                    break

            # Based on results, add to proper list
            if not_matched:
                not_matched_conts.append(c)
            elif ambiguous:
                ambiguous_conts.append(c)
            else:
                # Create input map of file refs
                inputs = {}
                for input_name, suggested_inputs in suggestions.iteritems():
                    is_optional_input = gear['gear']['inputs'][input_name].get('optional', False)
                    no_suggested_inputs = optional_input_policy == 'ignored' or len(suggested_inputs) == 0

                    if no_suggested_inputs and is_optional_input:
                        continue
                    elif suggested_inputs[0]['base'] == 'file':
                        inputs[input_name] = {'type': container_type, 'id': str(c['_id']), 'name': suggested_inputs[0]['name']}
                    else:
                        inputs[input_name] = suggested_inputs[0]
                c['inputs'] = inputs
                matched_conts.append(c)
        else:
            not_matched_conts.append(c)
    return {
        'matched': matched_conts,
        'not_matched': not_matched_conts,
        'ambiguous': ambiguous_conts
    }

def insert(batch_proposal):
    """
    Simple database insert given a batch proposal.
    """

    time_now = datetime.datetime.utcnow()
    batch_proposal['created'] = time_now
    batch_proposal['modified'] = time_now
    return config.db.batch.insert(batch_proposal)

def update(batch_id, payload):
    """
    Updates a batch job, being mindful of state flow.
    """

    time_now = datetime.datetime.utcnow()
    bid = bson.ObjectId(batch_id)
    query = {'_id': bid}
    payload['modified'] = time_now
    if payload.get('state'):
        # Require that the batch job has the previous state
        query['state'] = BATCH_JOB_TRANSITIONS[payload.get('state')]
    result = config.db.batch.update_one({'_id': bid}, {'$set': payload})
    if result.modified_count != 1:
        raise Exception('Batch job not updated')

def run(batch_job):
    """
    Creates jobs from proposed inputs, returns jobs enqueued.
    """

    proposal = batch_job.get('proposal')
    if not proposal:
        raise APIStorageException('The batch job is not formatted correctly.')

    elif 'jobs' in proposal:
        proposed_jobs = proposal.get('jobs', [])

        gear_id = batch_job['gear_id']
        gear = gears.get_gear(gear_id)
        gear_name = gear['gear']['name']

        config_ = batch_job.get('config')
        origin = batch_job.get('origin')
        tags = proposal.get('tags', [])
        tags.append('batch')

        if gear.get('category') == 'analysis':
            analysis_base = proposal.get('analysis', {})
            if not analysis_base.get('label'):
                time_now = datetime.datetime.utcnow()
                analysis_base['label'] = {'label': '{} {}'.format(gear_name, time_now)}
            an_storage = AnalysisStorage()
            acq_storage = AcquisitionStorage()

        jobs = []
        job_ids = []

        job_defaults = {
            'config':   config_,
            'gear_id':  gear_id,
            'tags':     tags,
            'batch':    str(batch_job.get('_id')),
            'inputs':   {}
        }

        for proposed_job in proposed_jobs:
            job_map = copy.deepcopy(job_defaults)
            if 'inputs' in proposed_job:
                job_map['inputs'] = proposed_job['inputs']

            if 'destination' not in proposed_job:
                raise APIStorageException('Destination is required for all proposed jobs')
            job_map['destination'] = proposed_job['destination']

            if 'compute_provider_id' in proposed_job:
                job_map['compute_provider_id'] = proposed_job['compute_provider_id']

            if gear.get('category') == 'analysis':
                analysis = copy.deepcopy(analysis_base)

                # Create analysis
                # NOTE: Batch destinations *MUST* be a session or acquisition
                if job_map['destination']['type'] == 'acquisition':
                    acquisition_id = job_map['destination']['id']
                    session_id = acq_storage.get_container(acquisition_id, projection={'session': 1}).get('session')
                else:
                    session_id = bson.ObjectId(job_map['destination']['id'])

                analysis['job'] = job_map
                result = an_storage.create_el(analysis, 'sessions', session_id, origin, None)

                analysis = an_storage.get_el(result.inserted_id)
                an_storage.inflate_job_info(analysis)
                job = analysis.get('job')
                job_id = bson.ObjectId(job.id_)

            else:
                job = Queue.enqueue_job(job_map, origin)
                job.insert()
                job_id = job.id_

            jobs.append(job)
            job_ids.append(job_id)

    elif 'preconstructed_jobs' in proposal:
        preconstructed_jobs = proposal.get('preconstructed_jobs')

        # If Running a batch from already-constructed jobs
        if preconstructed_jobs:
            origin = batch_job.get('origin')
            jobs = []
            job_ids = []

            for preconstructed_job in preconstructed_jobs:
                job = Queue.enqueue_job(preconstructed_job, origin)
                job.insert()
                job_id = job.id_
                jobs.append(job)
                job_ids.append(job_id)
    else:
        raise APIStorageException('The batch job is not formatted correctly.')

    update(batch_job['_id'], {'state': 'running', 'jobs': job_ids})
    return jobs

def cancel(batch_job):
    """
    Cancels all pending jobs, returns number of jobs cancelled.
    """

    pending_jobs = config.db.jobs.find({'state': 'pending', '_id': {'$in': batch_job.get('jobs')}})
    cancelled_jobs = 0
    for j in pending_jobs:
        job = Job.load(j)
        try:
            Queue.mutate(job, {'state': 'cancelled'})
            cancelled_jobs += 1
        except Exception: # pylint: disable=broad-except
            # if the cancellation fails, move on to next job
            continue

    update(batch_job['_id'], {'state': 'cancelled'})
    return cancelled_jobs

def check_state(batch_id):
    """
    Returns state of batch based on state of each of its jobs
    are complete or failed
    """

    batch = get(str(batch_id))

    if batch.get('state') == 'cancelled':
        return None

    batch_jobs = config.db.jobs.find({'_id':{'$in': batch.get('jobs', [])}, 'state': {'$nin': ['complete', 'failed', 'cancelled']}})
    non_failed_batch_jobs = config.db.jobs.find({'_id':{'$in': batch.get('jobs', [])}, 'state': {'$ne': 'failed'}})

    if batch_jobs.count() == 0:
        if non_failed_batch_jobs.count() > 0:
            return 'complete'
        else:
            return 'failed'
    else:
        return None

def get_stats():
    """
    Return the number of jobs by state.
    """
    raise NotImplementedError()

def resume():
    """
    Move cancelled jobs back to pending.
    """
    raise NotImplementedError()

def delete():
    """
    Remove:
      - the batch job
      -  it's spawned jobs
      - all the files it's jobs produced.
    """
    raise NotImplementedError()
