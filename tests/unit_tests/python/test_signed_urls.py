import base64
import hashlib
import hmac
import urlparse
from urllib import quote, urlencode

import pytest
from api import signed_urls
from api.web import errors


def test_generate_signed_url(mocker):
    mock_time = mocker.patch.object(signed_urls.time, 'time', return_value=0)
    mock_config = mocker.patch.object(signed_urls.config, 'get_config', return_value={'core': {'signed_url_secret': 'secret'}})
    signed_url = signed_urls.generate_signed_url('http://localhost', expires_in=3601)
    signature = quote(base64.urlsafe_b64encode(hmac.new(
        'secret',
        msg='{}:{}:{}:{}'.format('GET', 'localhost', '', 3601),
        digestmod=hashlib.sha256
    ).digest()))
    assert signed_url == 'http://localhost?expires=3601&signature={}'.format(signature)

def test_verify_signed_url(mocker):
    # valid case
    mock_time = mocker.patch.object(signed_urls.time, 'time', return_value=0)
    mock_config = mocker.patch.object(signed_urls.config, 'get_config', return_value={'core': {'signed_url_secret': 'secret'}})
    signed_url = signed_urls.generate_signed_url('http://localhost')
    assert signed_urls.verify_signed_url(signed_url, 'GET')
    # wrong HTTP method
    with pytest.raises(errors.APIPermissionException) as error:
        assert signed_urls.verify_signed_url(signed_url, 'POST')
    assert 'Invalid signature' in str(error)
    # manipulated url -> changed path
    parsed_url = urlparse.urlparse(signed_url)
    parsed_url = parsed_url._replace(path='/some/other/path')
    url = urlparse.urlunparse(parsed_url)
    with pytest.raises(errors.APIPermissionException) as error:
        assert signed_urls.verify_signed_url(url, 'GET')
    assert 'Invalid signature' in str(error)
    # expired signature
    mock_time = mocker.patch.object(signed_urls.time, 'time', return_value=3601)
    with pytest.raises(errors.APIPermissionException) as error:
        signed_urls.verify_signed_url(signed_url, 'GET')
    assert 'Expired signed url' in str(error)
    # manipulated url -> invalid signature
    parsed_url = urlparse.urlparse(signed_url)
    query = dict(urlparse.parse_qsl(parsed_url.query))
    query['expires'] = 3900
    parsed_url = parsed_url._replace(query=urlencode(query))
    url = urlparse.urlunparse(parsed_url)
    with pytest.raises(errors.APIPermissionException) as error:
        signed_urls.verify_signed_url(url, 'GET')
    assert 'Invalid signature' in str(error)
