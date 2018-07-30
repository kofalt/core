import datetime
import os
import sys

import bson
import copy
import pytest
import pytz


@pytest.fixture(scope='function')
def database(mocker):
    bin_path = os.path.join(os.getcwd(), 'bin')
    mocker.patch('sys.path', [bin_path] + sys.path)
    import database
    return database


def test_42(data_builder, api_db, as_admin, database):
    # Mimic old-style archived flag
    session = data_builder.create_session()
    session2 = data_builder.create_session()
    api_db.sessions.update_one({'_id': bson.ObjectId(session)}, {'$set': {'archived': True}})
    api_db.sessions.update_one({'_id': bson.ObjectId(session2)}, {'$set': {'archived': False}})

    # Verfiy archived session is not hidden anymore
    assert session  in [s['_id'] for s in as_admin.get('/sessions').json()]

    # Verify upgrade creates new-style hidden tag
    database.upgrade_to_42()
    session_data = as_admin.get('/sessions/' + session).json()
    assert 'archived' not in session_data
    assert 'hidden' in session_data['tags']

    # Verify archived was removed when false as well
    session_data = as_admin.get('/sessions/' + session2).json()
    assert 'archived' not in session_data


def test_43(data_builder, api_db, as_admin, file_form, database):
    # Create session and upload file for later use as analysis input
    session = data_builder.create_session()
    r = as_admin.post('/sessions/' + session + '/files', files=file_form('input.txt'))
    assert r.ok

    # Create ad-hoc analysis with input ref, then upload output
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'offline',
        'inputs': [{'type': 'session', 'id': session, 'name': 'input.txt'}]
    })
    assert r.ok
    analysis_id = r.json()['_id']
    r = as_admin.post('/analyses/' + analysis_id + '/files', files=file_form('output.txt', meta=[{'name': 'output.txt'}]))
    assert r.ok

    # Mimic old-style analysis input/output tags
    analyses = api_db.analyses.find({}, ['inputs', 'files'])
    for analysis in analyses:
        files = []
        for f_ref in analysis.get('inputs', []):
            f = api_db['files'].find_one({'_id': f_ref})
            f['input'] = True
            files.append(f)
        for f_ref in analysis.get('files', []):
            f = api_db['files'].find_one({'_id': f_ref})
            f['output'] = True
            files.append(f)
        api_db.analyses.update_one({'_id': analysis['_id']},
                                   {'$set': {'files': files},
                                    '$unset': {'inputs': ''}})

    # Verify upgrade gets rid of tags and separates inputs/files
    database.upgrade_to_43()
    analysis = api_db.analyses.find_one({'_id': bson.ObjectId(analysis_id)}, ['inputs', 'files'])
    assert 'inputs' in analysis
    assert len(analysis['inputs']) == 1
    assert 'input' not in analysis['inputs'][0]

    assert 'files' in analysis
    assert len(analysis['files']) == 1
    assert 'output' not in analysis['files'][0]

    # cleanup
    api_db.analyses.delete_one({'_id': bson.ObjectId(analysis_id)})


