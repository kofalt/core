# coding=utf-8
import bson
import copy
import datetime
import json

import dateutil.parser
import pytest

def get_full_container(user, url, index):
    '''
    Helper function to get the full container when finding it in a list
    because containers don't return the info block and other fields when returned
    in a list
    '''
    cont_type = url.split('/')[-1]
    cont = user.get(url).json()[index]
    r = user.get('/' + cont_type + '/' + cont['_id'])
    assert r.ok
    return r.json()


# TODO switch to upload_file_form in all uid(-match)/label/reaper upload tests
# after #772 (coverage-low-hanging 3) gets merged to avoid conflict hell
@pytest.fixture(scope='function')
def upload_file_form(file_form, merge_dict, randstr):
    def create_form(**meta_override):
        prefix = randstr()
        names = ('project', 'subject', 'session', 'acquisition', 'unused')
        files = {name: '{}-{}.csv'.format(prefix, name) for name in names}
        meta = {
            'project': {
                'label': prefix + '-project-label',
                'files': [{'name': files['project']}],
                'tags': ['one', 'two']
            },
            'session': {
                'uid': prefix + '-session-uid',
                'label': prefix + '-session-label',
                'subject': {
                    'code': prefix + '-subject-code'
                },
                'files': [{'name': files['session']}],
                'tags': ['one', 'two']
            },
            'acquisition': {
                'uid': prefix + '-acquisition-uid',
                'label': prefix + '-acquisition-label',
                'files': [{'name': files['acquisition']}],
                'tags': ['one', 'two']
            }
        }
        if meta_override:
            merge_dict(meta, meta_override)
        return file_form(*files.values(), meta=meta)

    return create_form


def test_reaper_upload(data_builder, randstr, upload_file_form, file_form, as_admin, with_site_settings, as_root, as_user, as_device, api_db, as_drone):

    group_1 = data_builder.create_group()
    prefix = randstr()
    project_label_1 = prefix + '-project-label-1'
    session_uid = unicode(bson.ObjectId())

    project_1 = data_builder.create_project(label=project_label_1, group=group_1)

    # Due to the order of tests the upgrade to 65 may have changed the assumed site storage provider
    site_provider = api_db.singletons.find_one({'_id': 'site'})['providers']['storage']

    # reaper-upload files to group_1/project_label_1 using session_uid
    r = as_drone.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_1},
        project={'label': project_label_1},
        session={'uid': session_uid},
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)

    # reaper-upload files to group_1/project_label_1 using session_uid without any files
    form = upload_file_form(
        group={'_id': group_1},
        project={'label': project_label_1, "files":[]},
        session={'uid': session_uid+"1", "files":[], 'subject': {
                    'code': prefix + '-subject-code',
                    'files': []
                }}
    )
    r = as_device.post('/upload/reaper', files={"metadata": form.get("metadata")})
    assert r.status_code == 400

    # get session created by the upload
    project_1 = as_device.get('/groups/' + group_1 + '/projects').json()[0]['_id']

    sessions = as_device.get('/projects/' + project_1 + '/sessions').json()
    assert len(sessions) == 1
    created_session = as_device.get('/sessions/' + sessions[0]['_id']).json()
    assert created_session['parents']['group'] == group_1
    assert created_session['parents']['project'] == project_1
    session = created_session['_id']

    acquisitions = as_device.get('/sessions/' + session + '/acquisitions').json()
    assert len(acquisitions) == 1
    created_acq = acquisitions[0]
    assert created_acq['parents']['group'] == group_1
    assert created_acq['parents']['project'] == project_1
    assert created_acq['parents']['session'] == session

    assert len(as_device.get('/sessions/' + session).json()['files']) == 1

    # move session to group_2/project_2
    group_2 = data_builder.create_group()
    project_2 = data_builder.create_project(group=group_2, label=prefix + '-project-label-2')
    as_device.put('/sessions/' + session, json={'project': project_2})
    assert len(as_device.get('/projects/' + project_1 + '/sessions').json()) == 0
    assert len(as_device.get('/projects/' + project_2 + '/sessions').json()) == 1

    # reaper-upload files using existing session_uid and incorrect group/project
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_1},
        project={'label': project_label_1},
        session={'uid': session_uid},
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)

    # verify no new sessions were created and that group/project was ignored
    # NOTE uploaded project file is NOT stored in this scenario!
    assert len(as_device.get('/projects/' + project_1 + '/sessions').json()) == 0
    assert len(as_device.get('/projects/' + project_2 + '/sessions').json()) == 1

    # verify that acquisition creation/file uploads worked
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 2
    assert len(as_device.get('/sessions/' + session).json()['files']) == 2

    # No group or project given
    # Only drone can upload to unknown project
    r = as_admin.post('/upload/reaper', files=upload_file_form(
        group={'_id': ''},
        project={'label': ''},
        session={'uid': session_uid+'1'},
    ))
    assert not r.ok
    assert r.status_code == 403
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': ''},
        project={'label': ''},
        session={'uid': session_uid+'1'},
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)

    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unsorted' == project_list[0]['label']
    unknown_group_unsorted_project = project['_id']
    assert len(as_device.get('/projects/' + unknown_group_unsorted_project + '/sessions').json()) == 1

    # No group given
    # Only devices can upload to unknown groups
    r = as_admin.post('/upload/reaper', files=upload_file_form(
        group={'_id': ''},
        project={'label': project_label_1},
        session={'uid': session_uid+'2'},
    ))
    assert not r.ok
    assert r.status_code == 403
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': ''},
        project={'label': project_label_1},
        session={'uid': session_uid+'2'},
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)

    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    assert len(as_device.get('/projects/' + unknown_group_unsorted_project + '/sessions').json()) == 2

    # Group given but no project
    group_3 = data_builder.create_group()
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_3},
        project={'label': ''},
        session={'uid': session_uid+'3'},
    ))
    assert r.ok
    # get session created by the upload
    r = as_device.get('/groups/' + group_3 + '/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unsorted' == project_list[0]['label']
    unknown_project = project['_id']
    r = as_device.get('/projects/' + unknown_project + '/sessions')
    assert r.ok
    assert len(r.json()) == 1
    assert r.json()[0].get('label') == 'gr-{}_proj-_ses-{}'.format(group_3, session_uid + '3')

    # Group given but project is missed typed
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_3},
        project={'label': 'Miss-typed project'},
        session={'uid': session_uid+'4'},
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)
    # get session created by the upload
    r = as_device.get('/groups/' + group_3 + '/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unsorted' == project_list[0]['label']
    unknown_project = project['_id']
    assert len(as_device.get('/projects/' + unknown_project + '/sessions').json()) == 2

    # Group given but project is missed typed
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_3},
        project={'label': 'Miss-typed project'},
        session={'uid': session_uid+'4'},
    ))
    assert r.ok
    # get session created by the upload
    r = as_device.get('/groups/' + group_3 + '/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unsorted' == project_list[0]['label']
    unknown_project = project['_id']
    assert len(as_device.get('/projects/' + unknown_project + '/sessions').json()) == 2

    # Try uploading as user without permissions
    user_id = as_user.get('/users/self').json()['_id']
    r = as_device.post('/projects/' + unknown_project + '/permissions', json={'_id': user_id, 'access': 'ro'})
    r = as_user.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_3},
        project={'label': 'Miss-typed project'},
        session={'uid': session_uid+'4'},
    ))
    assert r.status_code == 403

    # Test reaper uploads for embedded subject metadata
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'_id': group_1},
        project={'label': project_label_1},
        session={
            'uid': session_uid + '5',
            'subject': {
                'code': 'embedded',
                'lastname': 'Lastname'
            }
        }
    ))
    assert r.ok
    files = r.json()
    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)


    # Test saving raw EM4 subject at session info
    sessions = as_device.get('/projects/' + project_1 + '/sessions').json()
    session_raw_subject_id = [s for s in sessions if s['uid'] == session_uid + '5'][0]['_id']
    session_raw_subject = as_device.get('/sessions/' + session_raw_subject_id).json()
    expected_raw_subject = {
        'lastname': 'Lastname'
    }
    assert session_raw_subject['info']['subject_raw'] == expected_raw_subject

    # Test reaper upload routing via group.label
    group_4 = data_builder.create_group(label='Group Label')
    project_4 = data_builder.create_project(group=group_4, label='Project Label')

    r = as_device.post('/upload/reaper', files=file_form('group.label.test.1', meta={
        'group': {'label': 'Group Label'},
        'project': {'label': 'Project Label'},
        'session': {'uid': 'group.label.test.1', 'label': 'Session Label'},
        'acquisition': {'uid': 'group.label.test.1', 'label': 'Acquisition Label',
                        'files': [{'name': 'group.label.test.1'}]},
    }))
    assert r.ok

    r = as_admin.post('/resolve', json={'path': [group_4, 'Project Label', 'Session Label', 'Acquisition Label']})
    assert r.ok

    acq_children = r.json()['children']
    assert len(acq_children) == 1
    assert acq_children[0]['name'] == 'group.label.test.1'

    # IF we have multiple similar matches then it should end up in the unknown group in the Unsorted project
    group_5 = data_builder.create_group(label='Group Labels')
    project_5 = data_builder.create_project(group=group_5, label='Project Label')
    r = as_device.post('/upload/reaper', files=file_form('group.label.test.2', meta={
        'group': {'label': 'Group Label'},
        'project': {'label': ''},
        'session': {'uid': 'group.label.test.2', 'label': 'Session Label'},
        'acquisition': {'uid': 'group.label.test.2', 'label': 'Acquisition Label',
                        'files': [{'name': 'group.label.test.2'}]},
    }))
    r = as_root.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    project = project_list[0]
    assert 'Unsorted' == project_list[0]['label']
    unknown_project = project['_id']
    sessions = as_root.get('/projects/' + unknown_project + '/sessions').json()
    found = False
    for ses in sessions:
        if ses['uid'] == 'group.label.test.2':
            found = True
    assert found == True


    r = as_admin.post('/resolve', json={'path': [group_5, 'Project Label', 'Session Label', 'Acquisition Label']})
    assert not r.ok
    r = as_admin.post('/resolve', json={'path': [group_5, 'Project Label', 'Session Label', 'Acquisition Label']})
    assert not r.ok

    r = as_device.post('/upload/reaper', files=file_form('group.label.test.3', meta={
        'group': {'label': 'Group Label'},
        'project': {'label': 'Project Label'},
        'session': {'uid': 'group.label.test.3', 'label': 'Session Label'},
        'acquisition': {'uid': 'group.label.test.3', 'label': 'Acquisition Label',
                        'files': [{'name': 'group.label.test.3'}]},
    }))
    assert r.ok

    # Change the name to not be similar anymore
    r = as_admin.put('/groups/' + group_5, json={'label': 'Not even close to similar'})
    assert r.ok

    #Now this will get placed into the group 4 tree
    r = as_device.post('/upload/reaper', files=file_form('group.label.test.4', meta={
        'group': {'label': 'Group Label'},
        'project': {'label': 'Project Label'},
        'session': {'uid': 'group.label.test.4', 'label': 'Session Label4'},
        'acquisition': {'uid': 'group.label.test.4', 'label': 'Acquisition Label4',
                        'files': [{'name': 'group.label.test.4'}]},
    }))
    assert r.ok
    r = as_admin.post('/resolve', json={'path': [group_4, 'Project Label', 'Session Label4', 'Acquisition Label4']})
    assert r.ok
    acq_children = r.json()['children']
    assert len(acq_children) == 1
    assert acq_children[0]['name'] == 'group.label.test.4'


    # And this group will be found and create the rest of the group_5 tree
    r = as_device.post('/upload/reaper', files=file_form('group.label.test.5', meta={
        'group': {'label': 'Not even close to similar'},
        'project': {'label': 'Project Label'},
        'session': {'uid': 'group.label.test.5', 'label': 'Session Label 5'},
        'acquisition': {'uid': 'group.label.test.5', 'label': 'Acquisition Label 5',
                        'files': [{'name': 'group.label.test.5'}]},
    }))
    assert r.ok
    r = as_admin.post('/resolve', json={'path': [group_5, 'Project Label', 'Session Label 5', 'Acquisition Label 5']})
    assert r.ok
    acq_children = r.json()['children']
    assert len(acq_children) == 1
    assert acq_children[0]['name'] == 'group.label.test.5'

    # Finally confirm it still works with similar names for the group 5 tree
    r = as_device.post('/upload/reaper', files=file_form('group.label.test.6', meta={
        'group': {'label': 'Not even close to simil'},
        'project': {'label': 'Project Label'},
        'session': {'uid': 'group.label.test.6', 'label': 'Session Label 6'},
        'acquisition': {'uid': 'group.label.test.6', 'label': 'Acquisition Label 6',
                        'files': [{'name': 'group.label.test.6'}]},
    }))
    assert r.ok
    r = as_admin.post('/resolve', json={'path': [group_5, 'Project Label', 'Session Label 6', 'Acquisition Label 6']})
    assert r.ok
    acq_children = r.json()['children']
    assert len(acq_children) == 1
    assert acq_children[0]['name'] == 'group.label.test.6'

    # No group label given
    project_label_2 = prefix + '-second-project-label-2'
    r = as_device.post('/upload/reaper', files=upload_file_form(
        group={'label': ''},
        project={'label': project_label_2},
        session={'uid': 'group.label.test.7'},
    ))
    assert r.ok
    files = r.json()

    # Device uploads should always go to the site provider
    assert files[0]['provider_id'] == str(site_provider)

    # get session created by the upload
    sessions = as_root.get('/projects/' + unknown_group_unsorted_project + '/sessions').json()
    found = False
    for ses in sessions:
        if ses['uid'] == 'group.label.test.7':
            found = True
    assert found == True

    # clean up
    data_builder.delete_group(group_1, recursive=True)
    data_builder.delete_group(group_2, recursive=True)
    data_builder.delete_group(group_3, recursive=True)
    data_builder.delete_group(group_4, recursive=True)
    data_builder.delete_group(group_5, recursive=True)
    data_builder.delete_project(unknown_group_unsorted_project, recursive=True)

