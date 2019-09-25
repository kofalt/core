import json

from requests import Session, exceptions

from .. import config
from ..web.encoder import custom_json_serializer


class BaseWebhook(object):
    def __init__(self, callback_urls, request_timeout=5):
        self.session = Session()
        self.callback_urls = callback_urls
        self._request_timeout = request_timeout

    def build_request_body(self, *args, **kwargs):
        raise NotImplementedError

    def call(self, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        failures = []
        for url in self.callback_urls:
            payload = self.build_request_body(*args, **kwargs)
            try:
                r = self.session.post(url, data=json.dumps(payload, default=custom_json_serializer), timeout=self._request_timeout)
                r.raise_for_status()
            except exceptions.RequestException as e:
                config.log.error('Webhook failed for the following callback url: %s, details: %s', url, e)
                failures.append(e)
                if raise_for_status:
                    raise
        return failures