def test_45(data_builder, randstr, api_db, as_admin, database, file_form):

    # Set up files with measurements

    assert True

    containers = [
        ('collections',  data_builder.create_collection()),
        ('projects',     data_builder.create_project()),
        ('sessions',     data_builder.create_session()),
        ('acquisitions', data_builder.create_acquisition())
    ]

    for c in containers:
        assert as_admin.post('/{}/{}/files'.format(c[0], c[1]), files=file_form('test.csv')).ok
        assert as_admin.post('/{}/{}/files'.format(c[0], c[1]), files=file_form('test2.csv')).ok
        files = api_db[c[0]].find_one({'_id': bson.ObjectId(c[1])})['files']
        for f_ref in files:
            api_db['files'].update_one(
                {'_id': f_ref},
                {'$set': { # Mangoes ...
                    'files.0.measurements': ['diffusion', 'functional'],
                    'files.1.measurements': ['diffusion', 'functional']
                }})


    # Set up rules referencing measurements

    rule = {
        'all' : [
            {'type' : 'file.measurements', 'value' : 'diffusion'},
            {'type' : 'container.has-measurements', 'value' : 'tests', 'regex': True}
        ],
        'any' : [
            {'type' : 'file.measurements', 'value' : 'diffusion'},
            {'type' : 'container.has-measurements', 'value' : 'tests', 'regex': True}
        ],
        'name' : 'Run dcm2niix on dicom',
        'alg' : 'dcm2niix',
        'project_id' : 'site'
    }

    api_db.project_rules.insert(copy.deepcopy(rule))
    api_db.project_rules.insert(copy.deepcopy(rule))


    # Set up session templates referencing measurements

    t_project1 = data_builder.create_project()
    t_project2 = data_builder.create_project()

    template = {
        'session': {'subject': {'code': '^compliant$'}},
        'acquisitions': [{
            'minimum': 1,
            'files': [{
                'minimum': 2,
                'measurements': 'diffusion'
            }]
        }]
    }

    assert as_admin.post('/projects/' + t_project1 + '/template', json=template).ok
    assert as_admin.post('/projects/' + t_project2 + '/template', json=template).ok


    ### RUN UPGRADE

    database.upgrade_to_45()

    ####


    # Ensure files were updated
    for c in containers:
        files_refs = as_admin.get('/{}/{}'.format(c[0], c[1])).json()['files']
        files = api_db['files'].find({'_id': {'$in': files_refs}})
        for f in files:
            assert f['classification'] == {'Contrast': ['Diffusion', 'T2*'], 'Intent': ['Functional', 'Structural'], 'Custom': ['diffusion', 'functional']}


    # Ensure rules were updated
    rule_after = {
        'all' : [
            {'type' : 'file.classification', 'value' : 'diffusion'},
            {'type' : 'container.has-classification', 'value' : 'tests', 'regex': True}
        ],
        'any' : [
            {'type' : 'file.classification', 'value' : 'diffusion'},
            {'type' : 'container.has-classification', 'value' : 'tests', 'regex': True}
        ],
        'name' : 'Run dcm2niix on dicom',
        'alg' : 'dcm2niix'
    }

    rules = as_admin.get('/site/rules').json()
    for r in rules:
        r.pop('_id')
        assert r == rule_after


    # Ensure templates were updated
    template_after = {
        'session': {'subject': {'code': '^compliant$'}},
        'acquisitions': [{
            'minimum': 1,
            'files': [{
                'minimum': 2,
                'classification': 'diffusion'
            }]
        }]
    }
    for p in [t_project1, t_project2]:
        assert as_admin.get('/projects/' + p).json()['template'] == template_after

    ### CLEANUP

    api_db.modalities.delete_many({})