def test_label_upload_unknown_group_project(data_builder, file_form, as_device, as_admin, as_drone):
    """
    If the label endpoint receives an upload with a blank group and project, set to
    group: unknown and create or find "Unknown" project
    """


    # Upload without group id or project label
    # Not allowed by users
    r = as_admin.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': ''},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert not r.ok
    assert r.status_code == 403
    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': ''},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok


    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unknown' == project_list[0]['label']
    unknown_project = project['_id']

    assert len(as_device.get('/projects/' + unknown_project + '/sessions').json()) == 1
    session = as_device.get('/projects/' + unknown_project + '/sessions').json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # Using the exhaustive flag get session created by the upload
    r = as_device.get('/groups/unknown/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unknown' == project_list[0]['label']
    unknown_project = project['_id']

    assert len(as_device.get('/projects/' + unknown_project + '/sessions', params={'exhaustive': True}).json()) == 1
    session = as_device.get('/projects/' + unknown_project + '/sessions', params={'exhaustive': True}).json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions', params={'exhaustive': True}).json()) == 1

    # do another upload without group id or project label
    r = as_drone.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': ''},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label_2',
            },
            'acquisition': {
                'label': 'test_acquisition_label_2',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # Test that another session was added to Unkonwn project
    assert len(as_device.get('/projects/' + unknown_project + '/sessions').json()) == 2
    session2 = as_device.get('/projects/' + unknown_project + '/sessions').json()[1]['_id']
    assert len(as_device.get('/sessions/' + session2 + '/acquisitions').json()) == 1

    # Using the exhaustive flag test that another session was added to Unkonwn project
    assert len(as_device.get('/projects/' + unknown_project + '/sessions', params={'exhaustive': True}).json()) == 2
    session2 = as_device.get('/projects/' + unknown_project + '/sessions', params={'exhaustive': True}).json()[1]['_id']
    assert len(as_device.get('/sessions/' + session2 + '/acquisitions', params={'exhaustive': True}).json()) == 1

    # Upload with a nonexistent group id and a project label
    # This should only work as drone due to the unknown upload ad-hoc restrictions
    r = as_admin.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': 'not_a_real_group'},
            'project': {
                'label': 'new_project',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert not r.ok
    assert r.status_code == 403
    r = as_drone.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': 'not_a_real_group'},
            'project': {
                'label': 'new_project',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # Try uploading 0 files
    r = as_device.post('/upload/label', files={"metadata":file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': 'not_a_real_group'},
            'project': {
                'label': 'new_project',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        }).get("metadata")}
    )
    assert r.status_code == 400


    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 2
    project = project_list[1]
    assert 'not_a_real_group_new_project' == project['label']
    named_unknown_project = project['_id']

    assert len(as_device.get('/projects/' + named_unknown_project + '/sessions').json()) == 1
    session = as_device.get('/projects/' + named_unknown_project + '/sessions').json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # get session created by the upload
    r = as_device.get('/groups/unknown/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 2
    project = project_list[1]
    assert 'not_a_real_group_new_project' == project['label']
    named_unknown_project = project['_id']

    assert len(as_device.get('/projects/' + named_unknown_project + '/sessions', params={'exhaustive': True}).json()) == 1
    session = as_device.get('/projects/' + named_unknown_project + '/sessions', params={'exhaustive': True}).json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions', params={'exhaustive': True}).json()) == 1

    group1 = data_builder.create_group()

    # Upload with an existing group id and no project label
    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': group1},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get session created by the upload
    r = as_device.get('/groups/' + group1 + '/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unknown' == project['label']
    project1 = project['_id']

    assert len(as_device.get('/projects/' + project1 + '/sessions').json()) == 1
    session = as_device.get('/projects/' + project1 + '/sessions').json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # get session created by the upload
    r = as_device.get('/groups/' + group1 + '/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert 'Unknown' == project['label']
    project1 = project['_id']

    assert len(as_device.get('/projects/' + project1 + '/sessions', params={'exhaustive': True}).json()) == 1
    session = as_device.get('/projects/' + project1 + '/sessions', params={'exhaustive': True}).json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions', params={'exhaustive': True}).json()) == 1

    # clean up
    data_builder.delete_group(group1, recursive=True)
    data_builder.delete_project(unknown_project, recursive=True)
    data_builder.delete_project(named_unknown_project, recursive=True)


def test_label_project_search(data_builder, file_form, as_admin, as_drone, as_device):
    """
    When attempting to find a project, we do a case insensitive lookup.
    Ensure that mongo regex works as expected.

    Scenario: three sessions come in with similar but different group labels
    and blank project lables.
    1 - "Test with more info"
    2 - "TeSt"
    3 - "test"

    Since neither of these groups exist by this id, they will be placed in the
    "unknown" group with the above string as their project label. Ensure the first
    is placed in a separate project than the second and third.
    """

    group_label_1 = 'Test with more info'
    group_label_2 = 'TeSt with longer string to avoid collision'
    group_label_3 = 'test with longer string to avoid collision'

    expected_project_label_1 = 'Test with more info_'
    expected_project_label_2 = 'TeSt with longer string to avoid collision_'

    # Upload with group 1
    r = as_drone.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': group_label_1},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok


    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert project_list[0]['label'] == expected_project_label_1
    project_1 = project['_id']

    assert len(as_device.get('/projects/' + project_1 + '/sessions').json()) == 1
    session = as_device.get('/projects/' + project_1 + '/sessions').json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # Using exhaustive flag get session created by the upload
    r = as_device.get('/groups/unknown/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 1
    project = project_list[0]
    assert project_list[0]['label'] == expected_project_label_1
    project_1 = project['_id']

    assert len(as_device.get('/projects/' + project_1 + '/sessions', params={'exhaustive': True}).json()) == 1
    session = as_device.get('/projects/' + project_1 + '/sessions', params={'exhaustive': True}).json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions', params={'exhaustive': True}).json()) == 1

    # Ensure group label 2 ends up in separate project
    r = as_drone.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': group_label_2},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label',
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 2

    # Order is not guaranteed
    if project_list[0]['_id'] == project_1:
        project = project_list[1]
    else:
        project = project_list[0]

    assert project['label'] == expected_project_label_2
    project_2 = project['_id']


    assert len(as_device.get('/projects/' + project_2 + '/sessions').json()) == 1
    session = as_device.get('/projects/' + project_2 + '/sessions').json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # Using exhaustive flag get session created by the upload
    r = as_device.get('/groups/unknown/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    assert len(project_list) == 2

    # Order is not guaranteed
    if project_list[0]['_id'] == project_1:
        project = project_list[1]
    else:
        project = project_list[0]

    assert project['label'] == expected_project_label_2
    project_2 = project['_id']

    assert len(as_device.get('/projects/' + project_2 + '/sessions', params={'exhaustive': True}).json()) == 1
    session = as_device.get('/projects/' + project_2 + '/sessions', params={'exhaustive': True}).json()[0]['_id']
    assert len(as_device.get('/sessions/' + session + '/acquisitions', params={'exhaustive': True}).json()) == 1

    # Upload with another "test" project with different case
    r = as_drone.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta={
            'group': {'_id': group_label_3},
            'project': {
                'label': '',
            },
            'session': {
                'label': 'test_session_label_2'
            },
            'acquisition': {
                'label': 'test_acquisition_label_2',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get session created by the upload
    r = as_device.get('/groups/unknown/projects')
    assert r.ok
    project_list = r.json()
    # Ensure there are still only 2 projects
    assert len(project_list) == 2

    # Order is not guaranteed
    if project_list[0]['_id'] == project_1:
        project = project_list[1]
    else:
        project = project_list[0]

    assert project['label'] == expected_project_label_2

    assert len(as_device.get('/projects/' + project_2 + '/sessions').json()) == 2
    session2 = as_device.get('/projects/' + project_2 + '/sessions').json()[1]['_id']
    assert len(as_device.get('/sessions/' + session2 + '/acquisitions').json()) == 1

    # Using exhaustive flag get session created by the upload
    r = as_device.get('/groups/unknown/projects', params={'exhaustive': True})
    assert r.ok
    project_list = r.json()
    # Ensure there are still only 2 projects
    assert len(project_list) == 2

    # Order is not guaranteed
    if project_list[0]['_id'] == project_1:
        project = project_list[1]
    else:
        project = project_list[0]

    assert project['label'] == expected_project_label_2

    assert len(as_device.get('/projects/' + project_2 + '/sessions', params={'exhaustive': True}).json()) == 2
    session2 = as_device.get('/projects/' + project_2 + '/sessions', params={'exhaustive': True}).json()[1]['_id']
    assert len(as_device.get('/sessions/' + session2 + '/acquisitions', params={'exhaustive': True}).json()) == 1


    # clean up
    data_builder.delete_group('unknown', recursive=True)


def test_reaper_reupload_deleted(data_builder, as_device, file_form, with_site_settings, api_db, randstr):

    label = randstr()
    group = data_builder.create_group(label=label)
    # use the same _ui for the discrete types, They will still be unique
    project = data_builder.create_project(label=label)
    reap_data = file_form('reaped.txt', meta={
        'group': {'_id': group},
        'project': {'label': label},
        'session': {'uid': group},
        'acquisition': {'uid': group,
                        'files': [{'name': 'reaped.txt'}]}
    })

    # reaper upload
    r = as_device.post('/upload/reaper', files=reap_data)
    assert r.ok

    ### test acquisition recreation
    # get + delete acquisition
    r = as_device.get('/acquisitions?filter=uid=' + group)
    assert r.ok
    acquisition = next(a['_id'] for a in r.json() if a['uid'] == group)

    r = as_device.get('/acquisitions?filter=uid=' + group, params={'exhaustive': True})
    assert r.ok
    acquisition = next(a['_id'] for a in r.json() if a['uid'] == group)

    r = as_device.delete('/acquisitions/' + acquisition)
    assert r.ok

    # reaper re-upload
    r = as_device.post('/upload/reaper', files=reap_data)
    assert r.ok

    # check new acquisition
    r = as_device.get('/acquisitions?filter=uid=' + group)
    assert r.ok
    assert next(a for a in r.json() if a['uid'] == group)

    r = as_device.get('/acquisitions?filter=uid=' + group, params={'exhaustive': True})
    assert r.ok
    assert next(a for a in r.json() if a['uid'] == group)

    ### test session recreation
    # get + delete session
    r = as_device.get('/sessions?filter=group=' + group)
    assert r.ok
    session = next(s['_id'] for s in r.json() if s['uid'] == group)

    r = as_device.get('/sessions?filter=group=' + group, params={'exhaustive': True})
    assert r.ok
    session = next(s['_id'] for s in r.json() if s['uid'] == group)

    r = as_device.delete('/sessions/' + session)
    assert r.ok

    # reaper re-upload
    r = as_device.post('/upload/reaper', files=reap_data)
    assert r.ok

    # check new session and acquisition
    r = as_device.get('/sessions?filter=group=' + group)
    assert r.ok
    assert next(s for s in r.json() if s['uid'] == group)

    r = as_device.get('/sessions?filter=group=' + group, params={'exhaustive': True})
    assert r.ok
    assert next(s for s in r.json() if s['uid'] == group)

    r = as_device.get('/acquisitions?filter=uid=' + group)
    assert r.ok
    assert next(a for a in r.json() if a['uid'] == group)

    r = as_device.get('/acquisitions?filter=uid=' + group, params={'exhaustive': True})
    assert r.ok
    assert next(a for a in r.json() if a['uid'] == group)

    # cleanup
    data_builder.delete_group(group, recursive=True)


def test_uid_upload(data_builder, file_form, as_device, as_user, as_public):
    group = data_builder.create_group()
    project3_id = data_builder.create_project()

    # try to uid-upload w/o logging in
    r = as_public.post('/upload/uid')
    assert r.status_code == 403

    # try to uid-upload w/o metadata
    r = as_device.post('/upload/uid', files=file_form('test.csv'))
    assert r.status_code == 400

    # NOTE unused.csv is testing code that discards files not referenced from meta
    uid_files = ('project.csv', 'subject.csv', 'session.csv', 'acquisition.csv', 'unused.csv')
    uid_meta = {
        'group': {'_id': group},
        'project': {
            'label': 'uid_upload',
            'files': [{'name': 'project.csv'}]
        },
        'session': {
            'uid': 'uid_upload',
            'subject': {
                'code': 'uid_upload'
            },
            'files': [{'name': 'session.csv'}]
        },
        'acquisition': {
            'uid': 'uid_upload',
            'files': [{'name': 'acquisition.csv'}]
        }
    }

    # try to uid-upload to new project w/o group rw perms
    r = as_user.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta))
    assert r.status_code == 403

    # try to uid-upload no files
    r = as_device.post('/upload/uid', files={"metadata": file_form(*uid_files, meta=uid_meta).get("metadata")})
    assert r.status_code == 400

    # uid-upload files
    r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta))
    assert r.ok

    # try to uid-upload to existing project w/o project rw perms
    uid_meta_2 = copy.deepcopy(uid_meta)
    uid_meta_2['session']['uid'] = uid_meta_2['acquisition']['uid'] = 'uid_upload_2'
    r = as_user.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta_2))
    assert r.status_code == 403

    # uid-upload to existing project but new session uid
    r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta_2))
    assert r.ok

    # uid-upload files to existing session uid
    r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta))
    assert r.ok

    # try uid-upload files to existing session uid w/ other user (having no rw perms on session)
    r = as_user.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta))
    assert r.status_code == 403

    #Upload to different project with same uid
    uid_meta_3 = copy.deepcopy(uid_meta)
    r = as_device.get('/projects/' + project3_id)
    assert r.ok
    uid_meta_3['project']['label'] = r.json()['label']
    r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta_3))
    assert r.ok
    r = as_device.get('/projects/' + project3_id + '/sessions')
    assert r.ok
    assert len(r.json()) > 0


    # TODO figure out why api.dao.hierarchy._group_id_fuzzy_match is NOT called below

    # # uid-upload to fat-fingered group id (should end up in group)
    # uid_meta_fuzzy = copy.deepcopy(uid_meta)
    # uid_meta_fuzzy['group']['_id'] = 'c' + group
    # r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta_fuzzy))
    # assert r.ok

    # # uid-upload to utterly non-existent group id (should end up in unknown group)
    # uid_meta_unknown = copy.deepcopy(uid_meta)
    # uid_meta_unknown['group']['_id'] = '0000000000000000000000000'
    # r = as_device.post('/upload/uid', files=file_form(*uid_files, meta=uid_meta_unknown))
    # assert r.ok

    # uid-match-upload files (to the same session and acquisition uid's as above)
    uid_match_meta = copy.deepcopy(uid_meta)
    del uid_match_meta['group']
    r = as_device.post('/upload/uid-match', files=file_form(*uid_files, meta=uid_match_meta))
    assert r.ok

    # try uid-match upload w/ other user (having no rw permissions on session)
    r = as_user.post('/upload/uid-match', files=file_form(*uid_files, meta=uid_match_meta))
    assert r.status_code == 403

    # try uid-match upload w/ non-existent acquisition uid
    uid_match_meta['acquisition']['uid'] = 'nonexistent_uid'
    r = as_device.post('/upload/uid-match', files=file_form(*uid_files, meta=uid_match_meta))
    assert r.status_code == 404

    # try uid-match upload w/ non-existent session uid
    uid_match_meta['session']['uid'] = 'nonexistent_uid'
    r = as_device.post('/upload/uid-match', files=file_form(*uid_files, meta=uid_match_meta))
    assert r.status_code == 404

    # delete group and children recursively (created by upload)
    data_builder.delete_group(group, recursive=True)


