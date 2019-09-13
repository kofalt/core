import fnmatch
import re
import itertools

from .. import config
from ..types import Origin
from ..dao.containerutil import FileReference, create_containerreference_from_filereference, create_filereference_from_dictionary
from ..web.errors import APIValidationException, InputValidationException

from . import gears
from .jobs import Job
from .mappers import RulesMapper
from .queue import Queue

log = config.log

# {
#     '_id':        'SOME_ID',
#     'project_id': 'SOME_PROJECT',

#     Algorithm to run if all sets of rules match
#     'alg':        'my-gear-name',
#
#     At least one match from this array must succeed, or array must be empty
#     'any': [],
#
#     There should be no matches in this array
#     'not': [],
#
#     All matches from array must succeed, or array must be empty
#     'all': [
#         {
#             'type': 'file.type', # Match the file's type
#             'value': 'dicom'
#         },
#         {
#             'type': 'file.name', # Match a shell glob for the file name
#             'value': '*.dcm'
#         },
#         {
#             'type': 'file.modality', # Match the file's modaliy
#             'value': 'MR'
#         },
#         {
#             'type': 'file.classification', # Match any of the file's classification
#             'value': 'diffusion'
#         },
#         {
#             'type': 'container.has-type', # Match the container having any file (including this one) with this type
#             'value': 'bvec'
#         },
#         {
#             'type': 'container.has-classification', # Match the container having any file (including this one) with this classification
#             'value': 'functional'
#         }
#     ]
# }


def get_base_rules():
    """
    Fetch the install-global gear rules from the database
    """

    # rule_doc = config.db.singletons.find_one({'_id': 'rules'}) or {}
    # return rule_doc.get('rule_list', [])
    return []

def _log_file_key_error(file_, container, error):
    log.warning('file ' + file_.get('name', '?') + ' in container ' + str(container.get('_id', '?')) + ' ' + error)

def eval_match(match_type, match_param, file_, container, regex=False):
    """
    Given a match entry, return if the match succeeded.
    """

    def match(value):
        if regex:
            return re.match(match_param, value, flags=re.IGNORECASE) is not None
        elif match_type == 'file.name':
            return fnmatch.fnmatch(value.lower(), match_param.lower())
        else:
            return match_param.lower() == value.lower()

    # Match the file's type
    if match_type == 'file.type':
        file_type = file_.get('type')
        if file_type:
            return match(file_type)
        else:
            _log_file_key_error(file_, container, 'has no type')
            return False

    # Match the file's modality
    if match_type == 'file.modality':
        file_modality = file_.get('modality')
        if file_modality:
            return match(file_modality)
        else:
            return False

    # Match a shell glob for the file name
    elif match_type == 'file.name':
        return match(file_['name'])

    # Match any of the file's classification
    elif match_type == 'file.classification':
        if match_param:
            classification_values = list(itertools.chain.from_iterable(file_.get('classification', {}).itervalues()))
            return any(match(value) for value in classification_values)
        else:
            return False

    # Match the container having any file (including this one) with this type
    elif match_type == 'container.has-type':
        for c_file in container['files']:
            c_file_type = c_file.get('type')
            if c_file_type and match(c_file_type):
                return True

        return False

    # Match the container having any file (including this one) with this classification
    elif match_type == 'container.has-classification':
        if match_param:
            for c_file in container['files']:
                classification_values = list(itertools.chain.from_iterable(c_file.get('classification', {}).itervalues()))
                if any(match(value) for value in classification_values):
                    return True

        return False

    raise Exception('Unimplemented match type ' + match_type)

def eval_rule(rule, file_, container):
    """
    Decide if a rule should spawn a job.
    """

    # Are there matches in the 'not' set?
    for match in rule.not_:
        if eval_match(match['type'], match['value'], file_, container, regex=match.get('regex')):
            return False

    # Are there matches in the 'any' set?
    must_match = len(rule.any_) > 0
    has_match = False

    for match in rule.any_:
        if eval_match(match['type'], match['value'], file_, container, regex=match.get('regex')):
            has_match = True
            break

    # If there were matches in the 'any' array and none of them succeeded
    if must_match and not has_match:
        return False

    # Are there matches in the 'all' set?
    for match in rule.all_:
        if not eval_match(match['type'], match['value'], file_, container, regex=match.get('regex')):
            return False

    return True

