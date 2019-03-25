def test_total(data_builder, as_admin, with_site_settings):
    a1 = data_builder.create_acquisition(label='a1')
    a2 = data_builder.create_acquisition(label='a2')

    r_list = as_admin.get('/acquisitions')
    assert r_list.ok
    acqs = r_list.json()

    r_page = as_admin.get('/acquisitions', headers={'X-Accept-Feature': 'pagination'})
    assert r_page.ok
    page = r_page.json()

    assert 'total' in page
    assert 'results' in page
    assert page['total'] == len(acqs)
    assert page['results'] == acqs

    r = as_admin.get('/gears', headers={'X-Accept-Feature': 'pagination'})
    assert r.ok
    assert r.json()['total'] == 0

    g_a0 = data_builder.create_gear(gear={'name': 'a', 'version': '0.0.0'})
    g_a1 = data_builder.create_gear(gear={'name': 'a', 'version': '1.0.0'})
    g_b0 = data_builder.create_gear(gear={'name': 'b', 'version': '0.0.0'})
    g_b1 = data_builder.create_gear(gear={'name': 'b', 'version': '1.0.0'})

    r_list = as_admin.get('/gears')
    assert r_list.ok
    gears = r_list.json()

    r_page = as_admin.get('/gears', headers={'X-Accept-Feature': 'pagination'})
    assert r_page.ok
    page = r_page.json()

    assert 'total' in page
    assert 'results' in page
    assert page['total'] == len(gears)
    assert page['results'] == gears


def test_limit(data_builder, as_admin, file_form, with_site_settings):
    assert as_admin.get('/users?limit=foo').status_code == 422
    assert as_admin.get('/users?limit=-1').status_code == 422

    u1 = data_builder.create_user()
    u2 = data_builder.create_user()
    assert len(as_admin.get('/users').json()) > 1
    assert len(as_admin.get('/users?limit=1').json()) == 1

    g1 = data_builder.create_group()
    g2 = data_builder.create_group()
    assert len(as_admin.get('/groups').json()) > 1
    assert len(as_admin.get('/groups?limit=1').json()) == 1

    p1 = data_builder.create_project()
    p2 = data_builder.create_project()
    assert len(as_admin.get('/projects').json()) > 1
    assert len(as_admin.get('/projects?limit=1').json()) == 1
    assert len(as_admin.get('/groups/' + g1 + '/projects').json()) > 1
    assert len(as_admin.get('/groups/' + g1 + '/projects?limit=1').json()) == 1

    s1 = data_builder.create_session()
    s2 = data_builder.create_session()
    assert len(as_admin.get('/sessions').json()) > 1
    assert len(as_admin.get('/sessions?limit=1').json()) == 1
    assert len(as_admin.get('/projects/' + p1 + '/sessions').json()) > 1
    assert len(as_admin.get('/projects/' + p1 + '/sessions?limit=1').json()) == 1

    aq1 = data_builder.create_acquisition()
    aq2 = data_builder.create_acquisition()
    assert len(as_admin.get('/acquisitions').json()) > 1
    assert len(as_admin.get('/acquisitions?limit=1').json()) == 1
    assert len(as_admin.get('/sessions/' + s1 + '/acquisitions').json()) > 1
    assert len(as_admin.get('/sessions/' + s1 + '/acquisitions?limit=1').json()) == 1

    an1 = as_admin.post('/sessions/' + s1 + '/analyses', files=file_form(
        'a.csv', meta={'label': 'no-job', 'inputs': [{'name': 'a.csv'}]})).json()['_id']
    an2 = as_admin.post('/sessions/' + s1 + '/analyses', files=file_form(
        'b.csv', meta={'label': 'no-job', 'inputs': [{'name': 'b.csv'}]})).json()['_id']
    assert len(as_admin.get('/sessions/' + s1 + '/analyses').json()) > 1
    assert len(as_admin.get('/sessions/' + s1 + '/analyses?limit=1').json()) == 1

    c1 = data_builder.create_collection()
    c2 = data_builder.create_collection()
    assert len(as_admin.get('/collections').json()) > 1
    assert len(as_admin.get('/collections?limit=1').json()) == 1

    g_a0 = data_builder.create_gear(gear={'name': 'a', 'version': '0.0.0'})
    g_a1 = data_builder.create_gear(gear={'name': 'a', 'version': '1.0.0'})
    g_b0 = data_builder.create_gear(gear={'name': 'b', 'version': '0.0.0'})
    g_b1 = data_builder.create_gear(gear={'name': 'b', 'version': '1.0.0'})
    assert len(as_admin.get('/gears').json()) > 1
    assert len(as_admin.get('/gears?limit=1').json()) == 1

    rule_doc = {'gear_id': g_a1, 'name': 'foo', 'any': [{'type': 'file.type', 'value': 'dicom', 'regex': False}], 'all': [], 'not': []}
    r1 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    r2 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    assert len(as_admin.get('/site/rules').json()) > 1
    assert len(as_admin.get('/site/rules?limit=1').json()) == 1

    assert as_admin.post('/acquisitions/' + aq1 + '/files', files=file_form('test.txt')).ok
    batch_json = {'gear_id': g_a1, 'targets': [{'type': 'acquisition', 'id': aq1}]}
    b1 = as_admin.post('/batch', json=batch_json).json()['_id']
    b2 = as_admin.post('/batch', json=batch_json).json()['_id']
    assert len(as_admin.get('/batch').json()) > 1
    assert len(as_admin.get('/batch?limit=1').json()) == 1

    job_json = {
        'gear_id': g_a1,
        'inputs': {'text': {'type': 'acquisition', 'id': aq1, 'name': 'test.txt'}},
        'destination': {'type': 'acquisition', 'id': aq2}}
    j1 = as_admin.post('/jobs/add', json=job_json).json()['_id']
    j2 = as_admin.post('/jobs/add', json=job_json).json()['_id']
    assert len(as_admin.get('/jobs').json()) > 1
    assert len(as_admin.get('/jobs?limit=1').json()) == 1

    assert as_admin.delete('/site/rules/' + r1).ok
    assert as_admin.delete('/site/rules/' + r2).ok


