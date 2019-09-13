import base64
import hashlib
import hmac
import time
import urlparse
from urllib import quote, unquote, urlencode

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
    expires = int(time.time()) + expires_in
    parsed_url = urlparse.urlparse(url)
    parsed_url = parsed_url._replace(path=quote(parsed_url.path))  # parsed_url is a namedtuple
    host_name = parsed_url.netloc.rsplit(':', 1)[0]
    signature = _calc_hash(method, host_name, parsed_url.path, expires)
    query = dict(urlparse.parse_qsl(parsed_url.query))
    query['expires'] = expires
    query['signature'] = base64.urlsafe_b64encode(signature)
    parsed_url = parsed_url._replace(query=urlencode(query))
    return urlparse.urlunparse(parsed_url)


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
    parsed_url = urlparse.urlparse(url)
    query = dict(urlparse.parse_qsl(parsed_url.query))
    signature = query.pop('signature', None)
    expires = int(query.pop('expires', 0))
    if not (signature and expires):
        raise errors.APIPermissionException
    parsed_url = parsed_url._replace(path=quote(unquote(parsed_url.path)), query=urlencode(query))
    url = urlparse.urlunparse(parsed_url)
    host_name = parsed_url.netloc.rsplit(':', 1)[0]
    calc_signature = _calc_hash(method, host_name, parsed_url.path, expires)
    signature = base64.urlsafe_b64decode(unquote(signature))
    if not hmac.compare_digest(calc_signature, signature):
        raise errors.APIPermissionException('Invalid signature')
    if expires < time.time():
        raise errors.APIPermissionException('Expired signed url')
    return True


def _calc_hash(method, host, endpoint, expires):
    return hmac.new(
        str(config.get_config()['core']['signed_url_secret']),
        msg='{}:{}:{}:{}'.format(method, host, endpoint, expires),
        digestmod=hashlib.sha256
    ).digest()
