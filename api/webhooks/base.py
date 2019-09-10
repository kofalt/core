import json

from requests import Session

from ..web.encoder import custom_json_serializer


class BaseWebhook(object):
    def __init__(self, callback_urls):
        self.session = Session()
        self.callback_urls = callback_urls

    def build_request_body(self, *args, **kwargs):
        raise NotImplementedError

    def call(self, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        failures = []
        for url in self.callback_urls:
            payload = self.build_request_body(*args, **kwargs)
            r = self.session.post(url, data=json.dumps(payload, default=custom_json_serializer))
            if raise_for_status:
                r.raise_for_status()
            if not r.ok:
                failures.append(r)
        return failures
