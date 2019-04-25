import datetime
import pytest

def test_get_tree_graph(as_public):
    r = as_public.get('/tree/graph')
    assert r.ok

    result = r.json()
    assert 'projects' in result

def test_fetch_tree_validation(as_admin):
    requests = [
        None,  # Body required
        {},  # No top-level keys
        {'subjects': {}},  # fields is required
        {'subjects': { 'fields': [] }, 'sessions': { 'fields': [] }},  #  Multiple top-level keys
        {'subjects': { 'fields': [], 'sessions': True }},  #  Invalid type for sessions
        {'job_tickets': { 'fields': [] }},  #  Invalid top-level type
    ]

    for request in requests:
        r = as_admin.post('/tree', json=request)
        if r.status_code != 400:
            pytest.fail('Expected request: {} to return a 400 Status Code, instead of {}'.format(request, r.status_code))

def test_fetch_tree_k(data_builder, as_admin):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session2 = data_builder.create_session(label='session2', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session)

    filter_str = 'parents.group={}'.format(group)

    # Empty retrieval
    r = as_admin.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': 'code=NOTEXIST'})
    assert r.ok
    assert len(r.json()) == 0

    # Simple retrieval
    r = as_admin.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok

    subjects = r.json()
    assert len(subjects) == 1

    assert subjects[0]['_id'] == subject
    assert subjects[0]['code'] == 'subject1'

    # Retrieve subject + session, sorted by id
    r = as_admin.post('/tree', json={'subjects': {
        'fields': ['code'],
        'sessions': {
            'fields': ['label', 'timestamp'],
            'sort': '_id:asc'
        }
    }}, params={'filter': filter_str})
    assert r.ok

    subjects = r.json()
    assert len(subjects) == 1

    assert len(subjects[0]['sessions']) == 2
    # swap order if random Ids are reversed
    if subjects[0]['sessions'][0]['_id'] != session:
        subjects[0]['sessions'][1], subjects[0]['sessions'][0] \
                = subjects[0]['sessions'][0], subjects[0]['sessions'][1]

    assert subjects[0]['sessions'][0]['_id'] == session
    assert subjects[0]['sessions'][0]['label'] == 'session1'
    assert 'subject' not in subjects[0]['sessions'][0]

    assert subjects[0]['sessions'][1]['_id'] == session2
    assert subjects[0]['sessions'][1]['label'] == 'session2'

    # Sessions with acquisitions
    r = as_admin.post('/tree', json={'sessions': {
        'fields': ['label'],
        'acquisitions': { 'fields': [], 'sort': '_id:desc' }
    }}, params={'filter': filter_str, 'sort': '_id:asc'})
    assert r.ok

    sessions = r.json()

    assert len(sessions) == 2
    if sessions[0]['_id'] != session:
        sessions[1], sessions[0] = sessions[0], sessions[1]
    assert sessions[0]['_id'] == session
    assert sessions[0]['label'] == 'session1'
    assert len(sessions[0]['acquisitions']) == 2
    # we cant be guranteed order based on id
    assert sessions[0]['acquisitions'][0]['_id'] in (acquisition, acquisition2)
    assert sessions[0]['acquisitions'][1]['_id'] in (acquisition, acquisition2)
    assert sessions[0]['acquisitions'][0]['_id'] != sessions[0]['acquisitions'][1]['_id']


    assert sessions[1]['_id'] == session2
    assert sessions[1]['label'] == 'session2'
    assert sessions[1]['acquisitions'] == []

    # 3 levels
    r = as_admin.post('/tree', json={'subjects': {
        'fields': ['code'],
        'sessions': {
            'fields': ['label', 'timestamp'],
            'sort': '_id:asc',
            'acquisitions': { 'fields': [], 'sort': '_id:desc' }
        }
    }}, params={'filter': filter_str})
    assert r.ok

    subjects = r.json()
    assert len(subjects) == 1
    sessions = subjects[0]['sessions']
    assert len(sessions) == 2
    if sessions[0]['_id'] != session:
        sessions[1], sessions[0] = sessions[0], sessions[1]

    assert sessions[0]['_id'] == session
    assert sessions[0]['label'] == 'session1'
    assert len(sessions[0]['acquisitions']) == 2

    assert sessions[0]['acquisitions'][0]['_id'] in (acquisition, acquisition2)
    assert sessions[0]['acquisitions'][1]['_id'] in (acquisition, acquisition2)
    assert sessions[0]['acquisitions'][0]['_id'] != sessions[0]['acquisitions'][1]['_id']

    assert sessions[1]['_id'] == session2
    assert sessions[1]['label'] == 'session2'
    assert sessions[1]['acquisitions'] == []