def test_47_and_48(api_db, data_builder, as_admin, file_form, database):
    # Create old device
    last_seen = datetime.datetime.utcnow().replace(microsecond=0)
    api_db.devices.insert_one({
        '_id': 'method_name',
        'method': 'method',
        'name': 'name',
        'last_seen': last_seen,
        'errors': [],
    })

    api_db.devices.insert_one({
        '_id': 'device_without_method',
        'last_seen': last_seen
    })

    # Create acq with files
    # * one with with above device as it's origin
    # * the other pointing to a device that doesn't exist
    acq_id = data_builder.create_acquisition()
    as_admin.post('/acquisitions/' + acq_id + '/files', files=file_form('a.txt'))
    as_admin.post('/acquisitions/' + acq_id + '/files', files=file_form('b.txt'))
    file_refs = api_db.acquisitions.find_one({'_id': bson.ObjectId(acq_id)})['files']
    files = list(api_db['files'].find({'_id': {'$in': file_refs}}))
    files[0]['origin'] = {'type': 'device', 'id': 'method_name'}
    files[1]['origin'] = {'type': 'device', 'id': 'missing_one'}
    api_db.acquisitions.update_one({'_id': bson.ObjectId(acq_id)}, {'$set': {'files': files}})

    # Test that devices are switched over to ObjectId via 47
    database.upgrade_to_47()
    device = api_db.devices.find_one({'type': 'method', 'name': 'name'})

    assert device
    device_id = device.get('_id')
    assert isinstance(device_id, bson.ObjectId)
    assert device == {
        '_id': device_id,
        'label': 'method_name',
        'type': 'method',
        'name': 'name',
        'last_seen': last_seen,
        'errors': [],
    }

    device = api_db.devices.find_one({'type': 'device_without_method'})
    assert device
    assert device['label'] == 'device_without_method'
    assert device['type'] == 'device_without_method'

    def to_file_refs():
        # sync the files array with the collection otherwise the get will fail
        files = api_db.acquisitions.find_one({'_id': bson.ObjectId(acq_id)})['files']
        file_refs = []
        for f in files:
            _id = f['_id']
            del f['_id']
            api_db['files'].update_one(
                {'_id': _id},
                {'$set': f}
            )
            file_refs.append(_id)

        api_db.acquisitions.update_one({'_id': bson.ObjectId(acq_id)}, {'$set': {'files': file_refs}})

    to_file_refs()
    # Verify that ObjectId casting is no longer 500-ing with `join=origin`, even without
    # upgrade 48 fixing device origins.
    r = as_admin.get('/acquisitions/' + acq_id + '?join=origin')
    assert r.ok

    # prepare for upgrade 48
    file_refs = api_db.acquisitions.find_one({'_id': bson.ObjectId(acq_id)})['files']
    print(file_refs)
    files = list(api_db['files'].find({'_id': {'$in': file_refs}}))
    api_db.acquisitions.update_one({'_id': bson.ObjectId(acq_id)}, {'$set': {'files': files}})
    # Test that device origins get fixed via 48
    database.upgrade_to_48()
    device_id_str = str(device_id)
    files = api_db.acquisitions.find_one({'_id': bson.ObjectId(acq_id)})['files']
    assert files[0]['origin'] == {'type': 'device', 'id': device_id_str}

    # Look for id of new device
    added_device_id_str = files[1]['origin']['id']
    assert files[1]['origin'] == {'type': 'device', 'id': added_device_id_str}
    added_device = api_db.devices.find_one({'label': 'missing_one'})
    assert added_device['type'] == 'unknown'
    added_device['_id'] = added_device_id_str

    to_file_refs()
    # Verify that `join=origin` now works as intended
    r = as_admin.get('/acquisitions/' + acq_id + '?join=origin')
    assert r.ok
    assert r.json()['join-origin']['device'] == {
        device_id_str: {
            '_id': device_id_str,
            'label': 'method_name',
            'type': 'method',
            'name': 'name',
            'last_seen': pytz.timezone('UTC').localize(last_seen).isoformat(),
            'errors': [],
        },
        added_device_id_str: added_device
    }

