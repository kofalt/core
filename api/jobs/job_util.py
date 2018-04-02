"""
Job related utilities.
"""
from ..auth import has_access
from ..dao.basecontainerstorage import ContainerStorage

def get_context_for_destination(cont_type, cont_id, uid):
    """ Get gear run context for the given destination container.
    
    Arguments:
        cont_type (str): The destination container type.
        cont_id (str): The destination container id.
        uid (str): The user id for permission checking

    Returns:
        dict: The context built from the container hierarchy
    """
    storage = ContainerStorage.factory(cont_type)
    cont = storage.get_container(cont_id)
    parent_tree = storage.get_parent_tree(cont_id, cont=cont)

    # This is a quick and dirty solution that walks top down, updating
    # context from each parent container if the user has ro permissions.
    context = {}

    # Walk top down, updating context as we go
    parent_tree.reverse()
    parent_tree.append(cont)

    for parent in parent_tree:
        if not uid or has_access(uid, parent, 'ro'):
            parent_context = parent.get('info', {}).get('context', {})
            context.update(parent_context)

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
                    'value': context[x]
                }
            else:
                config['inputs'][x] = {
                    'base': 'context',
                    'found': False
                }

