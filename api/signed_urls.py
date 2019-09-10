import datetime
import hashlib
import hmac
import time
import urlparse
from urllib import quote, urlencode

from . import config
from .web import errors


def generate_signed_url(url, method='GET', expires_in=3600):
    expires = int(time.time() + datetime.timedelta(seconds=expires_in).total_seconds())
    url_parts = list(urlparse.urlparse(url))
    url_parts[2] = quote(url_parts[2])
    signature = hmac.new(
        str(config.get_config()['core']['signed_url_secret']),
        msg='{}:{}:{}:{}'.format(method, url_parts[1].rsplit(':', 1)[0], url_parts[2], expires),
        digestmod=hashlib.sha256
    ).hexdigest()
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query['expires'] = expires
    query['signature'] = signature
    url_parts[4] = urlencode(query)
    return urlparse.urlunparse(url_parts)

def verify_signed_url(url, method):
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    expires = int(query.pop('expires'))
    signature = query.pop('signature')
    url_parts[4] = urlencode(query)
    url = urlparse.urlunparse(url_parts)
    calc_signature = hmac.new(
        str(config.get_config()['core']['signed_url_secret']),
        msg='{}:{}:{}:{}'.format(method, url_parts[1].rsplit(':', 1)[0], url_parts[2], expires),
        digestmod=hashlib.sha256
    ).hexdigest()
    if signature != calc_signature:
        raise errors.APIPermissionException('Invalid signature')
    if expires < time.time():
        raise errors.APIPermissionException('Expired signed url')

    return True
