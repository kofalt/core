
from mock import patch
import bson
import pytest

from flywheel_common import errors

from api.dao import basecontainerstorage
from api.site import providers
from api.storage.py_fs.py_fs_storage import PyFsStorage


def _create_project_tree(data_builder):

    from collections import namedtuple
    Project = namedtuple('Project', 'id, subjects')
    Subject = namedtuple('Subject', 'id, sessions')


    group = data_builder.create_group()

    # First create a project with 3 unique subjects with 2 sessions each as copy subjects
    # And also one unique subject with only 1 session as a move session
    project1 = data_builder.create_project(group=group, label='source')
    p1s1 = data_builder.create_subject(project=project1, code='unique1')
    p1s1s1 = data_builder.create_session(project=project1, subject={'_id': p1s1})
    p1s1s2 = data_builder.create_session(project=project1, subject={'_id': p1s1})
    p1s2 = data_builder.create_subject(project=project1, code='unique2')
    p1s2s1 = data_builder.create_session(project=project1, subject={'_id': p1s2})
    p1s2s2 = data_builder.create_session(project=project1, subject={'_id': p1s2})
    p1s3 = data_builder.create_subject(project=project1, code='conflict1')
    p1s3s1 = data_builder.create_session(project=project1, subject={'_id': p1s3})
    p1s3s2 = data_builder.create_session(project=project1, subject={'_id': p1s3})
    p1s4 = data_builder.create_subject(project=project1, code='uniqueMove1')
    p1s4s1 = data_builder.create_session(project=project1, subject={'_id': p1s4})

    projects = [Project(project1, [
        #Subject(p1s1, [p1s1s1, p1s1s2, p1s1s3]),
        Subject(p1s1, [p1s1s1, p1s1s2]),
        Subject(p1s2, [p1s2s1, p1s2s2]),
        Subject(p1s3, [p1s3s1, p1s3s2]),
        Subject(p1s4, [p1s4s1]),
    ])]

    # Now create another project with 3 unique subjects and 2 sesions each.
    # One of the subjects shares the same code as in project 1, a conflict
    project2 = data_builder.create_project(group=group, label='destination')
    p2s1 = data_builder.create_subject(project=project2, code='unique3')
    p2s1s1 = data_builder.create_session(project=project2, subject={'_id': p2s1})
    p2s1s2 = data_builder.create_session(project=project2, subject={'_id': p2s1})
    p2s2 = data_builder.create_subject(project=project2, code='unique4')
    p2s2s1 = data_builder.create_session(project=project2, subject={'_id': p2s2})
    p2s2s2 = data_builder.create_session(project=project2, subject={'_id': p2s2})
    p2s3 = data_builder.create_subject(project=project2, code='conflict1')
    p2s3s1 = data_builder.create_session(project=project2, subject={'_id': p2s3})
    p2s3s2 = data_builder.create_session(project=project2, subject={'_id': p2s3})

    projects.append(Project(project2, [
        Subject(p2s1, [p2s1s1, p2s1s2]),
        Subject(p2s2, [p2s2s1, p2s2s2]),
        Subject(p2s3, [p2s3s1, p2s3s2])
    ]))

    # Now create another project with 2 unique subjects and 2 sesions each.
    # One of the subjects shares the same code as in project 1, a conflict but wont move
    project3 = data_builder.create_project(group=group, label='outsideOfScope')
    p3s1 = data_builder.create_subject(project=project3, code='unique5')
    p3s1s1 = data_builder.create_session(project=project3, subject={'_id': p3s1})
    p3s1s2 = data_builder.create_session(project=project3, subject={'_id': p3s1})
    p3s2 = data_builder.create_subject(project=project3, code='conflict1')
    p3s2s1 = data_builder.create_session(project=project3, subject={'_id': p3s2})
    p3s2s2 = data_builder.create_session(project=project3, subject={'_id': p3s2})

    projects.append(Project(project3, [
        Subject(p3s1, [p3s1s1, p3s1s2]),
        Subject(p3s2, [p3s2s1, p3s2s2])
    ]))

    return projects

