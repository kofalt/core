from ..types import Origin
from ..web.errors import APIPermissionException

PERMISSIONS = [
    {
        'rid': 'ro',
        'name': 'Read-Only',
    },
    {
        'rid': 'rw',
        'name': 'Read-Write',
    },
    {
        'rid': 'admin',
        'name': 'Admin',
    },
]

INTEGER_PERMISSIONS = {r['rid']: i for i, r in enumerate(PERMISSIONS)}

def _get_group_access(uid, group, scope=None, get_projects=None):
    """Checks to see if user has access to the group, or any of the groups
        projects, in which case the access to the group is read only.

    Args:
        uid (str): user id
        group (dict): The group container document
        scope (dict): A scope if the handler is scoped by its api key
        get_projects (fn): A function to check if a project has a user's permissions

    Returns:
        int: The integer value of the user's access to the container
    """
    get_access_result = _get_access(uid, group, scope)
    if get_access_result == -1 and scope is None:
        if get_projects is not None and len(get_projects()) > 0:
            # If user has access to any projects of the group, return ro
            return INTEGER_PERMISSIONS['ro']
    return get_access_result

def _get_access(uid, container, scope=None):
    if scope:
        if _check_scope(scope, container):
            return INTEGER_PERMISSIONS[scope['access']]
        else:
            return -1
    permissions_list = container.get('permissions', [])
    for perm in permissions_list:
        if perm['_id'] == uid:
            return INTEGER_PERMISSIONS[perm['access']]
    return -1

def _check_scope(scope, container, parent_container=None):
    if container and container.get('parents'):
        return scope['id'] in container['parents'].itervalues() or scope['id'] == container['_id']
    elif parent_container and parent_container.get('parents'):
        return scope['id'] in parent_container['parents'].itervalues() or scope['id'] == parent_container['_id']

def has_access(uid, container, perm):
    return _get_access(uid, container) >= INTEGER_PERMISSIONS[perm]


def always_ok(exec_op):
    """
    This decorator leaves the original method unchanged.
    It is used as permissions checker when the request is from a site admin
    """
    return exec_op

def require_login(handler_method):
    """
    A decorator to ensure the request is not a public request.

    Accepts drone and user requests.
    """
    def check_login(self, *args, **kwargs):
        if self.public_request:
            raise APIPermissionException('Login required.')
        return handler_method(self, *args, **kwargs)
    return check_login

def require_admin(handler_method):
    """
    A decorator to ensure the request is made as a site admin.

    Accepts drone and user requests.
    """
    def check_admin(self, *args, **kwargs):
        if not self.user_is_admin:
            raise APIPermissionException('Admin user required.')
        return handler_method(self, *args, **kwargs)
    return check_admin

def require_drone(handler_method):
    """
    A decorator to ensure the request is made as a drone.

    Will also ensure site admin, which is implied with a drone request.
    """
    def check_drone(self, *args, **kwargs):
        if self.origin.get('type', '') != Origin.device:
            raise APIPermissionException('Drone request required.')
        if not self.user_is_admin:
            raise APIPermissionException('Superuser required.')
        return handler_method(self, *args, **kwargs)
    return check_drone