def queue_job_legacy(gear_id, input_, fixed_inputs=None):
    """
    Tie together logic used from the no-manifest, single-file era.
    Takes a single FileReference instead of a map.
    """

    gear = gears.get_gear(gear_id)
    gear = gears.filter_optional_inputs(gear)
    fixed_input_keys = [fixed_input['input'] for fixed_input in fixed_inputs] if fixed_inputs else []

    if gears.count_file_inputs(gear) - len(fixed_input_keys) != 1:
        # This shouldn't happen if the handler is correctly validating the POST and PUT methods for rules
        log.error("Legacy gear enqueue attempt of " + gear_id + " failed: must have exactly 1 non-fixed input from the manifest, it has {} non-fixed inputs".format(gears.count_file_inputs(gear) - len(fixed_input_keys)))
        return

    for x in gear['gear']['inputs'].keys():
        if gear['gear']['inputs'][x]['base'] == 'file' and x not in fixed_input_keys:
            input_name = x

    inputs = {
        input_name: input_
    }

    if fixed_inputs:
        for fixed_input in fixed_inputs:
            inputs[fixed_input['input']] = FileReference(type=fixed_input['type'], id=str(fixed_input['id']),
                                                         name=fixed_input['name'])

    gear_name = gear['gear']['name']
    destination = create_containerreference_from_filereference(input_)
    job = Job(gear, inputs, destination=destination, tags=['auto', gear_name])
    return job

def find_type_in_container(container, type_):
    for c_file in container['files']:
        if type_ == c_file['type']:
            return c_file
    return None

def create_potential_jobs(db, container, container_type, file_, rule_failure_callback=None):
    """
    Check all rules that apply to this file, and creates the jobs that should be run.
    Jobs are created but not enqueued.
    Returns list of potential job objects containing job ready to be inserted and rule.
    rule_failure_callback will be called for each rule evauation that fails for any reason
    """

    potential_jobs = []

    # Skip if virus scan feature enabled and the file is quarantined
    if config.get_feature('virus_scan', False):
        virus_scan_state = file_.get('virus_scan', {}).get('state')
        if virus_scan_state and virus_scan_state != 'clean':
            return []

    # Get configured rules for this project
    rules = get_rules_for_container(db, container)

    # Add hardcoded rules that cannot be removed or changed
    for hardcoded_rule in get_base_rules():
        rules.append(hardcoded_rule)

    for rule in rules:
        try:
            if eval_rule(rule, file_, container):
                gear_id = rule.gear_id

                input_ = FileReference(type=container_type, id=str(container['_id']), name=file_['name'])
                job = queue_job_legacy(gear_id, input_, fixed_inputs=rule.fixed_inputs)

                if 'config' in rule:
                    job.config = rule.config

                if 'compute_provider_id' in rule:
                    job.compute_provider_id = rule['compute_provider_id']

                if 'compute_provider_id' in rule:
                    job.compute_provider_id = rule['compute_provider_id']

                potential_jobs.append({
                    'job': job,
                    'rule': rule.to_dict()
                })
        except Exception as exc_val:  # pylint: disable=broad-except
            log.exception('Unable to evaluate rule %s(name=%s)', rule['_id'], rule.get('name'))
            if rule_failure_callback:
                rule_failure_callback(rule, exc_val)

    return potential_jobs

