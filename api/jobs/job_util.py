"""
Job related utilities.
"""
from ..auth import has_access
from ..dao.basecontainerstorage import ContainerStorage

def get_context_for_destination(destination, uid):
    """ Get gear run context for the given destination container.
    
    Arguments:
        destination (ContainerRef): A reference to the destination container.
        uid (str): The user id for permission checking

    Returns:
        dict: The context built from the container hierarchy
    """
    storage = ContainerStorage.factory(destination.type)
    cont = storage.get_container(destination.id)
    parent_tree = storage.get_parent_tree(destination.id, cont=cont)

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

def resolve_context_inputs(config, gear, destination, uid):
    """ Resolve input fields with a base of 'context' given a destination and gear spec.
    
    Arguments:
        config (dict): The job configuration to be updated
        gear (dict): The gear spec
        destination (ContainerRef): A reference to the destination container.
        uid (str): The user id for permission checking
    """
    # Callers don't (shouldn't) specify the context inputs when scheduling a job,
    # so we walk the gear inputs, checking for any context inputs.
    context = None
    for x in gear['gear']['inputs']:
        input_type = gear['gear']['inputs'][x]['base']
        if input_type == 'context':
            # Lazily resolve the context a single time
            if context is None:
                context = get_context_for_destination(destination, uid)

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

