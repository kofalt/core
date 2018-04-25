
def years_to_secs(age):
    return age * 86400 * 365

def test_csv_data(name, rows=5, delim=','):
    result = [ 'name{0}value{0}value2'.format(delim) ]

    for i in range(rows):
        result.append('{1}{0}{2}{0}{3}'.format(delim, name, i, i*2))

    return '\r\n'.join(result)


def test_adhoc_data_view(data_builder, file_form, as_admin, as_user):
    from pprint import pprint

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

    project = data_builder.create_project(label='test-project')
    session1 = data_builder.create_session(project=project, subject=subject1, label='ses-01')
    session2 = data_builder.create_session(project=project, subject=subject2, label='ses-01')
    acquisition1 = data_builder.create_acquisition(session=session1, label='scout')
    acquisition2 = data_builder.create_acquisition(session=session2, label='scout')
    
    file_form1 = file_form(('values.csv', test_csv_data('a1')))
    assert as_admin.post('/acquisitions/' + acquisition1 + '/files', files=file_form1).ok

    file_form2 = file_form(('values.csv', test_csv_data('a2')))
    assert as_admin.post('/acquisitions/' + acquisition2 + '/files', files=file_form2).ok

    # Requires authorization
    r = as_user.post('/views/data?containerId={}'.format(project), json={
        "columns": [
            { "src": "subject.code", "dst": "subject" }
        ]
    })
    assert r.status_code == 403

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

    pprint(r.json())
    assert r.ok