def test_page(data_builder, as_admin, with_site_settings):
    assert as_admin.get('/users?page=foo').status_code == 422
    assert as_admin.get('/users?page=-1').status_code == 422

    a = data_builder.create_acquisition(label='a')
    b = data_builder.create_acquisition(label='b')

    r = as_admin.get('/acquisitions?limit=1&page=1')
    assert {aq['_id'] for aq in r.json()} == {a}

    r = as_admin.get('/acquisitions?limit=1&page=2')
    assert {aq['_id'] for aq in r.json()} == {b}

    r = as_admin.get('/acquisitions?limit=1&page=3')
    assert {aq['_id'] for aq in r.json()} == set()


def test_skip(data_builder, as_admin, with_site_settings):
    assert as_admin.get('/users?skip=foo').status_code == 422
    assert as_admin.get('/users?skip=-1').status_code == 422

    a = data_builder.create_acquisition(label='a')
    b = data_builder.create_acquisition(label='b')

    r = as_admin.get('/acquisitions')
    assert {aq['_id'] for aq in r.json()} == {a, b}

    r = as_admin.get('/acquisitions?skip=1')
    assert {aq['_id'] for aq in r.json()} == {b}


def test_sort(data_builder, as_admin, with_site_settings):
    assert as_admin.get('/acquisitions?sort=label:foo').status_code == 422

    a1 = data_builder.create_acquisition(label='a')
    b1 = data_builder.create_acquisition(label='b')
    c1 = data_builder.create_acquisition(label='c')

    r = as_admin.get('/acquisitions?sort=label:1')
    assert [a['_id'] for a in r.json()] == [a1, b1, c1]
    assert as_admin.get('/acquisitions?sort=label:asc').json() == r.json()

    r = as_admin.get('/acquisitions?sort=label:-1')
    assert [a['_id'] for a in r.json()] == [c1, b1, a1]
    assert as_admin.get('/acquisitions?sort=label:desc').json() == r.json()

    a2 = data_builder.create_acquisition(label='a')
    b2 = data_builder.create_acquisition(label='b')
    c2 = data_builder.create_acquisition(label='c')

    r = as_admin.get('/acquisitions?sort=label:1,created:-1')
    assert [a['_id'] for a in r.json()] == [a2, a1, b2, b1, c2, c1]

    g_a0 = data_builder.create_gear(gear={'name': 'a', 'version': '0.0.0'})
    g_a1 = data_builder.create_gear(gear={'name': 'a', 'version': '1.0.0'})
    g_b0 = data_builder.create_gear(gear={'name': 'b', 'version': '0.0.0'})
    g_b1 = data_builder.create_gear(gear={'name': 'b', 'version': '1.0.0'})
    r = as_admin.get('/gears?sort=gear.name:-1')
    assert [g['_id'] for g in r.json()] == [g_b1, g_a1]


