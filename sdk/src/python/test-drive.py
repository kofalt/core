#!/usr/bin/env python
from __future__ import print_function

import sys
sys.path.append('gen')

import os
import random
import string

import flywheel

from pprint import pprint

# Helper function to generate random data
def rand_string():
	return ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

# Get API get from environment
api_key = os.environ['SdkTestKey']

# Create client
fw = flywheel.Flywheel(api_key)

# A test file
filepath = __file__
filename = os.path.basename(filepath)

# A second test file
filename2 = 'test.txt';
with open(filename2, 'w') as f:
    f.write('This is a test file')

#
## Users
#
user = fw.get_current_user()
assert len(user['_id']) > 0

users = fw.get_all_users()
assert len(users) >= 1

email = rand_string() + '@' + rand_string() + '.com'
userId = fw.add_user({
    'email':     email,
    'firstname': rand_string(),
    'lastname':  rand_string(),
})

fw.modify_user(userId, {'firstname': 'John'})
user2 = fw.get_user(userId)
assert user2['email'] == email
assert user2['firstname'] == 'John'

fw.delete_user(userId)


#
## Groups
#
groupId = fw.add_group({
	'_id': rand_string(),
})

fw.add_group_tag(groupId, 'blue')
fw.modify_group(groupId, {'label': 'testdrive'})

groups = fw.get_all_groups()
assert len(groups) > 0

group = fw.get_group(groupId)
assert group['tags'][0] == 'blue'
assert group['label'] == 'testdrive'


#
## Projects
#
projectId = fw.add_project({
	'label': rand_string(),
	'group': groupId,
})

fw.add_project_tag(projectId, 'blue')
fw.modify_project(projectId, {'label': 'testdrive'})
fw.add_project_note(projectId, 'This is a note')

projects = fw.get_all_projects()
assert len(projects) > 0

fw.upload_file_to_project(projectId, filepath, metadata={'zip_member_count': 15})
fw.download_file_from_project(projectId, filename, '/tmp/download.py')

project = fw.get_project(projectId)
assert project['tags'][0] == 'blue'
assert project['label'] == 'testdrive'
assert project['notes'][0]['text'] == 'This is a note'
assert project['files'][0]['name'] == filename
assert project['files'][0]['size'] == os.path.getsize('/tmp/download.py')
assert project['files'][0]['zip_member_count'] == 15

projectDownloadUrl = fw.get_project_download_url(projectId, filename)
assert projectDownloadUrl != ''

fw.delete_project_file(projectId, filename)
project = fw.get_project(projectId)
assert len(project['files']) == 0


#
## Sessions
#
sessionId = fw.add_session({
	'label': rand_string(),
	'project': projectId,
})

fw.add_session_tag(sessionId, 'blue')
fw.modify_session(sessionId, {'label': 'testdrive'})
fw.add_session_note(sessionId, 'This is a note')

sessions = fw.get_project_sessions(projectId)
assert len(sessions) > 0

sessions = fw.get_all_sessions()
assert len(sessions) > 0

fw.upload_file_to_session(sessionId, filepath, metadata={'zip_member_count': 15})
fw.download_file_from_session(sessionId, filename, '/tmp/download2.py')

session = fw.get_session(sessionId)
assert session['tags'][0] == 'blue'
assert session['label'] == 'testdrive'
assert session['notes'][0]['text'] == 'This is a note'
assert session['files'][0]['name'] == filename
assert session['files'][0]['size'] == os.path.getsize('/tmp/download2.py')
assert session['files'][0]['zip_member_count'] == 15

sessionDownloadUrl = fw.get_session_download_url(sessionId, filename)
assert sessionDownloadUrl != ''

analysisId = fw.add_session_analysis(sessionId, {
    'label': 'testdrive',
    'inputs': [{
        'type': 'session',
        'id': sessionId,
        'name': filename
    }]
})

fw.upload_output_to_analysis(analysisId, filename2)

analysis = fw.get_analysis(analysisId)
assert analysis['label'] == 'testdrive'

assert analysis['inputs'][0]['name'] == filename
assert analysis['files'][0]['name'] == filename2

