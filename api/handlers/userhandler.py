import base64
import datetime
import pymongo
import os

from ..web import base
from .. import util
from .. import config
from .. import validators
from ..auth import userauth, require_privilege, Privilege
from ..auth.apikeys import UserApiKey
from ..auth.authproviders import AuthProvider
from ..dao import containerstorage
from ..dao import noop
from ..dao import dbutil
from ..jobs.queue import Queue

from ..web.errors import APIStorageException

log = config.log


class UserHandler(base.RequestHandler):

    def __init__(self, request=None, response=None):
        super(UserHandler, self).__init__(request, response)
        self.storage = containerstorage.UserStorage()

    def get(self, _id):
        user = self._get_user(_id)
        permchecker = userauth.default(self, user)
        projection = {}
        if not self.user_is_admin:
            projection['wechat'] = 0
        if not (self.uid == _id or self.user_is_admin):
            projection['info'] = 0
        result = permchecker(self.storage.exec_op)('GET', _id, projection=projection or None)
        if result is None:
            self.abort(404, 'User does not exist')
        result['root'] = 'site_admin' in result.get('roles', ['user'])
        return result

    def self(self):
        """Return details for the current User."""
        if not self.uid:
            self.abort(400, 'no user is logged in')
        user = self.storage.exec_op('GET', self.uid)
        if not user:
            self.abort(403, 'user does not exist')
        user['root'] = 'site_admin' in user.get('roles', ['user'])
        api_key = UserApiKey.get(self.uid)
        if api_key:
            user['api_key'] = {
                'key': api_key['_id'],
                'created': api_key['created'],
                'last_used': api_key['last_used']
            }
        return user

    def get_all(self):
        permchecker = userauth.list_permission_checker(self)
        projection = {'preferences': 0, 'api_key': 0, 'info': 0}
        if not self.user_is_admin:
            projection['wechat'] = 0
        page = permchecker(self.storage.exec_op)('GET', projection=projection, pagination=self.pagination)
        for result in page['results']:
            result['root'] = 'site_admin' in result.get('roles', ['user'])
        if page['results'] is None:
            self.abort(404, 'Not found')
        return self.format_page(page)

    def delete(self, _id):
        user = self._get_user(_id)
        permchecker = userauth.default(self, user)
        # Check for authZ before cleaning up user permissions
        permchecker(noop)('DELETE', _id)
        result = self.storage.exec_op('DELETE', _id)
        if result.deleted_count == 1:
            return {'deleted': result.deleted_count}
        else:
            self.abort(404, 'User {} not removed'.format(_id))
        return result

    @validators.verify_payload_exists
    def put(self, _id):
        """Update a user"""
        user = self._get_user(_id)
        permchecker = userauth.default(self, user)
        payload = self.request.json_body
        if not payload:
            self.abort(400, 'PUT request body cannot be empty')

        # Password is only valid if basic auth enabled
        password = payload.pop('password', None)

        if payload.get('root') is not None:
            payload['roles'] = ['site_admin'] if payload.pop('root', None) else ['user']
        mongo_schema_uri = validators.schema_uri('mongo', 'user.json')
        mongo_validator = validators.decorator_from_schema_path(mongo_schema_uri)
        payload_schema_uri = validators.schema_uri('input', 'user-update.json')
        payload_validator = validators.from_schema_path(payload_schema_uri)
        payload_validator(payload, 'PUT')

        self.hash_password(password, payload)

        payload['modified'] = datetime.datetime.utcnow()
        result = mongo_validator(permchecker(self.storage.exec_op))('PUT', _id=_id, payload=payload)
        if result.modified_count == 1:
            if payload.get('disabled', False) and self.is_true('clear_permissions'):
                self.storage.cleanup_user_permissions(_id)
            return {'modified': result.modified_count}
        else:
            self.abort(404, 'User {} not updated'.format(_id))

    def post(self):
        """Add user"""
        permchecker = userauth.default(self)
        payload = self.request.json_body

        # Password is only valid if basic auth enabled
        password = payload.pop('password', None)
        payload['roles'] = payload.get('roles', ['user'])
        if payload.pop('root', None):
            payload['roles'] = ['site_admin']

        if self.is_true('wechat'):
            payload['wechat'] = {'registration_code': base64.urlsafe_b64encode(os.urandom(42))}
        mongo_schema_uri = validators.schema_uri('mongo', 'user.json')
        mongo_validator = validators.decorator_from_schema_path(mongo_schema_uri)
        payload_schema_uri = validators.schema_uri('input', 'user-new.json')
        payload_validator = validators.from_schema_path(payload_schema_uri)
        payload_validator(payload, 'POST')
        payload['created'] = payload['modified'] = datetime.datetime.utcnow()
        payload.setdefault('email', payload['_id'])
        payload.setdefault('avatars', {})

        self.hash_password(password, payload)

        if self.public_request and config.db.users.count() == 0:
            try:
                config.db.singletons.insert_one({'_id': 'bootstrap', 'uid': payload['_id']})
            except pymongo.errors.DuplicateKeyError:
                pass
            else:
                payload['roles'] = ['site_admin']
                result = mongo_validator(self.storage.exec_op)('POST', payload=payload)
                if result.acknowledged:
                    api_key = UserApiKey.generate(payload['_id'])
                    return {'_id': result.inserted_id, 'key': api_key}
                else:
                    config.db.singletons.delete_one({'_id': 'bootstrap'})

        result = mongo_validator(permchecker(self.storage.exec_op))('POST', payload=payload)
        if result.acknowledged:
            return {'_id': result.inserted_id}
        else:
            self.abort(404, 'User {} not created'.format(payload['_id']))

    def avatar(self, uid):
        self.resolve_avatar(uid, default=self.request.GET.get('default'))

    def self_avatar(self):
        if self.uid is None:
            self.abort(404, 'not a logged-in user')
        self.resolve_avatar(self.uid, default=self.request.GET.get('default'))

    def resolve_avatar(self, email, default=None):
        """
        Given an email, redirects to their avatar.
        On failure, either 404s or redirects to default, if provided.
        """

        # Storage throws a 404; we want to catch that and handle it separately in the case of a provided default.
        try:
            user = self._get_user(email)
        except APIStorageException:
            user = {}

        avatar  = user.get('avatar', None)

        # If the user exists but has no set avatar, try to get one
        if user and avatar is None:
            gravatar = util.resolve_gravatar(email)

            if gravatar is not None:
                user = config.db['users'].find_one_and_update({
                        '_id': email,
                    }, {
                        '$set': {
                            'avatar': gravatar,
                            'avatars.gravatar': gravatar,
                        }
                    },
                    return_document=pymongo.collection.ReturnDocument.AFTER
                )

        if user.get('avatar', None):
            # Our data is unicode, but webapp2 wants a python-string for its headers.
            self.redirect(str(user['avatar']), code=307)
        elif default is not None:
            self.redirect(str(default), code=307)
        else:
            self.abort(404, 'no avatar')

    def generate_api_key(self):
        if not self.uid:
            self.abort(400, 'no user is logged in')
        generated_key = UserApiKey.generate(self.uid)
        return {'key': generated_key}

    @require_privilege(Privilege.is_admin)
    def reset_registration(self, uid):
        new_registration_code = base64.urlsafe_b64encode(os.urandom(42))
        update = {
            'modified': datetime.datetime.utcnow(),
            'wechat': {
                'registration_code': new_registration_code
            }
        }
        result = self.storage.exec_op('PUT', _id=uid, payload=update)
        if result.modified_count == 1:
            return {'registration_code': new_registration_code}
        else:
            self.abort(404, 'User {} not updated'.format(uid))

    def _get_user(self, _id):
        user = self.storage.get_container(_id)
        if user is not None:
            return user
        else:
            self.abort(404, 'user {} not found'.format(_id))

    @require_privilege(Privilege.is_user)
    def get_info(self):
        result = self.storage.get_el(self.uid, projection={'info': 1}).get('info', {})
        if self.get_param('fields', None):
            filtered = {}
            for field in self.get_param('fields').split(','):
                if result.get(field):
                    filtered[field] = result[field]
            result = filtered
        return result

    @require_privilege(Privilege.is_user)
    @validators.verify_payload_exists
    def modify_info(self):
        payload = self.request.json_body
        validators.validate_data(payload, 'info_update.json', 'input', 'POST')
        result = self.storage.modify_info(self.uid, payload)
        return {'modified': result.modified_count}

    @require_privilege(Privilege.is_user)
    def get_jobs(self):
        whitelist = {'created-by': [self.uid]}
        if self.get_param('gear', None):
            whitelist['gear-name'] = [self.get_param('gear')]

        query = Queue.lists_to_query(whitelist, {}, [])
        page = dbutil.paginate_find(config.db.jobs, {'filter': query}, self.pagination)

        result = {
            'stats': Queue.job_states(whitelist, {}, []),
            'total': page['total'],
            'jobs': page['results']
        }

        return result

    def hash_password(self, password, payload):
        if password is not None:
            try:
                auth_provider = AuthProvider.factory('basic')
            except NotImplementedError as e:
                self.abort(400, str(e))

            payload['password_hash'] = auth_provider.hash(password)