def test_50(data_builder, api_db, as_admin, file_form, database):
    acquisition = data_builder.create_acquisition()
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test_file1.csv'))
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test_file2.csv'))
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test_file3.csv'))
    assert r.ok

    # Clean up modality
    r = as_admin.delete('/modalities/MR')

    payload = {
        '_id': 'MR',
        'classification': {
            'Intent': ["Structural", "Functional", "Localizer"],
            'Measurement': ["B0", "B1", "T1", "T2"]
        }
    }
    r = as_admin.post('/modalities', json=payload)
    assert r.ok

    r = as_admin.post('/acquisitions/' + acquisition + '/files/test_file1.csv/classification', json={
        'modality': 'MR',
        'replace': {
            'Intent': ['Structural'],
            'Measurement': ['T1'],
            'Custom': ['anatomy_t1w', 'foobar']
        }
    })
    assert r.ok

    r = as_admin.post('/acquisitions/' + acquisition + '/files/test_file2.csv/classification', json={
        'modality': 'MR',
        'replace': {
            'Intent': ['Functional'],
            'Measurement': ['T2'],
            'Custom': ['functional']
        }
    })
    assert r.ok

    # move back files from the files collection
    file_refs = api_db.acquisitions.find_one({'_id': bson.ObjectId(acquisition)})['files']
    files = list(api_db['files'].find({'_id': {'$in': file_refs}}).sort([('created', 1)]))
    api_db.acquisitions.update_one({'_id': bson.ObjectId(acquisition)}, {'$set': {'files': files}})

    database.upgrade_to_50()

    # Confirm that measurements is set and classification is updated
    r_acquisition = api_db.acquisitions.find_one({'_id': bson.ObjectId(acquisition)})
    f = r_acquisition['files'][0]
    assert f['name'] == 'test_file1.csv'
    assert f['classification'] == {
        'Intent': ['Structural'],
        'Measurement': ['T1'],
        'Custom': ['foobar']
    }
    assert f['measurements'] == ['anatomy_t1w']

    f = r_acquisition['files'][1]
    assert f['name'] == 'test_file2.csv'
    assert f['classification'] == {
        'Intent': ['Functional'],
        'Measurement': ['T2']
    }
    assert f['measurements'] == ['functional']

    f = r_acquisition['files'][2]
    assert f['name'] == 'test_file3.csv'
    assert f['classification'] == {}
    assert 'measurements' not in f

    # Create file refs
    files = api_db.acquisitions.find_one({'_id': bson.ObjectId(acquisition)})['files']
    file_refs = []
    for f in files:
        _id = f['_id']
        del f['_id']
        api_db['files'].update_one(
            {'_id': _id},
            {'$set': f}
        )
        file_refs.append(_id)

    api_db.acquisitions.update_one({'_id': bson.ObjectId(acquisition)}, {'$set': {'files': file_refs}})

    # Assert that changing modality resets measurements
    r = as_admin.put('/acquisitions/' + acquisition + '/files/test_file1.csv', json={
        'modality': None
    })
    assert r.ok

    # Assert that changing classification resets measurements
    r = as_admin.post('/acquisitions/' + acquisition + '/files/test_file2.csv/classification', json={
        'add': {
            'Custom': ['myvalue']
        }
    })
    assert r.ok

    r_acquisition = api_db.acquisitions.find_one({'_id': bson.ObjectId(acquisition)})
    f = api_db['files'].find_one({'_id': r_acquisition['files'][0]})
    assert f['name'] == 'test_file1.csv'
    assert f['classification'] == {
        'Custom': ['foobar']
    }
    assert 'measurements' not in f

    f = api_db['files'].find_one({'_id': r_acquisition['files'][1]})
    assert f['name'] == 'test_file2.csv'
    assert f['classification'] == {
        'Intent': ['Functional'],
        'Measurement': ['T2'],
        'Custom': ['myvalue']
    }
    assert 'measurements' not in f

    # Clean up modality
    r = as_admin.delete('/modalities/MR')
    assert r.ok

