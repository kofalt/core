from ..web import base
from .. import config, validators
from ..auth import require_login
from ..dao.containerstorage import SearchStorage
from ..web.errors import APIStorageException
from ..auth import groupauth
from ..dao import noop


log = config.log

class SaveSearchHandler(base.RequestHandler):

    def __init__(self, request=None, response=None):
        super(SaveSearchHandler, self).__init__(request, response)
        self.storage = SearchStorage()

    @require_login
    def post(self):
        payload = self.request.json_body
        validators.validate_data(payload, 'save-search-input.json', 'input', 'POST')
        payload['permissions'] = [{"_id": self.uid, "access": "admin"}]
        result = self.storage.create_el(payload)
        if result.acknowledged:
            if result.inserted_id:
                return {'_id': result.inserted_id}
        else:
            raise APIStorageException("Failed to save the search")

    def get_all(self):
        log.debug(self.uid)
        return self.storage.get_all_el({}, {'_id': self.uid}, {'label': 1})

    def get(self, sid):
        result = self.storage.get_el(sid)
        if result is None:
            self.abort(404, 'Element {} not found'.format(sid))
        return result

    def delete(self, sid):
        search = self.storage.get_container(sid)
        permchecker = groupauth.default(self, search)
        result = permchecker(self.storage.exec_op)('DELETE', sid)
        if result.deleted_count == 1:
            return {'deleted': result.deleted_count}
        else:
            self.abort(404, 'Group {} not removed'.format(sid))
        return result

    def put(self, sid):
        payload = self.request.json_body
        log.debug(payload)
        validators.validate_data(payload, 'save-search-update.json', 'input', 'PUT')
        permchecker = groupauth.default(self, payload)
        permchecker(noop)('PUT', sid)
        result = self.storage.update_el(sid, payload)
        log.debug(result)
        if result.modified_count == 1:
            return {'modified': result.modified_count}
        else:
            self.abort(404, 'Saved search {} not updated'.format(sid))
