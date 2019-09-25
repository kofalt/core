from .. import signed_urls, validators
from ..dao import liststorage
from ..web import base, errors


class VirusScanCallbackHandler(base.RequestHandler):
    def post(self, cont_name, **kwargs):
        payload = self.request.json_body
        validators.validate_data(payload, 'callbacks-virus-scan.json', 'input', 'POST')

        signed_urls.verify_signed_url(self.request.url, 'POST')
        _id = kwargs.pop('cid')
        storage = liststorage.FileStorage(cont_name)
        file_info = storage.exec_op('GET', _id=_id, query_params=kwargs)
        # prevent using the url multiple times
        if file_info['virus_scan']['state'] != 'quarantined':
            raise errors.APIPreconditionFailed('Virus scan state is already set for this file')
        storage.set_virus_scan_state(_id=_id, query_params=kwargs, state=payload['state'])