def test_52(data_builder, api_db, as_admin, file_form, database, default_payload):
    # Create a valid gear
    gear_doc = default_payload['gear']
    gear_doc['gear']['name'] = 'test-52-upgrade-gear'
    gear_doc['category'] = 'analysis'
    gear_id = api_db.gears.insert_one(gear_doc).inserted_id
    assert gear_id

    # Create project
    session = data_builder.create_session()

    # Create job with existing gear
    job_data = {
        'gear_id': str(gear_id),
        'inputs': {},
        'config': { 'two-digit multiple of ten': 20 },
    }

    job1_id = api_db.jobs.insert_one(job_data).inserted_id
    if '_id' in job_data:
        del job_data['_id']
    assert job1_id

    # Create analysis
    analysis_id = api_db.analyses.insert_one({
        'job': str(job1_id),
        'inputs': []
    }).inserted_id
    assert analysis_id

    # Create job with invalid gear id
    job_data['gear_id'] = '000000000000000000000000'
    job2_id = api_db.jobs.insert_one(job_data).inserted_id
    assert job2_id

    # Perform the upgrade
    database.upgrade_to_52()

    job1 = api_db.jobs.find_one({'_id': job1_id})
    gear_info = job1['gear_info']
    assert gear_info['name'] == 'test-52-upgrade-gear'
    assert gear_info['version'] == '0.0.1'
    assert gear_info['category'] == 'analysis'

    job2 = api_db.jobs.find_one({'_id': job2_id})
    assert 'gear_info' not in job2

    analysis = api_db.analyses.find_one({'_id': analysis_id})
    gear_info = analysis['gear_info']
    assert gear_info['id'] == str(gear_id)
    assert gear_info['name'] == 'test-52-upgrade-gear'
    assert gear_info['version'] == '0.0.1'
    assert gear_info['category'] == 'analysis'

    api_db.gears.delete_one({'_id': gear_id})
    api_db.analyses.delete_one({'_id': analysis_id})
    api_db.jobs.delete_one({'_id': job1_id})
    api_db.jobs.delete_one({'_id': job2_id})


def test_53():
    pass


def test_54(api_db, database):
    api_db.projects.delete_many({})
    api_db.sessions.delete_many({})
    api_db.acquisitions.delete_many({})
    api_db.analyses.delete_many({})
    api_db.collections.delete_many({})

    # Prepare database
    file_info = {
        "_id": "bf4f7a06-9f79-4b53-84ea-4f4897be45b8",
        "info": {},
        "hash": "foo-bar",
        "classification": {},
        "tags": [],
        "size": 989752,
        "mimetype": "application/zip",
        "name": "4784_1_1_localizer.dicom.zip",
    }

    acquisition = {"files": [file_info]}

    result = api_db.acquisitions.insert_one(acquisition)
    inserted_id = result.inserted_id

    # Perform the upgrade
    database.upgrade_to_54()

    r_acquisition = api_db.acquisitions.find_one({'_id': inserted_id})
    assert r_acquisition['files'][0] == acquisition['files'][0]['_id']

    r_file = api_db.files.find_one({'_id': r_acquisition['files'][0]})
    assert r_file

    # cleanup
    api_db.acquisitions.delete_one({'_id': acquisition['_id']})
    api_db.files.delete_one({'_id': file_info['_id']})

    # Test error handling

    file_info_no_id = {
        "info": {},
        "hash": "foo-bar",
        "classification": {},
        "tags": [],
        "size": 989752,
        "mimetype": "application/zip",
        "name": "4784_1_1_localizer.dicom.zip",
    }

    acquisition_2 = {"files": [file_info_no_id]}
    api_db.acquisitions.insert_one(acquisition_2)

    # Perform the upgrade
    with pytest.raises(Exception):
        database.upgrade_to_54()

    # cleanup
    api_db.acquisitions.delete_one({'_id': acquisition_2['_id']})

    acquisition_3 = {"files": [file_info]}
    api_db.acquisitions.insert_one(acquisition_3)

    # silently skip already inserted files
    analysis = {"inputs": [file_info]}
    api_db.analyses.insert_one(analysis)

    database.upgrade_to_54()

    r_analysis = api_db.analyses.find_one({'_id': analysis['_id']})
    assert r_analysis['inputs'][0] == analysis['inputs'][0]['_id']

    r_file = api_db.files.find({'_id': r_analysis['inputs'][0]})
    assert len(list(r_file)) == 1

    # cleanup
    api_db.acquisitions.delete_one({'_id': acquisition_3['_id']})
    api_db.analyses.delete_one({'_id': analysis['_id']})
    api_db.files.delete_one({'_id': file_info['_id']})