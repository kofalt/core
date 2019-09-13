from urlparse import urljoin
import urlparse
from api import config, signed_urls


def test_virus_scan_handler(mocker, data_builder, as_public, file_form):
    # prepare
    mock_set_virus_scan_state = mocker.patch('api.callbacks.virus_scan_handler.liststorage.FileStorage.set_virus_scan_state')
    mock_exec_op = mocker.patch('api.callbacks.virus_scan_handler.liststorage.FileStorage.exec_op', return_value={'virus_scan': {'state': 'quarantined'}})
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

    signed_url = signed_urls.generate_signed_url(url, method='POST')
    parsed_url = urlparse.urlparse(signed_url)

    # valid request, clean
    r = as_public.post('/{}?{}'.format(endpoint, parsed_url.query), json={'state': 'clean'})
    assert r.ok
    mock_set_virus_scan_state.assert_called_with(_id='000000000000000000000000', query_params={'name': 'test.csv'}, state='clean')
    mock_set_virus_scan_state.reset_mock()

    # valid request, virus
    r = as_public.post('/{}?{}'.format(endpoint, parsed_url.query), json={'state': 'virus'})
    assert r.ok
    mock_set_virus_scan_state.assert_called_with(_id='000000000000000000000000', query_params={'name': 'test.csv'}, state='virus')

    # invalid payload
    r = as_public.post('/{}?{}'.format(endpoint, parsed_url.query), json={'state': 'wrong state'})
    assert not r.ok

    # state already set
    mock_exec_op.return_value = {'virus_scan': {'state': 'clean'}}
    r = as_public.post('/{}?{}'.format(endpoint, parsed_url.query), json={'state': 'virus'})
    assert not r.ok
