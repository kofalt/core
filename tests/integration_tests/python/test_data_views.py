import os
import zipfile
import gzip
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
    rows = r.json()
    assert len(rows) == 0

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
    rows = r.json()
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
    rows = r.json()
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
    rows = r.json()

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
    rows = r.json()

    assert len(rows) == 5

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['name'] == 'a1' 
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

def test_adhoc_data_view_csv_files_missing_data(data_builder, file_form, as_admin):
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
    rows = r.json()

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
    rows = r.json()

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
    rows = r.json()

    assert len(rows) == 5 

    for i in range(5):
        row = rows[i]

        assert row['subject'] == subject1['code']
        assert row['subject.age'] == subject1['age']
        assert row['subject.sex'] == subject1['sex']
        assert row['name'] == 'file2' 
        assert row['value'] == str(i)
        assert row['value2'] == str(2*i)

