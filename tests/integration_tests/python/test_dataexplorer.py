def test_search_status(as_drone, as_user, as_public):

    r = as_user.get('/dataexplorer/search/status')
    assert r.ok
    assert r.json()['status'] == 'missing'

    as_mongoconnector_drone = as_drone
    as_mongoconnector_drone.headers.update({
        'X-SciTran-Method': "service-reporting",
        'X-SciTran-Name': "mongo-connector"
    })

    r = as_mongoconnector_drone.get('/devices')
    assert r.ok
    mongoconnector = [device for device in r.json() if device['name'] == 'mongo-connector'][0]
    mongoconnector_id = mongoconnector['_id']

    r = as_mongoconnector_drone.get('/devices/' + mongoconnector_id)
    assert r.ok
    mongoconnector_key = r.json()['key']

    as_drone.headers.update({
        'X-SciTran-Method': 'bootstrapper',
        'X-SciTran-Name': 'Bootstrapper'
    })

    as_mongoconnector = as_public
    as_mongoconnector.headers.update({'Authorization': 'scitran-user ' + mongoconnector_key})

    r = as_mongoconnector.put('/devices/self', json={'info': {'status': 'indexing'}})
    assert r.ok

    r = as_user.get('/dataexplorer/search/status')
    assert r.ok
    assert r.json()['status'] == 'indexing'

    r = as_mongoconnector.put('/devices/self', json={'info': {'status': 'up-to-date'}})
    assert r.ok

    r = as_user.get('/dataexplorer/search/status')
    assert r.ok
    assert r.json()['status'] == 'up-to-date'

def test_parse_query(as_public):
    r = as_public.post('/dataexplorer/search/parse', json={'structured_query': 'subject.code =~ ex8*'})
    assert r.ok
    assert r.json() == {'valid': True, 'errors': []}

    r = as_public.post('/dataexplorer/search/parse', json={'structured_query': 'subject.code ~~ ex8*'})
    assert r.ok
    assert r.json() == {'valid': False, 'errors': [{'line': 1, 'pos': 14, 'offset': 13, 'message': "Unknown operator: '~~'"}]}
