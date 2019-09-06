
from .. import config, util
from ..dao.liststorage import FileStorage
from ..web import base, errors


class VirusScanCallbackHandler(base.RequestHandler):
    def post(self, cont_name, list_name, **kwargs):
        util.verify_signed_url(self.request.url, 'POST')
        _id = kwargs.pop('cid')
        signature = self.get_param('signature')
        filename = kwargs.get('name')
        if not signature:
            raise errors.APIPermissionException

        payload = self.request.json_body
        payload = {
            'virus_scan.state': payload['state']
        }
        storage = FileStorage(cont_name)
        storage.exec_op('PUT', _id=_id, query_params=kwargs, payload=payload)
        if payload['virus_scan.state']:
            storage.exec_op('DELETE', _id=_id, query_params=kwargs)
