import datetime
import hashlib
import hmac
import time
import urlparse
from urllib import quote, urlencode

from . import config
from .web import errors


def generate_signed_url(url, method='GET', expires_in=3600):
    """
    Generate a signed url for the given url.

    First we extract the host name and the endpoint from the url. After that using the `signed_url_secret`
    key from the config and SHA256 algorithm we calculate the hash of the following string:
    '<method>:<host>:<endpoint>:<expiration_epoch_time>'

    <method>: restrict using the signed url only with the given HTTP method
    <host>: restrict using the signed url only at the given site
    <endpoint>: restrict using the signed url only for the given endpoint
    <expiration_epoch_time>: restrict using the signed url only for the given time

    The generated signed url will contain this calculated signature and the expiration time:
    <url>?expires=<expiration_epoch_time>signature=<signature>

    Since we use hashing algorithm we need to place the expiration time in the url to have everything later
    to verify the url.

    If the user changes the expiration time in the url, the calculated signature during the verification will differ,
    so the url will be invalid.

    Using a secret key also makes sure that the user can't manipulate the url.

    :param url: url to sign
    :param method: HTTP method with the url will be used
    :expires_in: seconds until the url is valid
    :returns The generated signed url
    """
    expires = int(time.time() + datetime.timedelta(seconds=expires_in).total_seconds())
    url_parts = list(urlparse.urlparse(url))
    url_parts[2] = quote(url_parts[2])
    signature = _calc_hash(method, url_parts[1].rsplit(':', 1)[0], url_parts[2], expires)
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query['expires'] = expires
    query['signature'] = signature
    url_parts[4] = urlencode(query)
    return urlparse.urlunparse(url_parts)


def verify_signed_url(url, method):
    """
    Verify the given signed url.

    First we pops the signed url specific query params from the url (expires, signature) and then we calculate the
    hash like in `generate_signed_url` method.
    We compare the calculated hash and the given signature from the url. If they differ raise an APIPermissionException.
    If the signature is ok we can make sure that the expiration time is not manipulated.
    The last step is to check that the url is expired or not.

    :param url: url to verify
    :param method: HTTP method with the url was requested
    :raises APIPermissionException: If the signature is invalid or the url is expired
    :returns: `True` if the url is valid
    """
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    expires = int(query.pop('expires'))
    signature = query.pop('signature')
    url_parts[4] = urlencode(query)
    url = urlparse.urlunparse(url_parts)
    calc_signature = _calc_hash(method, url_parts[1].rsplit(':', 1)[0], url_parts[2], expires)
    if signature != calc_signature:
        raise errors.APIPermissionException('Invalid signature')
    if expires < time.time():
        raise errors.APIPermissionException('Expired signed url')

    return True


def _calc_hash(method, host, endpoint, expires):
    return hmac.new(
        str(config.get_config()['core']['signed_url_secret']),
        msg='{}:{}:{}:{}'.format(method, host, endpoint, expires),
        digestmod=hashlib.sha256
    ).hexdigest()
