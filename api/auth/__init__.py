from enum import Enum

from ..types import Origin
from ..web.errors import APIPermissionException
from ..config import log

# The values for the user roles and what they can access are below
# A developer can do everything allowed by the developer access key
#  but also anything allowed by the user and public access keys
class Role(Enum):
    public =        0b00000
    user =          0b00001
    developer =     0b00011
    site_admin =    0b00111
    super_user =    0b01111
    drone =         0b11111

# The values for the role privileges are below
class Privilege(Enum):
    user =         0b00001
    developer =    0b00010
    site_admin =   0b00100
    super_user =   0b01000
    drone =        0b10000

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

def require_privilege_decorator(privilege):
    """
    Returns a decorator that requires the given role
    """
    def require_privilege(handler_method):
        def check_role(self, *args, **kwargs):
            log.debug(self.role.value)
            if self.role.value & privilege.value != privilege.value:
                raise APIPermissionException('{} privilege required for action.'.format(privilege))
            return handler_method(self, *args, **kwargs)
        return check_role
    return require_privilege

def require_privilege_check(role, privilege):
    """
    A non decorator role check function
    """
    if role.value & privilege.value != privilege.value:
        raise APIPermissionException('{} privilege required for action.'.format(privilege))
    return True