def test_label_upload(data_builder, file_form, as_device):
    group = data_builder.create_group()

    # label-upload files
    r = as_device.post('/upload/label', files=file_form(
        'project.csv', 'subject.csv', 'session.csv', 'acquisition.csv', 'unused.csv',
        meta={
            'group': {'_id': group},
            'project': {
                'label': 'test_project',
                'files': [{'name': 'project.csv'}]
            },
            'session': {
                'label': 'test_session_label',
                'subject': {
                    'code': 'test_subject_code',
                    'firstname': 'Name1',
                    'files': [{'name': 'subject.csv'}]
                },
                'files': [{'name': 'session.csv'}]
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get newly created project/session/acquisition
    project = as_device.get('/groups/' + group + '/projects').json()[0]['_id']
    subject = get_full_container(as_device, '/projects/' + project + '/subjects', 0)
    assert subject['firstname'] == 'Name1'

    session_id = as_device.get('/projects/' + project + '/sessions').json()[0]['_id']
    r = as_device.get('/sessions/' + session_id)
    assert r.ok
    session = r.json()

    assert session['parents']['group'] == group
    assert session['parents']['project'] == project
    assert session['info']['subject_raw'] == {'firstname': 'Name1'}

    acquisition = as_device.get('/sessions/' + session_id + '/acquisitions').json()[0]
    assert acquisition['parents']['group'] == group
    assert acquisition['parents']['project'] == project
    assert acquisition['parents']['session'] == session_id

    # label-upload files to a second session under the same subjects
    r = as_device.post('/upload/label', files=file_form(
        'project.csv', 'session.csv', 'acquisition.csv', 'unused.csv',
        meta={
            'group': {'_id': group},
            'project': {
                'label': 'test_project',
                'files': [{'name': 'project.csv'}]
            },
            'session': {
                'label': 'test_session2_label',
                'subject': {
                    'code': 'test_subject_code',
                    'firstname': 'Name2'  # Note that we don't upload a file here
                },
                'files': [{'name': 'session.csv'}]
            },
            'acquisition': {
                'label': 'test_acquisition_label',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get sessions
    project = as_device.get('/groups/' + group + '/projects').json()[0]['_id']
    subject = get_full_container(as_device, '/projects/' + project + '/subjects', 0)

    session = get_full_container(as_device, '/projects/' + project + '/sessions', 1)
    session2 = get_full_container(as_device, '/projects/' + project + '/sessions', 0)

    # Swap so that session represents test_session1
    if session['label'] == 'test_session2_label':
        session, session2 = session2, session
    session_id = session['_id']
    session2_id = session2['_id']

    assert subject['firstname'] == 'Name1'  # Because a file wasn't uploaded to a subject,
                                            # the name isn't overwritten

    assert session['parents']['group'] == group
    assert session['parents']['project'] == project
    assert session['info']['subject_raw'] == {'firstname': 'Name1'}

    assert session2['parents']['group'] == group
    assert session2['parents']['project'] == project
    assert session2['info']['subject_raw'] == {'firstname': 'Name2'}

    # label-upload files to the second session under the same subjects
    r = as_device.post('/upload/label', files=file_form(
        'project.csv', 'session.csv', 'acquisition.csv', 'unused.csv',
        meta={
            'group': {'_id': group},
            'project': {
                'label': 'test_project',
                'files': [{'name': 'project.csv'}]
            },
            'session': {
                'label': 'test_session2_label',
                'subject': {
                    'code': 'test_subject_code',
                    'firstname': 'Name3'  # Note that we don't upload a file here
                },
                'files': [{'name': 'session.csv'}]
            },
            'acquisition': {
                'label': 'test_acquisition_label2',
                'files': [{'name': 'acquisition.csv'}]
            }
        })
    )
    assert r.ok

    # get sessions and metadata shouldn't change for the sessions,
    # because neither of them were created by this upload
    project = as_device.get('/groups/' + group + '/projects').json()[0]['_id']
    subject = get_full_container(as_device, '/projects/' + project + '/subjects', 0)

    session = get_full_container(as_device, '/projects/' + project + '/sessions', 1)
    session2 = get_full_container(as_device, '/projects/' + project + '/sessions', 0)

    # Swap so that session represents test_session1
    if session['label'] == 'test_session2_label':
        session, session2 = session2, session
    session_id = session['_id']
    session2_id = session2['_id']

    assert subject['firstname'] == 'Name1'  # Because a file wasn't uploaded to a subject,
                                            # the name isn't overwritten

    assert session['parents']['group'] == group
    assert session['parents']['project'] == project
    assert session['info']['subject_raw'] == {'firstname': 'Name1'}

    assert session2['parents']['group'] == group
    assert session2['parents']['project'] == project
    assert session2['info']['subject_raw'] == {'firstname': 'Name2'}
    # delete group and children recursively (created by upload)
    data_builder.delete_group(group, recursive=True)


def test_master_subject_code_upload(data_builder, file_form, as_admin, as_device):
    group = data_builder.create_group()

    metadata = {
        'group': {'_id': group},
        'project': {
            'label': 'test_project'
        },
        'session': {
            'label': 'test_session_label',
            'subject': {
                'code': 'test_code',
                'master_code': 'non_existent'
            }
        },
        'acquisition': {
            'label': 'test_acquisition_label',
            'files': [{'name': 'acquisition.csv'}]
        }
    }
    # invalid master subject code
    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta=metadata)
    )
    assert r.status_code == 400

    # create a valid master subject code
    r = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': 'MRN-123456'
    })
    assert r.ok
    master_code_1 = r.json()['code']
    metadata['session']['subject']['master_code'] = master_code_1

    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta=metadata)
                      )
    assert r.ok

    # get newly created project/session/acquisition
    project = as_admin.get('/groups/' + group + '/projects').json()[0]['_id']
    subjects = as_admin.get('/projects/' + project + '/subjects').json()
    assert len(subjects) == 1
    assert subjects[0]['master_code'] == master_code_1

    sessions = as_admin.get('/projects/' + project + '/sessions').json()
    assert len(sessions) == 1

    acquisitions = as_admin.get('/sessions/' + sessions[0]['_id'] + '/acquisitions').json()
    assert len(acquisitions) == 1

    # upload the previous metadata, but use different master subject code and same subject code
    # it should fail
    # create a valid master subject code
    r = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': 'MRN-56789'
    })
    assert r.ok
    master_code_2 = r.json()['code']
    metadata['session']['subject']['master_code'] = master_code_2
    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta=metadata))
    assert r.status_code == 409

    # uploading a new file will go into the same subject if the master subject code is the same
    metadata['session']['subject']['master_code'] = master_code_1
    metadata['acquisition']['label'] = 'test_acquisition_label_2'
    r = as_device.post('/upload/label', files=file_form(
        'acquisition.csv',
        meta=metadata))
    assert r.ok

    # get newly created project/session/acquisition
    project = as_admin.get('/groups/' + group + '/projects').json()[0]['_id']
    subjects = as_admin.get('/projects/' + project + '/subjects').json()
    assert len(subjects) == 1
    assert subjects[0]['master_code'] == master_code_1

    sessions = as_admin.get('/projects/' + project + '/sessions').json()
    assert len(sessions) == 1

    acquisitions = as_admin.get('/sessions/' + sessions[0]['_id'] + '/acquisitions').json()
    assert len(acquisitions) == 2

    # delete group and children recursively (created by upload)
    data_builder.delete_group(group, recursive=True)