def test_filter(data_builder, as_admin, with_site_settings):
    assert as_admin.get('/acquisitions?filter=foo').status_code == 422
    assert as_admin.get('/acquisitions?filter=label=a&filter=label=b').status_code == 422

    a = data_builder.create_acquisition(label='a')
    b = data_builder.create_acquisition(label='b')
    c = data_builder.create_acquisition(label='c')

    r = as_admin.get('/acquisitions?filter=label<b')
    assert {aq['_id'] for aq in r.json()} == {a}

    r = as_admin.get('/acquisitions?filter=label<=b')
    assert {aq['_id'] for aq in r.json()} == {a, b}

    r = as_admin.get('/acquisitions?filter=label=b')
    assert {aq['_id'] for aq in r.json()} == {b}

    r = as_admin.get('/acquisitions?filter=label!=b')
    assert {aq['_id'] for aq in r.json()} == {a, c}

    r = as_admin.get('/acquisitions?filter=label>=b')
    assert {aq['_id'] for aq in r.json()} == {b, c}

    r = as_admin.get('/acquisitions?filter=label=~(a|c)')
    assert {aq['_id'] for aq in r.json()} == {a, c}

    r = as_admin.get('/acquisitions?filter=label=~[ab]')
    assert {aq['_id'] for aq in r.json()} == {a, b}

    r = as_admin.get('/acquisitions?filter=label>b')
    assert {aq['_id'] for aq in r.json()} == {c}

    r = as_admin.get('/acquisitions?filter=label>a,label<c')
    assert {aq['_id'] for aq in r.json()} == {b}

    r = as_admin.get('/acquisitions?filter=_id=' + b)
    assert {aq['_id'] for aq in r.json()} == {b}

    # Filter for unset/null
    r = as_admin.get('/acquisitions?filter=uid=null')
    assert {aq['_id'] for aq in r.json()} == {a, b, c}

    b_created = as_admin.get('/acquisitions/' + b).json()['created'][:-6]
    r = as_admin.get('/acquisitions?filter=created=' + b_created)
    assert {aq['_id'] for aq in r.json()} == {b}

    # Force string match
    dec = data_builder.create_acquisition(label='1001')

    r = as_admin.get('/acquisitions?filter=label=1001')
    assert len(r.json()) == 0

    r = as_admin.get('/acquisitions?filter=label="1001"')
    assert {aq['_id'] for aq in r.json()} == {dec}

    r = as_admin.get('/gears?filter=single_input')
    assert r.ok

    g_a0 = data_builder.create_gear(gear={'name': 'a', 'version': '0.0.0'})
    g_a1 = data_builder.create_gear(gear={'name': 'a', 'version': '1.0.0'})
    g_b0 = data_builder.create_gear(gear={'name': 'b', 'version': '0.0.0'})
    g_b1 = data_builder.create_gear(gear={'name': 'b', 'version': '1.0.0'})
    r = as_admin.get('/gears?filter=gear.name=a')
    assert r.ok
    assert {g['_id'] for g in r.json()} == {g_a1}


