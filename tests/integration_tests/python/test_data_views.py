import os
import bson
import csv
import json
import zipfile
import gzip
import collections
from StringIO import StringIO

def years_to_secs(age):
    return age * 86400 * 365

subject1 = {
    'code': '1001',
    'sex': 'male',
    'age': years_to_secs(27)
}

subject2 = {
    'code': '1002',
    'sex': 'female',
    'age': years_to_secs(33)
}

subject3 = {
    'code': '1003'
}

subjects = [subject1, subject2, subject3]

def csv_test_data(name, rows=5, delim=',', compress=False):
    result = [ 'name{0}value{0}value2'.format(delim) ]

    for i in range(rows):
        result.append('{1}{0}{2}{0}{3}'.format(delim, name, i, i*2))

    result = '\r\n'.join(result)

    if compress:
        sio = StringIO()
        gzf = gzip.GzipFile(fileobj=sio, mode='w')
        gzf.write(result)
        gzf.close()
        result = sio.getvalue()

    return result

def json_test_data(name, rows=5):
    output = []
    row_count = rows if rows else 1
    for i in range(row_count):
        output.append(collections.OrderedDict([
            ('name', name),
            ('aValue', i),
            ('value2', i*2)
        ]))

    if not rows:
        output = output[0]

    return json.dumps(output)

def zip_test_data(files=['dir1/file1.csv', 'dir2/file2.csv']):
    sio = StringIO()
    zf = zipfile.ZipFile(sio, 'w')

    for filename in files:
        root, _ext = os.path.splitext(filename)
        file_data = csv_test_data(os.path.basename(root))

        zf.writestr(filename, file_data)

    zf.close()
    return sio.getvalue()

def test_adhoc_data_view_permissions(data_builder, as_admin, as_user):
    project = data_builder.create_project(label='test-project')
    r = as_user.post('/views/data?containerId={}'.format(project), json={
        "columns": [
            { "src": "subject.code", "dst": "subject" }
        ]
    })
    assert r.status_code == 403

def test_adhoc_data_view_empty_result(data_builder, file_form, as_admin):
    # JSON
    project = data_builder.create_project(label='test-project')
    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'project.label', 'dst': 'project' },
            { 'src': 'acquisition.label', 'dst': 'acquisition' }
        ]
    })
    assert r.ok
    rows = r.json()['data']
    assert len(rows) == 0

    # JSON row-column
    r = as_admin.post('/views/data?containerId={}&format=json-row-column'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'project.label', 'dst': 'project' },
            { 'src': 'acquisition.label', 'dst': 'acquisition' }
        ]
    })
    assert r.ok
    data = r.json()['data']
    assert len(data['columns']) == 0
    assert len(data['rows']) == 0

def test_adhoc_data_view_metadata_only(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    session2 = data_builder.create_session(project=project, subject=subject2, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    acquisition2 = data_builder.create_acquisition(session=session2, label='scout')

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'project.label', 'dst': 'project' },
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' },
            { 'src': 'session.label', 'dst': 'session' },
            { 'src': 'acquisition.label', 'dst': 'acquisition' }
        ]
    })

    assert r.ok
    rows = r.json()['data']
    assert len(rows) == 2

    assert rows[0]['project'] == 'test-project'
    assert rows[0]['subject'] == subject1['code']
    assert rows[0]['subject.age'] == subject1['age']
    assert rows[0]['subject.sex'] == subject1['sex']
    assert rows[0]['session'] == 'ses-01'
    assert rows[0]['acquisition'] == 'scout'

    assert rows[1]['project'] == 'test-project'
    assert rows[1]['subject'] == subject2['code']
    assert rows[1]['subject.age'] == subject2['age']
    assert rows[1]['subject.sex'] == subject2['sex']
    assert rows[1]['session'] == 'ses-01'
    assert rows[1]['acquisition'] == 'scout'

def test_adhoc_data_view_session_target(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    session2 = data_builder.create_session(project=project, subject=subject2, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    acquisition2 = data_builder.create_acquisition(session=session2, label='scout')

    r = as_admin.post('/views/data?containerId={}'.format(session2), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'project.label', 'dst': 'project' },
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' },
            { 'src': 'session.label', 'dst': 'session' },
            { 'src': 'acquisition.label', 'dst': 'acquisition' }
        ]
    })

    assert r.ok
    rows = r.json()['data']
    assert len(rows) == 1

    assert rows[0]['project'] == 'test-project'
    assert rows[0]['subject'] == subject2['code']
    assert rows[0]['subject.age'] == subject2['age']
    assert rows[0]['subject.sex'] == subject2['sex']
    assert rows[0]['session'] == 'ses-01'
    assert rows[0]['acquisition'] == 'scout'