def test_multi_upload(data_builder, upload_file_form, randstr, as_device):
    # test uid-uploads respecting existing uids
    fixed_uid = randstr()
    fixed_uid_group = data_builder.create_group(_id=fixed_uid)
    fixed_uid_form_args = dict(
        group={'_id': fixed_uid_group},
        project={'label': fixed_uid + '-project-label'},
        session={'uid': fixed_uid + '-fixed-uid'},
        acquisition={'uid': fixed_uid + '-fixed-uid'},
    )

    # uid-upload #1 w/ fixed uid
    r = as_device.post('/upload/uid', files=upload_file_form(**fixed_uid_form_args))
    assert r.ok

    # get newly created project/session/acquisition
    project = as_device.get('/groups/' + fixed_uid_group + '/projects').json()[0]['_id']
    session = as_device.get('/projects/' + project + '/sessions').json()[0]['_id']
    acquisition = as_device.get('/sessions/' + session + '/acquisitions').json()[0]['_id']

    # test uploaded files
    assert len(as_device.get('/projects/' + project).json()['files']) == 1
    assert len(as_device.get('/sessions/' + session).json()['files']) == 1
    assert len(as_device.get('/acquisitions/' + acquisition).json()['files']) == 1

    # uid-upload #2 w/ fixed uid
    r = as_device.post('/upload/uid', files=upload_file_form(**fixed_uid_form_args))
    assert r.ok

    # test hierarchy (should have no new containers)
    assert len(as_device.get('/groups/' + fixed_uid_group + '/projects').json()) == 1
    assert len(as_device.get('/projects/' + project + '/sessions').json()) == 1
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # test uploaded files
    assert len(as_device.get('/projects/' + project).json()['files']) == 2
    assert len(as_device.get('/sessions/' + session).json()['files']) == 2
    assert len(as_device.get('/acquisitions/' + acquisition).json()['files']) == 2

    # label-upload w/ fixed uid
    r = as_device.post('/upload/label', files=upload_file_form(**fixed_uid_form_args))
    assert r.ok

    # test hierarchy (should have new session)
    assert len(as_device.get('/groups/' + fixed_uid_group + '/projects').json()) == 1
    assert len(as_device.get('/projects/' + project + '/sessions').json()) == 2

    # test label-uploads respecting existing labels
    # NOTE subject.code is also checked when label-matching sessions!
    fixed_label = randstr()
    fixed_label_group = data_builder.create_group(_id=fixed_label)
    fixed_label_form_args = dict(
        group={'_id': fixed_label_group},
        project={'label': fixed_label + '-project-label'},
        session={'label': fixed_label + '-fixed-label', 'subject': {'code': fixed_label + '-subject-code'}},
        acquisition={'label': fixed_label + '-fixed-label'},
    )

    # label-upload #1 w/ fixed label
    r = as_device.post('/upload/label', files=upload_file_form(**fixed_label_form_args))
    assert r.ok

    # get newly created project/session/acquisition
    project = as_device.get('/groups/' + fixed_label_group + '/projects').json()[0]['_id']
    session = as_device.get('/projects/' + project + '/sessions').json()[0]['_id']
    acquisition = as_device.get('/sessions/' + session + '/acquisitions').json()[0]['_id']

    # test uploaded files
    assert len(as_device.get('/projects/' + project).json()['files']) == 1
    assert len(as_device.get('/sessions/' + session).json()['files']) == 1
    assert len(as_device.get('/acquisitions/' + acquisition).json()['files']) == 1

    # label-upload #2 w/ fixed label
    r = as_device.post('/upload/label', files=upload_file_form(**fixed_label_form_args))
    assert r.ok

    # test hierarchy (should have no new containers)
    assert len(as_device.get('/groups/' + fixed_label_group + '/projects').json()) == 1
    assert len(as_device.get('/projects/' + project + '/sessions').json()) == 1
    assert len(as_device.get('/sessions/' + session + '/acquisitions').json()) == 1

    # test uploaded files
    assert len(as_device.get('/projects/' + project).json()['files']) == 2
    assert len(as_device.get('/sessions/' + session).json()['files']) == 2
    assert len(as_device.get('/acquisitions/' + acquisition).json()['files']) == 2

    # uid-upload w/ fixed label
    r = as_device.post('/upload/uid', files=upload_file_form(**fixed_label_form_args))
    assert r.ok

    # test hierarchy (should have new session)
    assert len(as_device.get('/groups/' + fixed_label_group + '/projects').json()) == 1
    assert len(as_device.get('/projects/' + project + '/sessions').json()) == 2

    # clean up
    data_builder.delete_group(fixed_uid_group, recursive=True)
    data_builder.delete_group(fixed_label_group, recursive=True)


