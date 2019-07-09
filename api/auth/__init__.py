from enum import Enum

from ..types import Origin
from ..web.errors import APIPermissionException
from ..config import log

# The values for the role privileges are below
class Privilege(Enum):

    is_user =           0b0001
    can_upload_gear =   0b0010
    is_admin =          0b0100
    is_drone =          0b1000

# the values for the user roles and what they can access are below
class Role(Enum):
    public =       ('public', 0)
    user =         ('user', Privilege.is_user.value)
    developer =    ('developer', Privilege.is_user.value | Privilege.can_upload_gear.value)
    site_admin =   ('site_admin', Privilege.is_user.value | Privilege.can_upload_gear.value | Privilege.is_admin.value)
    drone =        ('drone', Privilege.is_user.value | Privilege.can_upload_gear.value | Privilege.is_admin.value | Privilege.is_drone.value)

    def __init__(self, role, privileges):
        self.role = role
        self.privileges = privileges


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

def require_privilege(privilege):
    """
    Returns a decorator that requires the given role
    """
    def require_privilege_decorator(handler_method):
        def check_role(self, *args, **kwargs):
            if not any([role.privileges & privilege.value == privilege.value for role in self.roles]):
                raise APIPermissionException('{} privilege required for action.'.format(privilege.name))
            return handler_method(self, *args, **kwargs)
        return check_role
    return require_privilege_decorator

def has_privilege(roles, privilege):
    """
    A non decorator role check function
    """
    if not any([role.privileges & privilege.value == privilege.value for role in roles]):
        raise APIPermissionException('{} privilege required for action.'.format(privilege))
    return True
