"""
Purpose of this module is to define all the permissions checker decorators for the ContainerHandler classes.
"""

from . import _get_access, INTEGER_PERMISSIONS
from ..web.errors import APIPermissionException


def default_container(handler, container=None, target_parent_container=None):
    """
    This is the default permissions checker generator.
    The resulting permissions checker modifies the exec_op method by checking the user permissions
    on the container before actually executing this method.
    """
    def g(exec_op):
        def f(method, _id=None, payload=None, unset_payload=None, recursive=False, r_payload=None, replace_metadata=False):
            projection = None
            errors = None
            if method == 'GET' and container.get('public', False):
                has_access = True
            elif method == 'GET':
                has_access = _get_access(handler.uid, container, scope=handler.scope) >= INTEGER_PERMISSIONS['ro']
            elif method == 'POST':
                required_perm = 'rw'
                if target_parent_container.get('cont_name') == 'group':
                    # Create project on group, require admin
                    required_perm = 'admin'
                has_access = _get_access(handler.uid, target_parent_container, scope=handler.scope) >= INTEGER_PERMISSIONS[required_perm]
            elif method == 'DELETE':
                # Project delete requires admin, others require rw
                if container['cont_name'] == 'project' or container.get('has_original_data', False):
                    required_perm = 'admin'
                else:
                    required_perm = 'rw'

                user_perms = _get_access(handler.uid, container, scope=handler.scope)
                has_access = user_perms >= INTEGER_PERMISSIONS[required_perm]

                if not has_access and container.get('has_original_data', False) and user_perms == INTEGER_PERMISSIONS['rw']:
                    # The user was not granted access because the container had original data
                    errors = {'reason': 'original_data_present'}
                else:
                    errors = {'reason': 'permission_denied'}

            elif method == 'PUT' and target_parent_container is not None:
                if target_parent_container.get('cont_name') in ['project', 'session', 'subject']:
                    required_perm = 'rw'
                else:
                    required_perm = 'admin'
                has_access = (
                    _get_access(handler.uid, container, scope=handler.scope) >= INTEGER_PERMISSIONS[required_perm] and
                    _get_access(handler.uid, target_parent_container, scope=handler.scope) >= INTEGER_PERMISSIONS[required_perm]
                )
            elif method == 'PUT' and target_parent_container is None:
                required_perm = 'rw'
                has_access = _get_access(handler.uid, container, scope=handler.scope) >= INTEGER_PERMISSIONS[required_perm]
            else:
                has_access = False

            if has_access:
                return exec_op(method, _id=_id, payload=payload, unset_payload=unset_payload, recursive=recursive, r_payload=r_payload, replace_metadata=replace_metadata, projection=projection)
            else:
                error_msg = 'user not authorized to perform a {} operation on the container.'.format(method)
                raise APIPermissionException(error_msg, errors=errors)
        return f
    return g


def collection_permissions(handler, container=None, _=None):
    """
    Collections don't have a parent_container, catch param from generic call with _.
    Permissions are checked on the collection itself or not at all if the collection is new.
    """
    def g(exec_op):
        def f(method, _id=None, payload = None):
            if method == 'GET' and container.get('public', False):
                has_access = True
            elif method == 'GET':
                has_access = _get_access(handler.uid, container) >= INTEGER_PERMISSIONS['ro']
            elif method == 'DELETE':
                has_access = _get_access(handler.uid, container) >= INTEGER_PERMISSIONS['admin']
            elif method == 'POST':
                has_access = True
            elif method == 'PUT':
                has_access = _get_access(handler.uid, container) >= INTEGER_PERMISSIONS['rw']
            else:
                has_access = False

            if has_access:
                return exec_op(method, _id=_id, payload=payload)
            else:
                handler.abort(403, 'user not authorized to perform a {} operation on the container'.format(method))
        return f
    return g


def default_referer(handler, parent_container=None):
    def g(exec_op):
        def f(method, _id=None, payload=None):
            access = _get_access(handler.uid, parent_container, scope=handler.scope)
            if method == 'GET' and parent_container.get('public', False):
                has_access = True
            elif method == 'GET':
                has_access = access >= INTEGER_PERMISSIONS['ro']
            elif method in ['POST', 'PUT', 'DELETE']:
                has_access = access >= INTEGER_PERMISSIONS['rw']
            else:
                has_access = False

            if has_access:
                return exec_op(method, _id=_id, payload=payload)
            else:
                handler.abort(403, 'user not authorized to perform a {} operation on parent container'.format(method))
        return f
    return g

def has_any_referer_access(handler, method, container, parent_container):
    """Check if access is allowed for this request.

    Arguments:
        handler (RequestHandler): The request handler instance, with a uid
        method (str): The method name (uppercase)
        container (dict): The base container
        parent_container (dict): The parent container

    Returns:
        bool: True if access is permitted, false otherwise
    """
    has_access = False

    # if parent container is "site", then the user must be a admin to make changes
    if handler.user_is_admin:
        has_access = True
    elif parent_container == 'site':
        has_access = method == 'GET' and container.get('public', False)
    elif method == 'GET' and (container.get('public', False) or parent_container.get('public', False)):
        has_access = True
    elif parent_container.get('cont_name') == 'user':
        # if the parent container is a user, then only the user has access
        has_access = handler.uid == parent_container['_id']
    else:
        access = _get_access(handler.uid, parent_container)
        if method == 'GET':
            has_access = access >= INTEGER_PERMISSIONS['ro']
        elif method in ['POST', 'PUT', 'DELETE']:
            # if the parent container is a group then the user must be an admin to create/delete views
            if parent_container.get('cont_name') == 'group':
                has_access = access >= INTEGER_PERMISSIONS['admin']
            else:
                has_access = access >= INTEGER_PERMISSIONS['rw']

    return has_access

def any_referer(handler, container=None, parent_container=None):
    def g(exec_op):
        def f(method, _id=None, payload=None):
            # finally we fall back on the default referrer
            if has_any_referer_access(handler, method, container, parent_container):
                return exec_op(method, _id=_id, payload=payload)
            else:
                raise APIPermissionException('user not authorized to perform a {} operation on parent container'.format(method))
        return f
    return g

def public_request(handler, container=None):
    """
    For public requests we allow only GET operations on containers marked as public.
    """
    def g(exec_op):
        def f(method, _id=None, payload = None):
            if method == 'GET' and container.get('public', False):
                return exec_op(method, _id, payload)
            else:
                handler.abort(403, 'not authorized to perform a {} operation on this container'.format(method))
        return f
    return g

def list_permission_checker(handler):
    def g(exec_op):
        def f(method, query=None, user=None, public=False, projection=None, pagination=None):
            if handler.scope:
                query['$or'] = [{'parents.{}'.format(handler.scope['level']): handler.scope['id']},
                                {'_id': handler.scope['id']}, {'public': True}]
            elif user and (user['_id'] != handler.uid):
                handler.abort(403, 'User ' + handler.uid + ' may not see the Projects of User ' + user['_id'])
            else:
                query['permissions'] = {'$elemMatch': {'_id': handler.uid}}
            if handler.is_true('public'):
                query['$or'] = [{'public': True}, {'permissions': query.pop('permissions')}]
            return exec_op(method, query=query, user=user, public=public, projection=projection, pagination=pagination)
        return f
    return g


def list_public_request(exec_op):
    def f(method, query=None, user=None, public=False, projection=None, pagination=None):
        if public:
            query['public'] = True
        return exec_op(method, query=query, user=user, public=public, projection=projection, pagination=pagination)
    return f