def find_file_in_array(filename, files):
    for f in files:
        if f.get('name') == filename:
            return f


def test_engine_upload_errors(as_drone, as_user):
    # try engine upload w/ non-admin
    r = as_user.post('/engine')
    assert r.status_code == 402

    # try engine upload w/o level
    r = as_drone.post('/engine', params={})
    assert r.status_code == 400

    # try engine upload w/ invalid level
    r = as_drone.post('/engine', params={'level': 'what'})
    assert r.status_code == 400

    # try engine upload w/o id
    r = as_drone.post('/engine', params={'level': 'project'})
    assert r.status_code == 400


def test_acquisition_engine_upload(data_builder, file_form, as_admin, api_db):
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    assert as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('test.txt')).ok


    job = data_builder.create_job(inputs={
        'test': {'type': 'acquisition', 'id': acquisition, 'name': 'test.txt'}
    })

    metadata = {
        'project':{
            'label': 'engine project',
            'info': {'test': 'p'},
            'tags': ['one', 'two']
        },
        'session':{
            'label': 'engine session',
            'subject': {
                'code': 'engine subject',
                'sex': 'male',
                'age': 100000000000,
            },
            'info': {'test': 's', 'file.txt': 'Hello'},
            'tags': ['one', 'two']
        },
        'acquisition':{
            'label': 'engine acquisition',
            'timestamp': '2016-06-20T21:57:36+00:00',
            'info': {'test': 'a'},
            'files':[
                {
                    'name': 'one.csv',
                    'type': 'engine type 0',
                    'info': {'test': 'f0'}
                },
                {
                    'name': 'two.csv',
                    'type': 'engine type 1',
                    'info': {'test': 'f1'}
                }
            ],
            'tags': ['one', 'two']
        }
    }

    # try engine upload w/ non-existent job_id
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': '000000000000000000000000'},
        files=file_form('one.csv', 'two.csv', meta=metadata)
    )
    assert r.status_code == 404

    metadata['acquisition']['files'] = [
        {
            'name': 'one.csv',
            'type': 'engine type 0',
            'info': {'test': 'f0'}
        },
        {
            'name': 'folderA/two.csv',
            'type': 'engine type 1',
            'info': {'test': 'f1'}
        },
        {
            'name': '../folderB/two.csv',
            'type': 'engine type 1',
            'info': {'test': 'f1'}
        }
    ]

    # engine upload with slashes in filenames with filename_path=true
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':True},
        files=file_form('one.csv', 'folderA/two.csv', '../folderB/two.csv', meta=metadata)
    )
    assert r.ok

    expected_metadata = copy.deepcopy(metadata)
    expected_metadata['acquisition']['files'][2]['name'] = 'folderB/two.csv'
    # fields get sanitized
    expected_metadata['session']['info']['file_txt'] = expected_metadata['session']['info'].pop('file.txt')

    # Confirm produced_metadata is unchanged
    job_doc = as_admin.get('/jobs/' + job).json()
    assert job_doc['produced_metadata'] == expected_metadata

    r = as_admin.get('/projects/' + project)
    assert r.ok
    p = r.json()
    # Engine metadata should not replace existing fields
    assert p['label'] != metadata['project']['label']
    assert p['info'] == metadata['project']['info']

    r = as_admin.get('/sessions/' + session)
    assert r.ok
    s = r.json()
    # Engine metadata should not replace existing fields
    assert s['label'] != metadata['session']['label']
    assert s['age'] == 100000000000

    metadata['session']['info']['subject_raw'] = {'sex': 'male'}
    metadata['session']['info']['file_txt'] = metadata['session']['info'].pop('file.txt')
    assert s['info'] == metadata['session']['info']
    assert s['subject']['code'] == metadata['session']['subject']['code']

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    # Engine metadata should not replace existing fields
    assert a['label'] != metadata['acquisition']['label']
    assert a['info'] == metadata['acquisition']['info']
    a_timestamp = dateutil.parser.parse(a['timestamp'])
    m_timestamp = dateutil.parser.parse(metadata['acquisition']['timestamp'])
    assert a_timestamp == m_timestamp

    # Change the metadata filename to its sanitized version
    metadata['acquisition']['files'][2]['name'] = 'folderB/two.csv'

    for mf in metadata['acquisition']['files']:
        f = find_file_in_array(mf['name'], a['files'])
        assert mf is not None
        assert f['type'] == mf['type']
        assert f['info'] == mf['info']



    # engine upload with slashes in filenames with filename_path=false

    metadata['acquisition']['files'] = [
        {
            'name': 'one.csv',
            'type': 'engine type 0',
            'info': {'test': 'f0'}
        },
        {
            'name': 'folderA/two.csv',
            'type': 'engine type 1',
            'info': {'test': 'f1'}
        }
    ]

    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition, 'job': job, 'filename_path':False},
        files=file_form('one.csv', 'folderA/two.csv', meta=metadata)
    )
    assert r.ok
    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()

    # Change the metadata filename to its sanitized version
    metadata['acquisition']['files'][1]['name'] = 'two.csv'

    for mf in metadata['acquisition']['files']:

        f = find_file_in_array(mf['name'], a['files'])
        assert mf is not None
        assert f['type'] == mf['type']
        assert f['info'] == mf['info']


