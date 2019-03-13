"""
Job related utilities.
"""
import copy

from ..auth import has_access
from ..dao.basecontainerstorage import ContainerStorage
from ..dao.containerutil import singularize
from ..web import errors
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
    for config_input in job_map_copy['config'].get('inputs', {}).values():
        if config_input.get('base') == 'file':
            config_input['object'].pop('info', None)
    return job_map_copy


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
            raise errors.APIPermissionException('Only admin can override job provider!')
        if validate_provider:
            validate_provider_class(compute_provider_id, 'compute')

    return compute_provider_id