def create_jobs(db, container_before, container_after, container_type, replaced_files=None, rule_failure_callback=None):
    """
    Given a before and after set of file attributes, enqueue a list of jobs that would only be possible
    after the changes.
    Returns the algorithm names that were queued.
    """
    if container_type == 'collection':
        return []

    # A list of FileContainerReferences that have been completely replaced
    # Jobs with these as inputs should get enqueue even if they are in the jobs_before list
    if not replaced_files:
        replaced_files = []

    jobs_before, jobs_after, potential_jobs = [], [], []

    files_before    = container_before.get('files', [])
    files_after     = container_after.get('files', [])

    for f in files_before:
        jobs_before.extend(create_potential_jobs(db, container_before, container_type, f, rule_failure_callback=rule_failure_callback))

    for f in files_after:
        jobs_after.extend(create_potential_jobs(db, container_after, container_type, f, rule_failure_callback=rule_failure_callback))

    # Using a uniqueness constraint, create a list of the set difference of jobs_after \ jobs_before
    # (members of jobs_after that are not in jobs_before)
    for ja in jobs_after:
        replaced_file_name = ''

        replaced_file_in_job_inputs = False
        list_of_inputs = [i for i in ja['job'].inputs.itervalues()]
        for replaced_file in replaced_files:
            if replaced_file in list_of_inputs:
                replaced_file_name = replaced_file.name
                replaced_file_in_job_inputs = True
                break

        if replaced_file_in_job_inputs:
            # one of the replaced files is an input
            log.info('Scheduling job for %s=%s via rule=<%s>, replaced_file=<%s>.',
                container_type, container_before['_id'], ja['rule'].get('name'), replaced_file_name)
            potential_jobs.append(ja)
        else:
            should_enqueue_job = True
            for jb in jobs_before:
                if ja['job'].intention_equals(jb['job']):
                    log.info('Ignoring rule: <%s> for %s=%s - Job has already been queued!',
                        ja['rule'].get('name'), container_type, container_before['_id'])
                    should_enqueue_job = False
                    break # this job matched in both before and after, ignore
            if should_enqueue_job:
                log.info('Scheduling job for %s=%s via rule=<%s>.',
                    container_type, container_before['_id'], ja['rule'].get('name'))
                potential_jobs.append(ja)


    spawned_jobs = []
    origin ={
        'type': str(Origin.system),
        'id': None
    }

    for pj in potential_jobs:
        job_map = pj['job'].map()
        try:
            # This can raise if we somehow ended up with an invalid provider
            job = Queue.enqueue_job(job_map, origin)
            job.insert()
            spawned_jobs.append(pj['rule']['gear_id'])
        except Exception as exc_val:  # pylint: disable=broad-except
            rule = pj.get('rule', {})
            log.exception('Unable to evaluate rule %s(name=%s)', rule.get('_id'), rule.get('name'))
            if rule_failure_callback:
                rule_failure_callback(rule, exc_val)

    return spawned_jobs


# TODO: consider moving to a module that has a variety of hierarchy-management helper functions
def get_rules_for_container(db, container):
    """
    Recursively walk the hierarchy until the project object is found.
    """

    if 'session' in container:
        session = db.sessions.find_one({'_id': container['session']})
        return get_rules_for_container(db, session)
    elif 'project' in container:
        project = db.projects.find_one({'_id': container['project']})
        return get_rules_for_container(db, project)
    else:
        rules_mapper = RulesMapper()
        # Assume container is a project, or a collection (which currently cannot have a rules property)
        result = list(rules_mapper.find_all(project_id=str(container['_id']), disabled={'$ne': True}))

        if not result:
            return []
        else:
            return result

def copy_site_rules_for_project(project_id):
    """
    Copy and insert all site-level rules for project.

    Note: Assumes project exists and caller has access.
    """

    rules_mapper = RulesMapper()
    site_rules = rules_mapper.find_all(project_id='site')

    for rule in site_rules:
        rule_copy = rule.copy()
        rule_copy.project_id = str(project_id)
        rules_mapper.insert(rule_copy)


def validate_regexes(rule):
    invalid_patterns = set()
    for match in rule.get('all', []) + rule.get('any', []) + rule.get('not', []):
        if match.get('regex'):
            pattern = match['value']
            try:
                re.compile(pattern)
            except re.error:
                invalid_patterns.add(pattern)
    if invalid_patterns:
        raise APIValidationException(
            reason='Cannot compile regex patterns',
            patterns=sorted(invalid_patterns)
        )


def validate_auto_update(rule_config, gear_id, update_gear_is_latest, current_gear_is_latest, fixed_inputs):
    if rule_config:
        raise InputValidationException("Gear rule cannot be auto-updated with a config")
    if fixed_inputs:
        raise InputValidationException("Gear rule cannot be auto-updated with fixed inputs")
    # Can only change gear_id to latest id
    # (Really only happens if updating auto_update and gear_id at once)
    elif gear_id:
        if not update_gear_is_latest:
            raise InputValidationException("Cannot manually change gear version of gear rule that is auto-updated")
    elif not current_gear_is_latest:
        raise InputValidationException("Gear rule cannot be auto-updated unless it is uses the latest version of the gear")


def validate_fixed_inputs(geardoc, fixed_inputs):
    """
    Validates the fixed inputs for a rule given a gear doc
    The fixed inputs must:
        - add up to one less than the number of required gear inputs
        - all be valid inputs for the gear
        - exist
    """
    fixed_inputs = fixed_inputs if fixed_inputs else []
    if gears.count_file_inputs(gears.filter_optional_inputs(geardoc)) - len(fixed_inputs) != 1:
        raise InputValidationException("Rule must have exactly 1 non-fixed gear value")
    for fixed_input in fixed_inputs:
        if not geardoc['gear']['inputs'].get(fixed_input['input']):
            raise InputValidationException("Unrecognized gear input cannot be fixed for the rule")
        # Check to see that each fixed input actually exists
        create_filereference_from_dictionary(fixed_input).get_file()