def test_session_engine_upload(data_builder, file_form, as_admin):
    project = data_builder.create_project()
    session = data_builder.create_session()

    metadata = {
        'project':{
            'label': 'engine project',
            'info': {'test': 'p'},
            'tags': ['one', 'two']
        },
        'session':{
            'label': 'engine session',
            'subject': {
                'code': 'engine subject',
                'race': 'Asian'
            },
            'timestamp': '2016-06-20T21:57:36+00:00',
            'info': {'test': 's'},
            'files': [
                {
                    'name': 'one.csv',
                    'type': 'engine type 0',
                    'info': {'test': 'f0'}
                },
                {
                    'name': 'two.csv',
                    'type': 'engine type 1',
                    'info': {'test': 'f1'}
                },
                {
                    'name': 'folder/three.csv',
                    'type': 'engine type 2',
                    'info': {'test': 'f2'}
                }
            ],
            'tags': ['one', 'two']
        }
    }

    r = as_admin.post('/engine',
        params={'level': 'session', 'id': session, 'filename_path':True},
        files=file_form('one.csv', 'two.csv', 'folder/three.csv', meta=metadata)
    )
    assert r.ok

    r = as_admin.get('/projects/' + project)
    assert r.ok
    p = r.json()
    # Engine metadata should not replace existing fields
    assert p['label'] != metadata['project']['label']
    assert p['info'] == metadata['project']['info']

    r = as_admin.get('/sessions/' + session)
    assert r.ok
    s = r.json()
    # Engine metadata should not replace existing fields
    assert s['label'] != metadata['session']['label']
    metadata['session']['info']['subject_raw'] = {'race': 'Asian'}
    assert s['info'] == metadata['session']['info']
    assert s['subject']['code'] == metadata['session']['subject']['code']
    s_timestamp = dateutil.parser.parse(s['timestamp'])
    m_timestamp = dateutil.parser.parse(metadata['session']['timestamp'])
    assert s_timestamp == m_timestamp

    for f in s['files']:
        mf = find_file_in_array(f['name'], metadata['session']['files'])
        assert mf is not None
        assert f['type'] == mf['type']
        assert f['info'] == mf['info']


def test_project_engine_upload(data_builder, file_form, as_admin):
    project = data_builder.create_project()
    metadata = {
        'project':{
            'label': 'engine project',
            'info': {'test': 'p'},
            'files': [
                {
                    'name': 'one.csv',
                    'type': 'engine type 0',
                    'info': {'test': 'f0'}
                },
                {
                    'name': 'two.csv',
                    'type': 'engine type 1',
                    'info': {'test': 'f1'}
                },
                {
                    'name': 'folder/three.csv',
                    'type': 'engine type 2',
                    'info': {'test': 'f2'}
                }
            ],
            'tags': ['one', 'two']
        }
    }

    r = as_admin.post('/engine',
        params={'level': 'project', 'id': project, 'filename_path':True},
        files=file_form('one.csv', 'two.csv', 'folder/three.csv', meta=metadata)
    )
    assert r.ok

    r = as_admin.get('/projects/' + project)
    assert r.ok
    p = r.json()
    # Engine metadata should not replace existing fields
    assert p['label'] != metadata['project']['label']
    assert p['info'] == metadata['project']['info']

    for f in p['files']:
        mf = find_file_in_array(f['name'], metadata['project']['files'])
        assert mf is not None
        assert f['type'] == mf['type']
        assert f['info'] == mf['info']


def test_acquisition_file_only_engine_upload(data_builder, file_form, as_admin):
    acquisition = data_builder.create_acquisition()
    file_names = ['one.csv', 'two.csv']

    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition},
        files=file_form(*file_names)
    )
    assert r.ok

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    assert set(f['name'] for f in r.json()['files']) == set(file_names)


