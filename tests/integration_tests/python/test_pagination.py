def test_limit(data_builder, as_admin, file_form):
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

    gear1 = data_builder.create_gear()
    gear2 = data_builder.create_gear()
    assert len(as_admin.get('/gears').json()) > 1
    assert len(as_admin.get('/gears?limit=1').json()) == 1

    rule_doc = {'alg': as_admin.get('/gears/' + gear1).json()['gear']['name'],
                'name': 'foo', 'any': [], 'all': []}
    r1 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    r2 = as_admin.post('/site/rules', json=rule_doc).json()['_id']
    assert len(as_admin.get('/site/rules').json()) > 1
    assert len(as_admin.get('/site/rules?limit=1').json()) == 1
    assert as_admin.delete('/site/rules/' + r1).ok
    assert as_admin.delete('/site/rules/' + r2).ok

    # TODO batch, job


def test_sort(data_builder, as_admin):
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


def test_filter(data_builder, as_admin):
    assert as_admin.get('/acquisitions?filter=foo').status_code == 422

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

    r = as_admin.get('/acquisitions?filter=label>b')
    assert {aq['_id'] for aq in r.json()} == {c}

    r = as_admin.get('/acquisitions?filter=label>a,label<c')
    assert {aq['_id'] for aq in r.json()} == {b}

    r = as_admin.get('/acquisitions?filter=_id=' + b)
    assert {aq['_id'] for aq in r.json()} == {b}

    b_created = as_admin.get('/acquisitions/' + b).json()['created'][:-6]
    r = as_admin.get('/acquisitions?filter=created=' + b_created)
    assert {aq['_id'] for aq in r.json()} == {b}
