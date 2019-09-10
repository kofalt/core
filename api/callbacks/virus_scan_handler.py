from .. import signed_urls, validators
from ..dao.liststorage import FileStorage
from ..web import base, errors


class VirusScanCallbackHandler(base.RequestHandler):
    def post(self, cont_name, **kwargs):
        if not (self.get_param('signature') and self.get_param('expires')):
            raise errors.APIPermissionException

        payload = self.request.json_body
        validators.validate_data(payload, 'callbacks-virus-scan.json', 'input', 'POST')

        signed_urls.verify_signed_url(self.request.url, 'POST')
        _id = kwargs.pop('cid')
        update = {
            'virus_scan.state': payload['state']
        }
        storage = FileStorage(cont_name)
        storage.exec_op('PUT', _id=_id, query_params=kwargs, payload=update)
        if payload['state'] == 'virus':
            storage.exec_op('DELETE', _id=_id, query_params=kwargs)