def test_acquisition_subsequent_file_engine_upload(data_builder, file_form, as_admin):
    acquisition = data_builder.create_acquisition()

    file_name_1 = 'one.csv'
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition},
        files=file_form(file_name_1, meta={
            'acquisition': {
                'files': [{
                    'name': file_name_1,
                    'type': 'engine type 1',
                    'info': {'test': 'f1'}
                }]
            }
        })
    )
    assert r.ok

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    assert set(f['name'] for f in r.json()['files']) == set([file_name_1])

    file_name_2 = 'two.csv'
    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition},
        files=file_form(file_name_2, meta={
            'acquisition': {
                'files': [{
                    'name': file_name_2,
                    'type': 'engine type 2',
                    'info': {'test': 'f2'}
                }]
            }
        })
    )
    assert r.ok

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    assert set(f['name'] for f in r.json()['files']) == set([file_name_1, file_name_2])


def test_acquisition_metadata_only_engine_upload(data_builder, file_form, as_admin):
    project = data_builder.create_project()
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()

    metadata = {
        'project': {
            'label': 'engine project',
            'info': {'test': 'p'},
            'tags': ['one', 'two']
        },
        'session':{
            'label': 'engine session',
            'subject': {
                'code': 'engine subject',
                'race': 'Asian',
                'age': 100200300
            },
            'info': {'test': 's'},
            'tags': ['one', 'two']
        },
        'acquisition':{
            'label': 'engine acquisition',
            'timestamp': '2016-06-20T21:57:36+00:00',
            'info': {'test': 'a'},
            'tags': ['one', 'two']
        }
    }

    r = as_admin.post('/engine',
        params={'level': 'acquisition', 'id': acquisition},
        files=file_form(meta=metadata)
    )
    assert r.ok

    r = as_admin.get('/projects/' + project)
    assert r.ok
    p = r.json()
    # Engine metadata should not replace existing fields
    assert p['label'] != metadata['project']['label']
    assert p['info'] == metadata['project']['info']

    r = as_admin.get('/sessions/' + session)
    assert r.ok
    s = r.json()
    # Engine metadata should not replace existing fields
    assert s['label'] != metadata['session']['label']
    metadata['session']['info']['subject_raw'] = {'race': 'Asian'}
    assert s['info'] == metadata['session']['info']
    assert s['age'] == metadata['session']['subject']['age']
    assert s['subject']['code'] == metadata['session']['subject']['code']

    r = as_admin.get('/acquisitions/' + acquisition)
    assert r.ok
    a = r.json()
    # Engine metadata should not replace existing fields
    assert a['label'] != metadata['acquisition']['label']
    assert a['info'] == metadata['acquisition']['info']
    a_timestamp = dateutil.parser.parse(a['timestamp'])
    m_timestamp = dateutil.parser.parse(metadata['acquisition']['timestamp'])
    assert a_timestamp == m_timestamp


def test_analysis_upload(data_builder, default_payload, file_form, as_admin):
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'csv': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    # create session analysis
    r = as_admin.post('/sessions/' + session + '/analyses', files=file_form(
        'one.csv', meta={'label': 'test analysis', 'inputs': [{'name': 'one.csv'}]}
    ))
    assert r.ok
    session_analysis = r.json()['_id']

    # delete session analysis
    r = as_admin.delete('/sessions/' + session + '/analyses/' + session_analysis)
    assert r.ok

    # create acquisition analysis
    r = as_admin.post('/acquisitions/' + acquisition + '/analyses', files=file_form(
        'one.csv', meta={'label': 'test analysis', 'inputs': [{'name': 'one.csv'}]}
    ))
    assert r.ok
    acquisition_analysis = r.json()['_id']

    # delete acquisition analysis
    r = as_admin.delete('/acquisitions/' + acquisition + '/analyses/' + acquisition_analysis)
    assert r.ok

    # create acquisition file (for the fixture acquisition)
    r = as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form('one.csv'))
    assert r.ok

    # create session analysis (job) using acquisition's file as input
    r = as_admin.post('/sessions/' + session + '/analyses', json={
        'label': 'test analysis job',
        'job': {
            'gear_id': gear,
            'inputs': {
                'csv': {
                    'type': 'acquisition',
                    'id': acquisition,
                    'name': 'one.csv'
                }
            },
            'tags': ['example']
        }
    })
    assert r.ok
    session_analysis = r.json()['_id']

    # delete session analysis (job)
    r = as_admin.delete('/sessions/' + session + '/analyses/' + session_analysis)
    assert r.ok


def test_analysis_engine_upload(data_builder, file_form, as_admin):
    session = data_builder.create_session()

    # create acquisition analysis
    r = as_admin.post('/sessions/' + session + '/analyses', files=file_form(
        'one.csv', meta={'label': 'test analysis', 'inputs': [{'name': 'one.csv'}]}
    ))
    assert r.ok
    session_analysis = r.json()['_id']

    r = as_admin.post('/engine',
        params={'level': 'analysis', 'id': session_analysis},
        files=file_form('out.csv', meta={
            'type': 'text',
            'value': {'label': 'test'},
            'enabled': True}
    ))
    assert r.ok

    # Check for created timestamps for output files
    r = as_admin.get('/sessions/'+ session + '/analyses/' + session_analysis)
    assert 'created' in r.json()['files'][0]


    # delete acquisition analysis
    r = as_admin.delete('/sessions/' + session + '/analyses/' + session_analysis)
    assert r.ok