def test_adhoc_data_view_csv_files(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    session2 = data_builder.create_session(project=project, subject=subject2, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    acquisition2 = data_builder.create_acquisition(session=session2, label='scout')
    
    file_form1 = file_form(('values.csv', csv_test_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    file_form2 = file_form(('values.csv', csv_test_data('a2')))
    assert as_admin.post('/acquisitions/' + acquisition2 + '/files', files=file_form2).ok

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 10

    for i in range(2):
        name_value = 'a{}'.format(i+1)
        subject = subjects[i]
        for j in range(5):
            row = rows[i*5+j]

            assert row['subject'] == subject['code']
            assert row['subject.age'] == subject['age']
            assert row['subject.sex'] == subject['sex']
            assert row['name'] == name_value
            assert row['value'] == str(j)
            assert row['value2'] == str(2*j)

def test_adhoc_data_view_json_row_column_format(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.csv', csv_test_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}&format=json-row-column'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv' }
        }
    })

    assert r.ok
    data = r.json()['data']
    columns = data['columns']
    rows = data['rows']

    assert columns == ['subject', 'subject.age', 'subject.sex', 'name', 'value', 'value2']
    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row[0] == subject1['code']
        assert row[1] == subject1['age']
        assert row[2] == subject1['sex']
        assert row[3] == 'a1'
        assert row[4] == str(i)
        assert row[5] == str(2*i)

def test_adhoc_data_view_csv_format(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.csv', csv_test_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}&format=csv'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv' }
        }
    })

    assert r.ok
    body = StringIO(r.text)
    rows = list(csv.reader(body))
    columns = rows.pop(0)

    assert columns == ['subject', 'subject.age', 'subject.sex', 'name', 'value', 'value2']
    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row[0] == subject1['code']
        assert row[1] == str(subject1['age'])
        assert row[2] == subject1['sex']
        assert row[3] == 'a1'
        assert row[4] == str(i)
        assert row[5] == str(2*i)

def test_adhoc_data_view_tsv_format(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.csv', csv_test_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}&format=tsv'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv' }
        }
    })

    assert r.ok
    body = StringIO(r.text)
    rows = list(csv.reader(body, dialect='excel-tab'))
    columns = rows.pop(0)

    assert columns == ['subject', 'subject.age', 'subject.sex', 'name', 'value', 'value2']
    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row[0] == subject1['code']
        assert row[1] == str(subject1['age'])
        assert row[2] == subject1['sex']
        assert row[3] == 'a1'
        assert row[4] == str(i)
        assert row[5] == str(2*i)

