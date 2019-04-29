"""
Job related utilities.
"""
import copy
from flywheel_common import errors

from ..config import log
from ..auth import has_access
from ..dao.basecontainerstorage import ContainerStorage
from ..dao.containerutil import singularize
from ..web.request import AccessType
from ..site.providers import validate_provider_class


def remove_potential_phi_from_job(job_map):
    """Remove certain fields from jobs to simplify the endpoint, the fields
    are produced metadata and info objects on config.inputs items

    Args:
        job_map (dict): A job object to be returned
    Returns:
        dict: A copy of the job object with potential phi removed
    """
    job_map_copy = copy.deepcopy(job_map)
    job_map_copy.pop('produced_metadata', None)
    job_config = job_map_copy.get('config', {})
    if not job_config:
        return job_map_copy
    try:
        config_inputs = job_config.get('inputs') or {}
        for config_input in config_inputs.values():
            if config_input.get('base') == 'file':
                config_input['object'].pop('info', None)
    except (TypeError, KeyError, AttributeError) as e:
        log.critical('Could not remove phi from job {}', exc_info=e)
    return job_map_copy


def log_job_access(handler, job):
    """Log a view_file access for each file input for the job because we
    are going to return the info object on the inputs

    Args:
        handler (RequestHandler): The handler that is returning the job
        job (Job): A job object
    """
    try:
        if job.config:
            config_inputs = job.config.get('inputs') or {}
            for config_input in config_inputs.values():
                if config_input.get('base') == 'file':
                    file_parent_type = config_input['hierarchy']['type']
                    file_parent_id = config_input['hierarchy']['id']
                    handler.log_user_access(AccessType.view_file,
                                            cont_name=file_parent_type,
                                            cont_id=file_parent_id,
                                            filename=config_input['location'].get('name'))
        if job.produced_metadata:
            for container_type, metadata in job.produced_metadata.items():
                if job.parents.get(container_type):
                    handler.log_user_access(AccessType.view_container,
                                            cont_name=container_type,
                                            cont_id=job.parents[container_type])
                if container_type == 'session' and metadata.get('subject'):
                    if job.parents.get('subject'):
                        handler.log_user_access(AccessType.view_subject,
                                                cont_name='subject',
                                                cont_id=job.parents['subject'])
    except (TypeError, KeyError, AttributeError) as e:
        log.critical('Could not log accessing all inputs and outputs of job {}'.format(job.id), exc_info=e)

    handler.log_user_access(AccessType.view_job, job_id=job.id_)


def get_context_for_destination(cont_type, cont_id, uid, storage=None, cont=None):
    """ Get gear run context for the given destination container.

    Arguments:
        cont_type (str): The destination container type.
        cont_id (str): The destination container id.
        uid (str): The user id for permission checking.
        storage (ContainerStorage): The optional container storage instance.
        cont (dict): The optional container, if already found.

    Returns:
        dict: The context built from the container hierarchy
    """
    if not storage:
        storage = ContainerStorage.factory(cont_type)

    if not cont:
        cont = storage.get_container(cont_id)

    cont['cont_type'] = storage.cont_name
    parent_tree = storage.get_parent_tree(cont_id, cont=cont)

    # This is a quick and dirty solution that walks top down, updating
    # context from each parent container if the user has ro permissions.
    context = {}

    # Walk top down, updating context as we go
    parent_tree.reverse()
    parent_tree.append(cont)

    for parent in parent_tree:
        if not uid or has_access(uid, parent, 'ro'):
            cont_type = singularize(parent['cont_type'])
            parent_context = parent.get('info', {}).get('context', {})

            for key, value in parent_context.items():
                context[key] = {
                    'container_type': cont_type,
                    'label': parent['label'],
                    'id': parent['_id'],
                    'value': value
                }

    return context

def resolve_context_inputs(config, gear, cont_type, cont_id, uid, context=None):
    """ Resolve input fields with a base of 'context' given a destination and gear spec.

    Arguments:
        config (dict): The job configuration to be updated
        gear (dict): The gear spec
        cont_type (str): The destination container type.
        cont_id (str): The destination container id.
        uid (str): The user id for permission checking
        context (dict): The optional context, if already resolved
    """
    # Callers don't (shouldn't) specify the context inputs when scheduling a job,
    # so we walk the gear inputs, checking for any context inputs.
    for x in gear['gear']['inputs']:
        input_type = gear['gear']['inputs'][x]['base']
        if input_type == 'context':
            # Lazily resolve the context a single time
            if context is None:
                context = get_context_for_destination(cont_type, cont_id, uid)

            if x in context:
                config['inputs'][x] = {
                    'base': 'context',
                    'found': True,
                    'value': context[x]['value']
                }
            else:
                config['inputs'][x] = {
                    'base': 'context',
                    'found': False
                }

def validate_job_compute_provider(job_map, request_handler, validate_provider=False):
    """Verify that the user can set compute_provider_id, if provided.

    Checks if compute_provider_id is set in job_map, and if so verifies that
    the user has the correct permissions.

    Returns:
        str: The compute_provider_id if specified, otherwise None

    Raises:
        APIPermissionException: If a non-admin user attempts to override provider
        APIValidataionException: If validate_provider is true and the provider either
            doesn't exist, or is not a compute provider
    """
    compute_provider_id = job_map.get('compute_provider_id')
    if compute_provider_id:
        if not request_handler.user_is_admin:
            raise errors.PermissionError('Only admin can override job provider!')
        if validate_provider:
            try:
                validate_provider_class(compute_provider_id, 'compute')
            except errors.ResourceNotFound:
                raise errors.ValidationError('Provider id is not valid')

    return compute_provider_id