def test_packfile_upload(data_builder, file_form, as_user, as_device, api_db, with_site_settings):
    group = data_builder.create_group()
    project = data_builder.create_project()
    session = data_builder.create_session()

    subject = data_builder.create_subject(project=project, code='subj-01')
    r = as_device.delete('/subjects/' + subject)
    assert r.ok

    number_of_subjects = len(list(api_db.subjects.find({'project': bson.ObjectId(project)})))

    # try to start packfile-upload to non-project target
    r = as_device.post('/sessions/' + session + '/packfile-start')
    assert r.status_code == 500

    # try to start packfile-upload to non-existent project
    r = as_device.post('/projects/000000000000000000000000/packfile-start')
    assert r.status_code == 500

    # start packfile-upload
    r = as_device.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']

    # try to upload to packfile w/o token
    r = as_device.post('/projects/' + project + '/packfile')
    assert r.status_code == 500

    # upload to packfile
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('one.csv'))
    assert r.ok

    # upload another one to packfile
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('two.csv'))
    assert r.ok

    # Upload another one to packfile
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('three.csv'))
    assert r.ok

    metadata_json = json.dumps({
        'project': {'_id': project},
        'session': {
            'label': 'test-packfile-label (session)',
            'subject': {
                'code': 'subj-01',
                'ethnicity': 'Hispanic or Latino'
            }
        },
        'acquisition': {
            'label': 'test-packfile-label (acquisition)',
            'timestamp': '1979-01-01T00:00:00+00:00'
        },
        'packfile': {'type': 'test'}
    })

    # try to finish packfile-upload w/o token
    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'metadata': metadata_json})
    assert r.status_code == 500

    # try to finish packfile-upload with files in the request
    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json},
        files={'file': ('packfile-end.txt', 'sending files to packfile-end is not allowed\n')}
    )
    assert r.status_code == 500

    # finish packfile-upload (creates new session/acquisition)
    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json})
    assert r.ok

    # Check that a new subject was created
    project_subjects = list(api_db.subjects.find({'project': bson.ObjectId(project)}))
    assert len(project_subjects) == number_of_subjects + 1

    # make sure file was uploaded and mimetype and type are properly set
    created_subject = get_full_container(as_device, '/projects/' + project + '/subjects', -1)
    assert created_subject['label'] == 'subj-01'
    assert created_subject['parents']['group'] == group
    assert created_subject['parents']['project'] == project
    assert created_subject['ethnicity'] == 'Hispanic or Latino'

    created_session = get_full_container(as_device, '/subjects/' + created_subject['_id'] + '/sessions', 0)
    assert created_session['label'] == 'test-packfile-label (session)'
    assert created_session['parents']['group'] == group
    assert created_session['parents']['project'] == project
    assert created_session['parents']['subject'] == created_subject['_id']
    assert created_session['info']['subject_raw'] == {'ethnicity': 'Hispanic or Latino'}

    created_acq = as_device.get('/sessions/' + created_session['_id'] + '/acquisitions').json()[0]
    assert created_acq['label'] == 'test-packfile-label (acquisition)'
    assert created_acq['parents']['group'] == group
    assert created_acq['parents']['project'] == project
    assert created_acq['parents']['subject'] == created_subject['_id']
    assert created_acq['parents']['session'] == created_session['_id']

    packfile = created_acq['files'][0]
    assert packfile['mimetype'] == 'application/zip'
    assert packfile['type'] == 'test'
    assert packfile['zip_member_count'] == 3

    # Test that acquisition timestamp was parsed into date type
    r = as_device.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('one.csv'))
    assert r.ok

    metadata_json = json.dumps({
        'project': {'_id': project},
        'session': {
            'label': 'test-packfile-timestamp'
        },
        'acquisition': {
            'label': 'test-packfile-timestamp',
            'timestamp': '1990-01-01T00:00:00+00:00'
        },
        'packfile': {'type': 'test'}
    })

    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json})
    assert r.ok

    acquisition = api_db.acquisitions.find_one({'label':'test-packfile-timestamp', 'timestamp':{'$type':'date'}})
    assert acquisition.get('label') == 'test-packfile-timestamp'


    # Test that acquisition timestamp is used to differenciate acquisitions and session code for sessions

    # Make sure there is only one session and one acquisition with the above label to start
    sessions = list(api_db.sessions.find({'label':'test-packfile-timestamp'}))
    acquisitions = list(api_db.acquisitions.find({'label':'test-packfile-timestamp'}))
    assert len(sessions) == 1
    assert len(acquisitions) == 1


    r = as_device.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('one.csv'))
    assert r.ok

    metadata_json = json.dumps({
        'project': {'_id': project},
        'session': {
            'label': 'test-packfile-timestamp',
            'subject': {
                'code': 'new-subject'
            }
        },
        'acquisition': {
            'label': 'test-packfile-timestamp',
            'timestamp': '1999-01-01T00:00:00+00:00'
        },
        'packfile': {'type': 'test'}
    })

    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json})
    assert r.ok

    sessions = list(api_db.sessions.find({'label':'test-packfile-timestamp'}))
    acquisitions = list(api_db.acquisitions.find({'label':'test-packfile-timestamp'}))

    # Ensure a new session was created
    assert len(sessions) == 2

    # Ensure a new acquisition was created
    assert len(acquisitions) == 2

    # Ensure subject code exists on a session
    for s in sessions:
        subj = api_db.subjects.find_one({'_id': s['subject']})
        if subj.get('code') == 'new-subject':
            break
    else:
        # We didn't fine one
        assert False

    # Ensure second acquisition timestamp exists on an acquisition
    for a in acquisitions:
        if str(a.get('timestamp')) == '1999-01-01 00:00:00':
            break
    else:
        # We didn't fine one
        assert False

    # Remove sessions and acquisitions via delete and ensure new containers are created
    session_ids_before = [str(x['_id']) for x in sessions]
    acquisition_ids_before = [str(x['_id']) for x in acquisitions]
    for s in session_ids_before:
        assert as_device.delete('/sessions/'+s).ok

    # Add another packfile with the same metadata as above
    r = as_device.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']
    r = as_device.post('/projects/' + project + '/packfile',
        params={'token': token}, files=file_form('one.csv'))
    assert r.ok

    r = as_device.post('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json})
    assert r.ok

    # Ensure a new session and acquisition was created
    sessions_after = list(api_db.sessions.find({'label':'test-packfile-timestamp', 'deleted': {'$exists': False}}))
    acquisitions_after = list(api_db.acquisitions.find({'label':'test-packfile-timestamp', 'deleted': {'$exists': False}}))
    assert len(sessions_after) == 1
    assert len(acquisitions_after) == 1
    assert str(sessions_after[0]['_id']) not in session_ids_before
    assert str(acquisitions_after[0]['_id']) not in acquisition_ids_before

    # Add user to project
    uid = as_user.get('/users/self').json()['_id']
    r = as_device.post('/projects/' + project + '/permissions', json={'_id': uid, 'access': 'admin'})
    assert r.ok
    # get another token (start packfile-upload)
    r = as_user.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']

    files = [
        ('file', file_form('two.csv')['file']) ,
        ('file', file_form('three.csv')['file'])
    ]

    # upload to packfile
    r = as_user.post('/projects/' + project + '/packfile',
        params={'token': token}, files=files)
    assert r.ok

    # expire upload token
    expired_time = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    api_db.tokens.update({'_id': token}, {'$set': {'modified': expired_time}})

    # try to clean packfile tokens w/o site admin priviledge
    r = as_user.post('/clean-packfiles')
    assert r.status_code == 402

    r = as_device.post('/clean-packfiles')
    assert r.ok
    assert r.json()['removed']['tokens'] > 0



    # Perform another user packfile upload this time as SSE
    sessions = list(api_db.sessions.find({'label':'test-packfile-timestamp', 'deleted': {'$exists': False}}))
    acquisitions = list(api_db.acquisitions.find({'label':'test-packfile-timestamp'}))
    session_ids_before = [str(x['_id']) for x in sessions]
    for s in session_ids_before:
        assert as_device.delete('/sessions/'+s).ok

    r = as_user.post('/projects/' + project + '/packfile-start')
    assert r.ok
    token = r.json()['token']

    files = [
        ('file', file_form('two.csv')['file']),
        ('file', file_form('three.csv')['file'])
    ]

    # upload to packfile
    r = as_user.post('/projects/' + project + '/packfile',
        params={'token': token}, files=files)
    assert r.ok

    # Specifically SSE uses a GET request and as such does not have auth headers that determine Origin
    # If origin is not set then choose_provider will return a 500 for unknown
    r = as_user.get('/projects/' + project + '/packfile-end',
        params={'token': token, 'metadata': metadata_json})
    assert r.ok

    # Ensure a new session and acquisition was created
    sessions_after = list(api_db.sessions.find({'label':'test-packfile-timestamp', 'deleted': {'$exists': False}}))
    acquisitions_after = list(api_db.acquisitions.find({'label':'test-packfile-timestamp', 'deleted': {'$exists': False}}))
    assert len(sessions_after) == 1
    assert len(acquisitions_after) == 1
    assert str(sessions_after[0]['_id']) not in session_ids_before
    assert str(acquisitions_after[0]['_id']) not in acquisition_ids_before

    # clean up added session/acquisition
    data_builder.delete_project(project, recursive=True)

def test_engine_tags(data_builder, file_form, as_root):
    project = data_builder.create_project()
    metadata = {
        'project':{
            'label': 'engine project',
            'info': {'test': 'p'},
            'files': [
                {
                    'name': 'one.csv',
                    'type': 'engine type 0',
                    'info': {'test': 'f0'},
                    'tags': ['ein', 'zwei']
                },
                {
                    'name': 'two.csv',
                    'type': 'engine type 1',
                    'info': {'test': 'f1'}
                },
                {
                    'name': 'folder/three.csv',
                    'type': 'engine type 2',
                    'info': {'test': 'f2'}
                }
            ],
            'tags': ['one', 'two']
        }
    }

    r = as_root.post('/engine',
        params={'level': 'project', 'id': project, 'filename_path':True},
        files=file_form('one.csv', 'two.csv', 'folder/three.csv', meta=metadata)
    )
    assert r.ok

    # verify that tags are not overwritten or duplicated
    # verify that any other fields are not overwritten
    # with another engine upload
    metadata_two = {
        'project':{
            'label': 'override test',
            'tags': ['two', 'three']
        }
    }
    r = as_root.post('/engine',
        params={'level': 'project', 'id': project},
        files=file_form(meta=metadata_two)
    )
    assert r.ok
    r = as_root.get('/projects/' + project)
    assert r.json()['tags'] == ['one', 'two', 'three']
    assert r.json()['label'] != 'override test'


def test_unicode_filenames(data_builder, file_form, as_admin, as_public, api_db):
    filename = u'∂©∑∂ç.csv'
    file_contents = 'Hello World!'
    project = data_builder.create_project()

    r = as_admin.post('/projects/' + project + '/files', files=file_form((filename, file_contents)))
    assert r.ok

    r = as_admin.get('/projects/' + project)
    assert r.ok
    r_project = r.json()

    assert len(r_project['files']) == 1
    assert r_project['files'][0]['name'] == filename

    # Download file
    r = as_admin.get('/projects/' + project + '/files/' + filename)
    assert r.ok
    assert r.text == file_contents

    # Download via ticket
    r = as_admin.get('/projects/' + project + '/files/' + filename + '?ticket=')
    assert r.ok
    ticket = r.json()['ticket']

    r = as_public.get('/projects/' + project + '/files/' + filename + '?ticket=' + ticket)
    assert r.ok
    assert r.text == file_contents