def test_fetch_tree_permissions(data_builder, as_admin, as_user, as_public):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(session=session)

    filter_str = 'parents.group={}'.format(group)

    # Simple retrieval
    r = as_public.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.status_code == 403

    # Masquerated as root
    r = as_user.post('/tree?root=true', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.status_code == 403

    r = as_user.post('/tree?exhaustive=true', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.status_code == 403

    # Retrieve as non-permissioned user
    r = as_user.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok
    assert not r.json()

    # Add user permissions to the project
    user_id = as_user.get('/users/self').json()['_id']
    assert as_admin.post('/projects/' + project + '/permissions', json={'_id': user_id, 'access': 'ro'}).ok

    # Retrieve as permissioned user
    r = as_user.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok
    subjects = r.json()
    assert len(subjects) == 1

    assert subjects[0]['_id'] == subject
    assert subjects[0]['code'] == 'subject1'

    # Remove "admin" permissions from project
    admin_user_id = as_admin.get('/users/self').json()['_id']
    assert as_admin.delete('/projects/' + project + '/permissions/' + admin_user_id).ok

    # Non-exhaustive list
    r = as_admin.post('/tree', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok
    assert not r.json()

    # Exhaustive lists
    r = as_admin.post('/tree?root=true', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok
    assert subjects == r.json()

    r = as_admin.post('/tree?exhaustive=true', json={'subjects': {'fields': ['code']}},
        params={'filter': filter_str})
    assert r.ok
    assert subjects == r.json()

def test_fetch_tree_filter_limit(data_builder, file_form, as_admin, as_root, api_db):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    session = data_builder.create_session(label='session1', project=project)
    session2 = data_builder.create_session(label='session1', project=project)
    acquisition = data_builder.create_acquisition(session=session, label='s1-acq1')
    acquisition2 = data_builder.create_acquisition(session=session, label='s1-acq2')
    acquisition3 = data_builder.create_acquisition(session=session2, label='s2-acq1')
    acquisition4 = data_builder.create_acquisition(session=session2, label='s2-acq2')

    filter_str = 'parents.group={}'.format(group)

    # Test filter acquisitions
    r = as_admin.post('/tree', json={'sessions': {
        'fields': ['label'],
        'acquisitions': {
            'fields': ['label'],
            'filter': 'label=~acq2$'  # Regex filter, matching *acq2
        }
    }}, params={'filter': filter_str})
    assert r.ok
    sessions = r.json()

    assert len(sessions) == 2
    assert sessions[0]['_id'] == session
    assert len(sessions[0]['acquisitions']) == 1
    assert sessions[0]['acquisitions'][0]['_id'] == acquisition2
    assert sessions[0]['acquisitions'][0]['label'] == 's1-acq2'

    assert sessions[1]['_id'] == session2
    assert len(sessions[1]['acquisitions']) == 1
    assert sessions[1]['acquisitions'][0]['_id'] == acquisition4
    assert sessions[1]['acquisitions'][0]['label'] == 's2-acq2'

    # Test limit acquisitions
    r = as_admin.post('/tree', json={'sessions': {
        'fields': ['label'],
        'acquisitions': {
            'fields': ['label'],
            'limit': 1,
            'sort': 'label:desc'
        }
    }}, params={'filter': filter_str})
    assert r.ok
    sessions = r.json()

    assert len(sessions) == 2
    assert sessions[0]['_id'] == session
    assert len(sessions[0]['acquisitions']) == 1
    assert sessions[0]['acquisitions'][0]['_id'] == acquisition2
    assert sessions[0]['acquisitions'][0]['label'] == 's1-acq2'

    assert sessions[1]['_id'] == session2
    assert len(sessions[1]['acquisitions']) == 1
    assert sessions[1]['acquisitions'][0]['_id'] == acquisition4
    assert sessions[1]['acquisitions'][0]['label'] == 's2-acq2'

def test_fetch_tree_parent(data_builder, as_admin):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    session2 = data_builder.create_session(label='session2', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(session=session)
    acquisition2 = data_builder.create_acquisition(session=session)

    filter_str = 'parents.group={}'.format(group)

    # Simple retrieval
    r = as_admin.post('/tree', json={'subjects': {
        'fields': ['code'],
        'project': { 'fields': ['label'] }
    }}, params={'filter': filter_str})
    assert r.ok

    subjects = r.json()
    assert len(subjects) == 1

    assert subjects[0]['_id'] == subject
    assert subjects[0]['code'] == 'subject1'

    assert subjects[0]['project']['_id'] == project
    assert subjects[0]['project']['label'] == 'project1'

    r = as_admin.post('/tree', json={'sessions': {
        'fields': ['label'],
        'group': { 'fields': ['label'] },
        'project': { 'fields': ['label'] },
        'subject': { 'fields': ['code'] },
    }}, params={'sort': '_id:asc', 'filter': filter_str})
    assert r.ok
    sessions = r.json()

    assert len(sessions) == 2

    if sessions[0]['_id'] != session:
        sessions[1], sessions[0] = sessions[0], sessions[1]

    assert sessions[0]['_id'] == session
    assert sessions[0]['label'] == 'session1'
    assert sessions[0]['group']['_id'] == group
    assert sessions[0]['group']['label'] == 'group1'
    assert sessions[0]['project']['_id'] == project
    assert sessions[0]['project']['label'] == 'project1'
    assert sessions[0]['subject']['_id'] == subject
    assert sessions[0]['subject']['code'] == 'subject1'

    assert sessions[1]['_id'] == session2
    assert sessions[1]['label'] == 'session2'
    assert sessions[1]['group']['_id'] == group
    assert sessions[1]['group']['label'] == 'group1'
    assert sessions[1]['project']['_id'] == project
    assert sessions[1]['project']['label'] == 'project1'
    assert sessions[1]['subject']['_id'] == subject
    assert sessions[1]['subject']['code'] == 'subject1'

def test_fetch_tree_files(data_builder, file_form, as_admin, as_root, api_db):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    session = data_builder.create_session(label='session1', project=project)
    acquisition = data_builder.create_acquisition(session=session)

    filter_str = 'parents.group={}'.format(group)

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test1.csv', meta={'name': 'test1.csv', 'type': 'csv'}))

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test2.csv', meta={'name': 'test2.csv', 'type': 'csv'}))

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test1.txt', meta={'name': 'test1.txt', 'type': 'text'}))

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test2.txt', meta={'name': 'test2.txt', 'type': 'text'}))

    # also a deleted file to make sure it doesn't show up
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'deleted_test.csv', meta={'name': 'deleted_test.csv', 'type': 'csv'}))
    r = as_admin.delete('/acquisitions/' + acquisition + '/files/deleted_test.csv')
    assert r.ok

    # All files
    # Permit sort & limit, not filtering
    r = as_admin.post('/tree', json={'acquisitions': {
        'fields': ['label'],
        'files': {
            'fields': ['name', 'size', 'type']
        }
    }}, params={'filter': filter_str})
    assert r.ok

    acquisitions = r.json()
    assert len(acquisitions) == 1

    assert len(acquisitions[0]['files']) == 4
    names = [ f['name'] for f in acquisitions[0]['files'] ]
    assert names == [ 'test1.csv', 'test2.csv', 'test1.txt', 'test2.txt' ]

    # Endpoint should include _id to be consistent
    assert '_id' in acquisitions[0]['files'][0]
    assert acquisitions[0]['files'][0]['size'] >= 1
    assert acquisitions[0]['files'][0]['type'] == 'csv'
    assert 'created' not in acquisitions[0]['files'][0]

    # Test sort & limit
    r = as_admin.post('/tree', json={'acquisitions': {
        'fields': ['label'],
        'files': {
            'sort': 'name:asc',
            'limit': 2,
            'fields': ['name', 'size', 'type']
        }
    }}, params={'filter': filter_str})
    assert r.ok

    acquisitions = r.json()
    assert len(acquisitions) == 1

    assert len(acquisitions[0]['files']) == 2
    names = [ f['name'] for f in acquisitions[0]['files'] ]
    assert names == [ 'test1.csv', 'test1.txt' ]

    # Test sort descending
    r = as_admin.post('/tree', json={'acquisitions': {
        'fields': ['label'],
        'files': {
            'sort': 'name:desc',
            'fields': ['name', 'size', 'type']
        }
    }}, params={'filter': filter_str})
    assert r.ok

    acquisitions = r.json()
    assert len(acquisitions) == 1

    names = [ f['name'] for f in acquisitions[0]['files'] ]
    assert names == [ 'test2.txt', 'test2.csv', 'test1.txt', 'test1.csv' ]

    # Test input validation
    # Only support single sort
    r = as_admin.post('/tree', json={'acquisitions': {
        'fields': ['label'],
        'files': {
            'sort': 'name:asc,modified:desc',
            'fields': ['name', 'size', 'type']
        }
    }}, params={'filter': filter_str})
    assert r.status_code == 400

    # Does not support filtering
    r = as_admin.post('/tree', json={'acquisitions': {
        'fields': ['label'],
        'files': {
            'filter': 'name=~csv$',
            'fields': ['name', 'size', 'type']
        }
    }}, params={'filter': filter_str})
    assert r.status_code == 400

def test_fetch_tree_analyses(data_builder, as_admin, file_form):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(label='acquisition1', session=session)

    filter_str = 'parents.group={}'.format(group)

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'input.csv', meta={'name': 'input.csv', 'type': 'csv'}))

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'input.txt', meta={'name': 'input.txt', 'type': 'txt'}))

    for container_type, container_id in [('projects', project), ('subjects', subject),
            ('sessions', session), ('acquisitions', acquisition)]:
        # Create ad-hoc analysis for container
        url = '/{}/{}/analyses'.format(container_type, container_id)
        r = as_admin.post(url, json={
            'label': 'analysis_label',
            'inputs': [
                {'type': 'acquisition', 'id': acquisition, 'name': 'input.csv'},
                {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'},
            ]
        })
        assert r.ok
        analysis_id = r.json()['_id']

        # Manual upload
        r = as_admin.post('/analyses/' + analysis_id + '/files', files=file_form('output1.csv', 'output2.csv', meta=[
            {'name': 'output1.csv', 'info': {'foo': 'foo'}},
            {'name': 'output2.csv', 'info': {'bar': 'bar'}},
        ]))
        assert r.ok

        # Then retrieve
        r = as_admin.post('/tree', json={container_type: {
            'fields': [],
            'analyses': {
                'fields': [ 'label' ],
                'inputs': {
                    'fields': ['name', 'size'],
                    'sort': 'name:desc'
                },
                'files': {
                    'fields': ['name', 'size'],
                    'limit': 1,
                    'sort': 'name:asc'
                }
            }
        }}, params={'filter': filter_str})
        assert r.ok

        containers = r.json()
        assert len(containers) == 1

        assert containers[0]['_id'] == container_id
        assert len(containers[0]['analyses']) == 1

        analysis = containers[0]['analyses'][0]
        assert analysis['_id'] == analysis_id
        assert analysis['label'] == 'analysis_label'
        assert len(analysis['inputs']) == 2
        assert analysis['inputs'][0]['name'] == 'input.txt'
        assert analysis['inputs'][1]['name'] == 'input.csv'
        assert len(analysis['files']) == 1
        assert analysis['files'][0]['name'] == 'output1.csv'

    # Test fetch of last 2 (session, acquisition) analyses
    r = as_admin.post('/tree', json={'analyses': {
        'fields': ['label'],
        'project': { 'fields': ['label'] },
        'session': { 'fields': ['label'] },
        'acquisition': { 'fields': ['label'] },
    }}, params={'filter': 'parents.session={}'.format(session), 'sort': '_id:asc'})
    assert r.ok

    analyses = r.json()
    assert len(analyses) == 2

    if analyses[0]['session']['_id'] != session:
        analyses[1], analyses[0] = analyses[0], analyses[1]

        assert analysis[0]['session']['_id'] == session
        assert analysis[0]['session']['label'] == 'session1'
        assert analyses[0]['acquisition'] == None

        assert analyses[1]['session']['_id'] == session
        assert analyses[1]['session']['label'] == 'session1'
        assert analyses[1]['acquisition']['_id'] == acquisition
        assert analyses[1]['acquisition']['label'] == 'acquisition1'


def test_fetch_tree_jobs(data_builder, default_payload, as_admin, file_form):
    # Dupe of test_queue.py
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'dicom': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)
    subject = data_builder.create_subject(code='subject1', project=project)
    session = data_builder.create_session(label='session1', project=project, subject={'_id': subject})
    acquisition = data_builder.create_acquisition(label='acquisition1', session=session)

    filter_str = 'parents.group={}'.format(group)

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(
        'test.zip', meta={'name': 'test.zip', 'type': 'zip'}))

    # Add a job to the acquisition
    job_data = {
        'gear_id': gear,
        'inputs': {
            'dicom': {
                'type': 'acquisition',
                'id': acquisition,
                'name': 'test.zip'
            }
        },
        'config': { 'two-digit multiple of ten': 20 },
        'destination': {
            'type': 'acquisition',
            'id': acquisition
        },
        'tags': [ 'test-tag' ]
    }

    r = as_admin.post('/jobs/add', json=job_data)
    assert r.ok
    job_id = r.json()['_id']

    r = as_admin.post('/tree', json={'projects': {
        'fields': ['label'],
        'jobs': { 'fields': [ 'gear_id', 'gear_info', 'created', 'state' ] }
    }}, params={'filter': filter_str})
    assert r.ok

    containers = r.json()
    assert len(containers) == 1

    assert containers[0]['label'] == 'project1'
    assert len(containers[0]['jobs']) == 1
    assert containers[0]['jobs'][0]['_id'] == job_id
    assert containers[0]['jobs'][0]['gear_id'] == gear
    assert containers[0]['jobs'][0]['state'] == 'pending'

    r = as_admin.post('/tree', json={'jobs': {
        'fields': [],
        'group': { 'fields': ['label'] },
        'project': { 'fields': ['label'] },
        'subject': { 'fields': ['code'] },
        'session': { 'fields': ['label'] },
        'acquisition': { 'fields': ['label'] },
        'analysis': { 'fields': ['label'] }
    }}, params={'filter': 'gear_id="{}"'.format(gear)})
    assert r.ok
    jobs = r.json()

    assert len(jobs) == 1

    assert jobs[0]['_id'] == job_id
    assert jobs[0]['group']['_id'] == group
    assert jobs[0]['group']['label'] == 'group1'
    assert jobs[0]['project']['_id'] == project
    assert jobs[0]['project']['label'] == 'project1'
    assert jobs[0]['subject']['_id'] == subject
    assert jobs[0]['subject']['code'] == 'subject1'
    assert jobs[0]['session']['_id'] == session
    assert jobs[0]['session']['label'] == 'session1'
    assert jobs[0]['acquisition']['_id'] == acquisition
    assert jobs[0]['acquisition']['label'] == 'acquisition1'
    assert jobs[0]['analysis'] == None

def test_fetch_tree_page_limits(data_builder, as_admin, file_form, api_db):
    group = data_builder.create_group(label='group1')
    project = data_builder.create_project(label='project1', group=group)

    filter_str = 'parents.group={}'.format(group)

    # Insert a bunch of subjects
    now = datetime.datetime.now()
    api_db.subjects.insert_many([{
        'code': 's{:04}'.format(i),
        'label': 's{:04}'.format(i),
        'project': project,
        'parents': {
            'group': group,
            'project': project
        },
        'created': now,
        'modified': now
    } for i in range(60)])

    try:
        r = as_admin.post('/tree?root=true', json={'subjects': {
            'fields': ['code'],
        }}, params={'filter': filter_str})
        assert r.ok
        assert len(r.json()) == 50

        r = as_admin.post('/tree?root=true', json={'subjects': {
            'fields': ['code'],
        }}, params={'filter': filter_str, 'limit': 100})
        assert r.ok
        assert len(r.json()) == 50

        r = as_admin.post('/tree?root=true', json={'subjects': {
            'fields': ['code'],
        }}, params={'filter': filter_str, 'limit': 10})
        assert r.ok
        assert len(r.json()) == 10
    finally:
        api_db.subjects.remove({'project': project})