def test_adhoc_data_view_tsv_file(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.tsv', csv_test_data('a1', delim='\t')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.tsv' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['name'] == 'a1' 
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

def test_adhoc_data_view_json_list_file(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.json', json_test_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.json' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['name'] == 'a1' 
        assert row['aValue'] == i
        assert row['value2'] == 2*i

def test_adhoc_data_view_json_dict_file(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('values.json', json_test_data('a1', rows=False)))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.json' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 1
    row = rows[0]
    assert row['subject'] == subject1['code']
    assert row['name'] == 'a1' 
    assert row['aValue'] == 0
    assert row['value2'] == 0

def test_adhoc_data_view_missing_data_csv_files(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    session2 = data_builder.create_session(project=project, subject=subject2, label='ses-01')
    session3 = data_builder.create_session(project=project, subject=subject3, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    acquisition2 = data_builder.create_acquisition(session=session2, label='scout')
    acquisition3 = data_builder.create_acquisition(session=session3, label='scout')
    
    file_form1 = file_form(('values.csv.gz', csv_test_data('a1', compress=True)))
    assert as_admin.post('/acquisitions/' + acquisition2 + '/files', files=file_form1).ok

    file_form2 = file_form(('values.csv.gz', csv_test_data('a2', compress=True)))
    assert as_admin.post('/acquisitions/' + acquisition3 + '/files', files=file_form2).ok

    # ============================
    # Default missing data strategy (replace values with null)
    # ============================
    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv.gz' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 11

    for i in range(2):
        name_value = 'a{}'.format(i+1)
        subject = subjects[i+1]
        for j in range(5):
            row = rows[i*5+j]

            assert row['subject'] == subject['code']
            assert row['subject.age'] == subject.get('age')
            assert row['subject.sex'] == subject.get('sex')
            assert row['name'] == name_value
            assert row['value'] == str(j)
            assert row['value2'] == str(2*j)

    # Subject with no file is last
    row = rows[10]
    assert row['subject'] == subject1['code']
    assert row['subject.age'] == subject1['age']
    assert row['subject.sex'] == subject1['sex']
    assert row['name'] == None
    assert row['value'] == None 
    assert row['value2'] == None

    # ============================
    # Drop rows missing data strategy
    # ============================
    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'missingDataStrategy': 'drop-row',
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.csv.gz' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 5
    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject2['code']
        assert row['subject.age'] == subject2.get('age')
        assert row['subject.sex'] == subject2.get('sex')
        assert row['name'] == 'a1'
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

def test_adhoc_data_view_zip_members(data_builder, file_form, as_admin):
    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    
    file_form1 = file_form(('data.zip', zip_test_data()))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'acquisition',
            'filter': { 'value': '*.zip' },
            'zipMember': { 'value': 'dir2/*.csv' }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 5 

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['subject.age'] == subject1['age']
        assert row['subject.sex'] == subject1['sex']
        assert row['name'] == 'file2' 
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

def test_adhoc_data_view_analyses_files(data_builder, file_form, as_admin, as_drone, api_db):
    project = data_builder.create_project(label='test-project')
    session = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    acquisition = data_builder.create_acquisition(session=session, label='scout')
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('input.csv')).ok

    gear1 = data_builder.create_gear(gear={'name': 'data-view-gear1', 'inputs': {'csv': {'base': 'file'}}})
    gear2 = data_builder.create_gear(gear={'name': 'data-view-gear2', 'inputs': {'csv': {'base': 'file'}}})

    # Create job-based analysis 1
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'analysis-1',
        'job': {'gear_id': gear1,
                'inputs': {'csv': {'type': 'acquisition', 'id': acquisition, 'name': 'input.csv'}}}
    })
    assert r.ok
    analysis1 = r.json()['_id']
    
    # Get job id
    r = as_admin.get('/analyses/' + analysis1)
    assert r.ok
    job1 = r.json().get('job')

    # Upload output file
    file_form1 = file_form(('values.csv', csv_test_data('a1')))
    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis1, 'job': job1},
        files=file_form1)
    assert r.ok

    # Create job-based analysis 2
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'second-analysis',
        'job': {'gear_id': gear2,
                'inputs': {'csv': {'type': 'acquisition', 'id': acquisition, 'name': 'input.csv'}}}
    })
    assert r.ok
    analysis2 = r.json()['_id']
    
    # Get job id
    r = as_admin.get('/analyses/' + analysis2)
    assert r.ok
    job2 = r.json().get('job')

    # Upload output file
    file_form2 = file_form(('values2.csv', csv_test_data('a2')))
    file_form3 = file_form(('values3.csv', csv_test_data('a3')))
    r = as_drone.post('/engine',
        params={'level': 'analysis', 'id': analysis2, 'job': job2},
        files=[
            ('file', file_form2['file']),
            ('file', file_form3['file'])
        ])
    assert r.ok

    # Execute data view, match on label
    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' }
        ],
        'fileSpec': {
            'container': 'session',
            'filter': { 'value': '*.csv' },
            'analysisFilter': {
                'label': { 'value': 'analysis*' }
            }
        }
    })

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 5 

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['subject.age'] == subject1['age']
        assert row['subject.sex'] == subject1['sex']
        assert row['name'] == 'a1' 
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

    # Execute data view, match on second label, multiple files
    r = as_admin.post('/views/data?containerId={}'.format(project), json={
        'includeIds': False,
        'includeLabels': False,
        'columns': [
            { 'src': 'subject.code', 'dst': 'subject' },
            { 'src': 'subject.age' },
            { 'src': 'subject.sex' },
            { 'src': 'analysis.label', 'dst': 'analysis' },
            { 'src': 'file.name', 'dst': 'filename' }
        ],
        'fileSpec': {
            'container': 'session',
            'filter': { 'value': '*.csv' },
            'match': 'all',
            'analysisFilter': {
                'label': { 'value': 'second-analysis' }
            }
        }
    })

    if not r.ok:
        from pprint import pprint
        pprint(r.json())

    assert r.ok
    rows = r.json()['data']

    assert len(rows) == 10

    for i in range(2):
        name_value = 'a{}'.format(i+2)
        filename = 'values{}.csv'.format(i+2)
        for j in range(5):
            row = rows[i*5+j]

            assert row['subject'] == subject1['code']
            assert row['subject.age'] == subject1['age']
            assert row['subject.sex'] == subject1['sex']
            assert row['filename'] == filename
            assert row['analysis'] == 'second-analysis' 
            assert row['name'] == name_value
            assert row['value'] == str(j)
            assert row['value2'] == str(2*j)

    api_db.analyses.delete_one({'_id': bson.ObjectId(analysis1)})
    api_db.analyses.delete_one({'_id': bson.ObjectId(analysis2)})


