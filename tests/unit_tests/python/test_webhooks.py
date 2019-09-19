import datetime
import json

import mock
import pytest
import pytz
import requests.exceptions

from api.web.encoder import custom_json_serializer
from api.webhooks.base import BaseWebhook
from api.webhooks.virus_scan import VirusScanWebhook, signed_urls


def test_base_webhook():
    webhook = BaseWebhook([])
    # build request body is not implemented by default
    with pytest.raises(NotImplementedError):
        webhook.build_request_body()


def test_virus_scan_webhook(mocker):
    webhook = VirusScanWebhook('http://localhost/callback')
    mock_session = mocker.patch.object(webhook, 'session')
    mock_signed_urls = mocker.patch.object(signed_urls, 'generate_signed_url', return_value='http://localhost')

    file_attrs = {
        '_id': '0',
        'name': 'test.txt',
        'mimetype': 'application/pdf',
        'hash': 'some-hash'
    }
    file_attrs['created'] = file_attrs['modified'] = datetime.datetime.now()
    webhook.call(file_info=file_attrs, parent={'_id': '0000000', 'type': 'acquisition'})
    expected_data = {
        'file': file_attrs,
        'file_download_url': 'http://localhost',
        'response_url': 'http://localhost'
    }
    expected_data['file']['created'] = pytz.timezone('UTC').localize(expected_data['file']['created']).isoformat()
    expected_data['file']['modified'] = pytz.timezone('UTC').localize(expected_data['file']['modified']).isoformat()
    call_args, call_kwargs = mock_session.post.call_args_list[0]
    call_url = call_args[0]
    call_data = call_kwargs['data']

    assert call_url == 'http://localhost/callback'
    assert json.loads(call_data) == expected_data

    mock_response = mock.MagicMock()
    mock_response.content = 'Some error happened'
    mock_session.post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    # by default return failed responses if some happend
    failures = webhook.call(file_info=file_attrs, parent={'_id': '0000000', 'type': 'acquisition'})
    assert 'Some error happened' in failures[0].response.content
    # raises if raise_for_status kwrag is true
    with pytest.raises(requests.exceptions.HTTPError) as error:
        webhook.call(file_info=file_attrs, parent={'_id': '0000000', 'type': 'acquisition'}, raise_for_status=True)
    assert 'Some error happened' in error.value.response.content
