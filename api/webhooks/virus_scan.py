from urlparse import urljoin

from .. import config, signed_urls
from ..dao import containerutil
from .base import BaseWebhook


class VirusScanWebhook(BaseWebhook):
    """
    VirusScanWebhook class.
    """

    def __init__(self, callback_url):
        self.download_link_tempalte = '{container}/{container_id}/files/{file_name}'
        self.response_link_tempalte = 'callbacks/virus-scan/{container}/{container_id}/files/{file_name}'
        super(VirusScanWebhook, self).__init__([callback_url])

    @staticmethod
    def _build_url(template, **kwargs):
        return urljoin(
            config.get_config()['site']['api_url'].rstrip('/') + '/',
            template.format(**kwargs)
        )

    def build_request_body(self, *args, **kwargs):
        file_info = kwargs.get('file_info')
        parent_container = kwargs.get('parent')
        url_params = {
            'container': containerutil.pluralize(parent_container['type']),
            'container_id': parent_container['_id'],
            'file_name': file_info['name']
        }
        signed_dowload_url = signed_urls.generate_signed_url(
            self._build_url(self.download_link_tempalte, **url_params)
        )
        signed_response_url = signed_urls.generate_signed_url(
            self._build_url(self.response_link_tempalte, **url_params),
            method='POST'
        )
        return {
            'file': {
                '_id': file_info['_id'],
                'name': file_info['name'],
                'created': file_info['created'],
                'modified': file_info['modified'],
                'mimetype': file_info['mimetype'],
                'hash': file_info['hash'],
            },
            'file_download_url': signed_dowload_url,
            'response_url': signed_response_url
        }