fw.delete_session_file(sessionId, filename)
session = fw.get_session(sessionId)
assert len(session['files']) == 0


#
## Acquisitions
#
acqId = fw.add_acquisition({
	'label': rand_string(),
	'session': sessionId,
})

fw.add_acquisition_tag(acqId, 'blue')
fw.modify_acquisition(acqId, {'label': 'testdrive'})
fw.add_acquisition_note(acqId, 'This is a note')

acqs = fw.get_session_acquisitions(sessionId)
assert len(acqs) > 0

acqs = fw.get_all_acquisitions()
assert len(acqs) > 0

fw.upload_file_to_acquisition(acqId, filepath, metadata={'zip_member_count': 15})
fw.download_file_from_acquisition(acqId, filename, '/tmp/download3.py')

acq = fw.get_acquisition(acqId)
assert acq['tags'][0] == 'blue'
assert acq['label'] == 'testdrive'
assert acq['notes'][0]['text'] == 'This is a note'
assert acq['files'][0]['name'] == filename
assert acq['files'][0]['size'] == os.path.getsize('/tmp/download3.py')
assert acq['files'][0]['zip_member_count'] == 15

acqDownloadUrl = fw.get_acquisition_download_url(acqId, filename)
assert acqDownloadUrl != ''


#
## Collections
#
colId = fw.add_collection({
	'label': rand_string(),
	'description': rand_string(),
})

fw.add_sessions_to_collection(colId, [sessionId])
fw.add_acquisitions_to_collection(colId, [acqId])

collSessions = fw.get_collection_sessions(colId)
assert len(collSessions) == 1

collAqs = fw.get_collection_acquisitions(colId)
assert len(collAqs) == 1

fw.add_collection_note(colId, 'This is a note')

fw.upload_file_to_collection(colId, filepath, metadata={'zip_member_count': 15})
fw.download_file_from_collection(colId, filename, '/tmp/download4.py')

collection = fw.get_collection(colId)
assert collection['notes'][0]['text'] == 'This is a note'
assert collection['files'][0]['name'] == filename
assert collection['files'][0]['size'] == os.path.getsize('/tmp/download4.py')
assert collection['files'][0]['zip_member_count'] == 15

colDownloadUrl = fw.get_collection_download_url(colId, filename)
assert colDownloadUrl != ''

fw.delete_collection_file(colId, filename)
collection = fw.get_collection(colId)
assert len(collection['files']) == 0


#
## Gears
#
gearId = fw.add_gear('test-drive-gear', {
	'category': 'converter',
	'exchange' : {
		'git-commit' : 'example',
		'rootfs-hash' : 'sha384:example',
		'rootfs-url' : 'https://example.example'
	},
	'gear':	{
		'name': 'test-drive-gear',
		'label': 'Test Drive Gear',
		'version': str(random.randint(1,9000)),
		'author': 'Noone',
		'description': 'An empty example gear',
		'license': 'Other',
		'source': 'http://example.example',
		'url': 'http://example.example',
        'config': {},
		'inputs': {
			'x': {
				'base': 'file'
			}
		}
	}
})

gear = fw.get_gear(gearId)
assert gear['gear']['name'] == 'test-drive-gear'

gears = fw.get_all_gears()
assert len(gears) > 0

job_id = fw.add_job({
	'gear_id': gearId,
	'state': 'pending',
	'inputs': {
		'x': {
			'type': 'acquisition',
			'id': acqId,
			'name': 'test-drive.py'
		}
	}
})

job = fw.get_job(job_id)
assert job['gear_id'] == gearId

logs = fw.get_job_logs(job_id)
# Likely will not have anything in them yet


#
## Misc
#
config = fw.get_config()
assert config is not None

version = fw.get_version()
assert version['database'] >= 25


#
## Cleanup
#
os.remove(filename2)
fw.delete_collection(colId)
fw.delete_acquisition(acqId)
fw.delete_session(sessionId)
fw.delete_project(projectId)
fw.delete_group(groupId)
fw.delete_gear(gearId)

print('')
print('Test drive complete.')