def test_after_id(data_builder, as_admin, file_form, with_site_settings):
    assert as_admin.get('/users?after_id=foo&after_id=bar').status_code == 422
    assert as_admin.get('/users?after_id=foo&sort=bar').status_code == 422

    u1 = data_builder.create_user()
    u2 = data_builder.create_user()
    users = sorted(u['_id'] for u in as_admin.get('/users').json())
    assert {u1, u2}.issubset(users)
    users_after = sorted(u['_id'] for u in as_admin.get('/users?after_id=' + u1).json())
    assert users_after == [u for u in users if u > u1]

    g1 = data_builder.create_group()
    g2 = data_builder.create_group()
    groups = sorted(g['_id'] for g in as_admin.get('/groups').json())
    assert {g1, g2}.issubset(groups)
    groups_after = sorted(g['_id'] for g in as_admin.get('/groups?after_id=' + g1).json())
    assert groups_after == [g for g in groups if g > g1]

    p1 = data_builder.create_project()
    p2 = data_builder.create_project()
    assert len(as_admin.get('/projects').json()) > 1
    assert len(as_admin.get('/projects?after_id=' + p1).json()) == 1
    assert len(as_admin.get('/groups/' + g1 + '/projects').json()) > 1
    assert len(as_admin.get('/groups/' + g1 + '/projects?after_id=' + p1).json()) == 1

    s1 = data_builder.create_session()
    s2 = data_builder.create_session()
    assert len(as_admin.get('/sessions').json()) > 1
    assert len(as_admin.get('/sessions?after_id=' + s1).json()) == 1
    assert len(as_admin.get('/projects/' + p1 + '/sessions').json()) > 1
    assert len(as_admin.get('/projects/' + p1 + '/sessions?after_id=' + s1).json()) == 1

    aq1 = data_builder.create_acquisition()
    aq2 = data_builder.create_acquisition()
    assert len(as_admin.get('/acquisitions').json()) > 1
    assert len(as_admin.get('/acquisitions?after_id=' + aq1).json()) == 1
    assert len(as_admin.get('/sessions/' + s1 + '/acquisitions').json()) > 1
    assert len(as_admin.get('/sessions/' + s1 + '/acquisitions?after_id=' + aq1).json()) == 1

    an1 = as_admin.post('/sessions/' + s1 + '/analyses', files=file_form(
        'a.csv', meta={'label': 'no-job', 'inputs': [{'name': 'a.csv'}]})).json()['_id']
    an2 = as_admin.post('/sessions/' + s1 + '/analyses', files=file_form(
        'b.csv', meta={'label': 'no-job', 'inputs': [{'name': 'b.csv'}]})).json()['_id']
    assert len(as_admin.get('/sessions/' + s1 + '/analyses').json()) > 1
    assert len(as_admin.get('/sessions/' + s1 + '/analyses?after_id=' + an1).json()) == 1

    c1 = data_builder.create_collection()
    c2 = data_builder.create_collection()
    assert len(as_admin.get('/collections').json()) > 1
    assert len(as_admin.get('/collections?after_id=' + c1).json()) == 1

    g_a0 = data_builder.create_gear(gear={'name': 'a', 'version': '0.0.0'})
    g_a1 = data_builder.create_gear(gear={'name': 'a', 'version': '1.0.0'})
    g_b0 = data_builder.create_gear(gear={'name': 'b', 'version': '0.0.0'})
    g_b1 = data_builder.create_gear(gear={'name': 'b', 'version': '1.0.0'})
    assert len(as_admin.get('/gears').json()) > 1
    assert as_admin.get('/gears?after_id=' + g_a1).status_code == 500
    # TODO enable after_id for /gears if needed
    # assert len(as_admin.get('/gears?after_id=' + g_a1).json()) == 1

    rule_doc = {'gear_id': g_a1, 'name': 'foo', 'any': [{'type': 'file.type', 'value': 'dicom', 'regex': False}], 'all': [], 'not': []}
    r1 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    r2 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    assert len(as_admin.get('/site/rules').json()) > 1
    assert len(as_admin.get('/site/rules?after_id=' + r1).json()) == 1

    assert as_admin.post('/acquisitions/' + aq1 + '/files', files=file_form('test.txt')).ok
    batch_json = {'gear_id': g_a1, 'targets': [{'type': 'acquisition', 'id': aq1}]}
    b1 = as_admin.post('/batch', json=batch_json).json()['_id']
    b2 = as_admin.post('/batch', json=batch_json).json()['_id']
    assert len(as_admin.get('/batch').json()) > 1
    assert len(as_admin.get('/batch?after_id=' + b1).json()) == 1

    job_json = {
        'gear_id': g_a1,
        'inputs': {'text': {'type': 'acquisition', 'id': aq1, 'name': 'test.txt'}},
        'destination': {'type': 'acquisition', 'id': aq2}}
    j1 = as_admin.post('/jobs/add', json=job_json).json()['_id']
    j2 = as_admin.post('/jobs/add', json=job_json).json()['_id']
    assert len(as_admin.get('/jobs').json()) > 1
    assert len(as_admin.get('/jobs?after_id=' + j1).json()) == 1

    assert as_admin.delete('/site/rules/' + r1).ok
    assert as_admin.delete('/site/rules/' + r2).ok