def test_bulk_move_session_to_project_move(data_builder, api_db, as_admin):
    """ Test moving sessions to project with the move conflict resolution"""
    projects = _create_project_tree(data_builder)
    project1 = projects[0].id
    project2 = projects[1].id
    # The sessions we are going to move
        # two that are copies and one that is a move
    sources = (
        projects[0].subjects[0].sessions +
        projects[0].subjects[2].sessions +
        projects[0].subjects[3].sessions
    )

    # We are going to move the sessions from unique1 and conflict1. All should end up
    # In project 2 with conflict1 in project2 having 4 sessions total
    r = as_admin.post('/bulk/move/sessions', json={
	"sources": sources,
	#"sources": [p1s1s1, p1s1s2, p1s3s1, p1s3s2]
	"destination_container_type": "projects",
	"destinations": [project2],
	"conflict_mode": "move"
    })
    assert r.ok

    object_ids = []
    for s in sources:
        object_ids.append(bson.ObjectId(s))
    moved_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    assert moved_sessions.count() == 5
    for session in moved_sessions:
        assert str(session['project']) == project2
        assert str(session['parents']['project']) == project2
        # TODO: set some permissions to validate they follow through
        #assert session['permissions'] == project2['permissions']
    object_ids = []
    for s in projects[0].subjects[1].sessions:
        object_ids.append(bson.ObjectId(s))
    not_moved_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    assert not_moved_sessions.count() == 2
    for session in not_moved_sessions:
        assert str(session['project']) == project1
        assert str(session['parents']['project']) == project1

    # Explicitely check each session in the conflict set
    conflicts = projects[0].subjects[2].sessions + projects[1].subjects[2].sessions
    object_ids = []
    for c in conflicts:
        object_ids.append(bson.ObjectId(c))
    #conflict_sessions = api_db.sessions.find({'_id': {'$in' [p1s3s1, p1s3s2, p2s3s1, p2s3s2]}})
    conflict_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    for session in conflict_sessions:
        assert str(session['project']) == project2
        assert str(session['subject']) == projects[1].subjects[2].id

    #p1s2 should only have the unmoved sessions, p1s2s1 and p1s2s2 specifically
    assert api_db.sessions.find({'subject': bson.ObjectId(projects[0].subjects[1].id)}).count() == 2
    assert api_db.sessions.find({'subject': bson.ObjectId(projects[0].subjects[3].id)}).count() == 1

    #Verify the session counts to make sure no sessions were lost or added
    assert api_db.sessions.find({'project': bson.ObjectId(projects[0].id)}).count() == 2
    assert api_db.sessions.find({'project': bson.ObjectId(projects[1].id)}).count() == 11
    assert api_db.sessions.find({'project': bson.ObjectId(projects[2].id)}).count() == 4



def test_bulk_move_session_to_project_skip(data_builder, api_db, as_admin):
    """Test bulk move sessions to project with skip conflict resolution"""
    projects = _create_project_tree(data_builder)
    project1 = projects[0].id
    project2 = projects[1].id
    # THe sessions we are going to attempt to move
    sources = projects[0].subjects[0].sessions + projects[0].subjects[2].sessions + projects[0].subjects[3].sessions

    # We are trying to move the sessions from unique1 and conflict1. 2 should end up
    # In project 2 with conflict1 getting skipped
    r = as_admin.post('/bulk/move/sessions', json={
	"sources": sources,
	"destination_container_type": "projects",
	"destinations": [project2],
	"conflict_mode": "skip"
    })
    assert r.ok

    object_ids = []
    for s in projects[0].subjects[0].sessions:
        object_ids.append(bson.ObjectId(s))
    moved_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    for session in moved_sessions:
        assert str(session['project']) == project2
        assert str(session['parents']['project']) == project2
        # TODO: set some permissions to validate they follow through
        #assert session['permissions'] == project2['permissions']
    object_ids = []
    for s in projects[0].subjects[1].sessions:
        object_ids.append(bson.ObjectId(s))
    not_moved_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    for session in not_moved_sessions:
        assert str(session['project']) == project1
        assert str(session['parents']['project']) == project1

    # Explicitly check each session in the conflict set was skipped and remains in project1
    object_ids = []
    for s in projects[0].subjects[2].sessions:
        object_ids.append(bson.ObjectId(s))
    conflict_sessions = api_db.sessions.find({'_id': {'$in': object_ids}})
    for session in conflict_sessions:
        assert str(session['project']) == project1
        assert str(session['subject']) == projects[0].subjects[2].id

    #p1s2 should still have the unmoved sessions
    assert api_db.sessions.find({'subject': bson.ObjectId(projects[0].subjects[1].id)}).count() == 2
    #p1s3 should have unmoved sessions as they should be skipped
    assert api_db.sessions.find({'subject': bson.ObjectId(projects[0].subjects[2].id)}).count() == 2
    # Moved subject should have no sessions left
    assert api_db.sessions.find({'subject': bson.ObjectId(projects[0].subjects[3].id)}).count() == 1

    #Verify the session counts to make sure no sessions were lost or added
    assert api_db.sessions.find({'project': bson.ObjectId(projects[0].id)}).count() == 4
    assert api_db.sessions.find({'project': bson.ObjectId(projects[1].id)}).count() == 9
    assert api_db.sessions.find({'project': bson.ObjectId(projects[2].id)}).count() == 4
