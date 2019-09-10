from urlparse import urljoin
import urlparse
from api import config, signed_urls


def test_virus_scan_handler(mocker, data_builder, as_public, file_form):
    # prepare
    mock_exec_op = mocker.patch('api.callbacks.virus_scan_handler.FileStorage.exec_op')
    acquisition_id = '000000000000000000000000'
    endpoint = 'callbacks/virus-scan/acquisitions/{}/files/test.csv'.format(acquisition_id)
    url = urljoin(
        config.get_config()['site']['api_url'].rstrip('/') + '/',
        endpoint
    )
    # permission denied without signature
    r = as_public.post('/' + endpoint, json={'state': 'clean'})
    assert not r.ok
    assert r.status_code == 403

    # valid request, clean
    signed_url = signed_urls.generate_signed_url(url, method='POST')
    url_parts = list(urlparse.urlparse(signed_url))
    r = as_public.post('/{}?{}'.format(endpoint, url_parts[4]), json={'state': 'clean'})
    assert r.ok
    mock_exec_op.assert_called_with('PUT', _id='000000000000000000000000', payload={'virus_scan.state': 'clean'}, query_params={'name': 'test.csv'})
    mock_exec_op.reset_mock()

    # valid request, virus
    r = as_public.post('/{}?{}'.format(endpoint, url_parts[4]), json={'state': 'virus'})
    assert r.ok
    mock_exec_op.assert_any_call('PUT', _id='000000000000000000000000', payload={'virus_scan.state': 'virus'}, query_params={'name': 'test.csv'})
    mock_exec_op.assert_any_call('DELETE', _id='000000000000000000000000', query_params={'name': 'test.csv'})

    # invalid payload
    r = as_public.post('/{}?{}'.format(endpoint, url_parts[4]), json={'state': 'wrong state'})
    assert not r.ok
