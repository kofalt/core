import unittest
from sdk_test_case import SdkTestCase
from test_project import create_test_project

import flywheel

class SubjectsTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id = create_test_project()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_subjects(self):
        fw = self.fw

        subject_code = self.rand_string_lower()
        subject = flywheel.Subject(
            project=self.project_id,
            firstname=self.rand_string(),
            lastname=self.rand_string(),
            code=subject_code,
            sex='other',
            info={'some-subject-key': 37}
        )

        # Add
        subject_id = fw.add_subject(subject)
        self.assertNotEmpty(subject_id)

        # Get
        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.id, subject_id)
        self.assertEqual(r_subject.code, subject_code)
        self.assertIn('some-subject-key', r_subject.info)
        self.assertEqual(r_subject.info['some-subject-key'], 37)
        self.assertTimestampBeforeNow(r_subject.created)
        self.assertGreaterEqual(r_subject.modified, r_subject.created)

        # Generic Get is equivalent
        self.assertEqual(fw.get(subject_id).to_dict(), r_subject.to_dict())

        # Get All
        subjects = fw.get_all_subjects()
        self.assertNotEmpty(subjects)

        self.sanitize_for_collection(r_subject)
        self.assertIn(r_subject, subjects)

        # # Get from parent
        subjects = fw.get_project_subjects(self.project_id)
        self.assertIn(r_subject, subjects)

        project = fw.get(self.project_id)
        r_subject = project.subjects.find_one('code="{}"'.format(subject_code))
        self.assertIsNotNone(r_subject)
        self.assertEqual(r_subject.id, subject_id)

        # Modify
        new_sex = 'male'
        r_subject.update(sex=new_sex)

        changed_subject = fw.get_subject(subject_id)
        self.assertEqual(changed_subject.sex, new_sex)
        self.assertEqual(changed_subject.created, r_subject.created)
        self.assertGreater(changed_subject.modified, r_subject.modified)

        # Notes, Tags
        message = 'This is a note'
        r_subject.add_note(message)

        tag = 'example-tag'
        r_subject.add_tag(tag)

        # Replace Info
        fw.replace_subject_info(subject_id, { 'foo': 3, 'bar': 'qaz' })

        # Set Info
        fw.set_subject_info(subject_id, { 'foo': 42, 'hello': 'world' })

        # Check
        r_subject = fw.get_subject(subject_id)

        self.assertEqual(len(r_subject.notes), 1)
        self.assertEqual(r_subject.notes[0].text, message)

        self.assertEqual(len(r_subject.tags), 1)
        self.assertEqual(r_subject.tags[0], tag)

        self.assertEqual(r_subject.info['foo'], 42)
        self.assertEqual(r_subject.info['bar'], 'qaz')
        self.assertEqual(r_subject.info['hello'], 'world')

        # Delete info fields
        fw.delete_subject_info_fields(subject_id, ['foo', 'bar'])

        r_subject = fw.get_subject(subject_id)
        self.assertNotIn('foo', r_subject.info)
        self.assertNotIn('bar', r_subject.info)
        self.assertEqual(r_subject.info['hello'], 'world')

        # Add session
        r_session = r_subject.add_session(label='Session 1')
        self.assertEqual(r_session.project, self.project_id)
        self.assertEqual(r_session.subject.id, subject_id)
        session_id = r_session.id

        # Find session
        r_session = r_subject.sessions.find_one('label=Session 1')
        self.assertIsNotNone(r_session)
        self.assertEqual(r_session.id, session_id)

        # Delete
        fw.delete_subject(subject_id)

        subjects = fw.get_all_subjects()
        self.sanitize_for_collection(r_subject)
        self.assertNotIn(r_subject, subjects)

    def test_subject_files(self):
        fw = self.fw

        subject = flywheel.Subject(code=self.rand_string(), project=self.project_id)
        subject_id = fw.add_subject(subject)

        # Upload a file
        poem = 'The best lack all conviction, while the worst'
        fw.upload_file_to_subject(subject_id, flywheel.FileSpec('yeats.txt', poem))

        # Check that the file was added to the subject
        r_subject = fw.get_subject(subject_id)
        self.assertEqual(len(r_subject.files), 1)
        self.assertEqual(r_subject.files[0].name, 'yeats.txt')
        self.assertEqual(r_subject.files[0].size, 45)
        self.assertEqual(r_subject.files[0].mimetype, 'text/plain')

        # Download the file and check content
        self.assertDownloadFileTextEquals(fw.download_file_from_subject_as_data, subject_id, 'yeats.txt', poem)

        # Test unauthorized download with ticket for the file
        self.assertDownloadFileTextEqualsWithTicket(fw.get_subject_download_url, subject_id, 'yeats.txt', poem)

        # Test file attributes
        self.assertEqual(r_subject.files[0].modality, None)
        self.assertEmpty(r_subject.files[0].classification)
        self.assertEqual(r_subject.files[0].type, 'text')

        resp = r_subject.files[0].update(type='type', modality='modality')

        # Check that no jobs were triggered, and attrs were modified
        self.assertEqual(resp.jobs_spawned, 0)

        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.files[0].modality, "modality")
        self.assertEmpty(r_subject.files[0].classification)
        self.assertEqual(r_subject.files[0].type, 'type')

        # Test classifications
        resp = fw.replace_subject_file_classification(subject_id, 'yeats.txt', {
            'Custom': ['measurement1', 'measurement2'],
        })
        self.assertEqual(resp.modified, 1)
        self.assertEqual(resp.jobs_spawned, 0)

        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.files[0].classification, {
            'Custom': ['measurement1', 'measurement2']
        });

        resp = fw.modify_subject_file_classification(subject_id, 'yeats.txt', {
            'add': {
                'Custom': ['HelloWorld'],
            },
            'delete': {
                'Custom': ['measurement2']
            }
        })
        self.assertEqual(resp.modified, 1)
        self.assertEqual(resp.jobs_spawned, 0)

        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.files[0].classification, {
            'Custom': ['measurement1', 'HelloWorld'],
        });

        # Test file info
        self.assertEmpty(r_subject.files[0].info)
        fw.replace_subject_file_info(subject_id, 'yeats.txt', {
            'a': 1,
            'b': 2,
            'c': 3,
            'd': 4
        })

        fw.set_subject_file_info(subject_id, 'yeats.txt', {
            'c': 5
        })

        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.files[0].info['a'], 1)
        self.assertEqual(r_subject.files[0].info['b'], 2)
        self.assertEqual(r_subject.files[0].info['c'], 5)
        self.assertEqual(r_subject.files[0].info['d'], 4)

        fw.delete_subject_file_info_fields(subject_id, 'yeats.txt', ['c', 'd'])
        r_subject = fw.get_subject(subject_id)
        self.assertEqual(r_subject.files[0].info['a'], 1)
        self.assertEqual(r_subject.files[0].info['b'], 2)
        self.assertNotIn('c', r_subject.files[0].info)
        self.assertNotIn('d', r_subject.files[0].info)

        fw.replace_subject_file_info(subject_id, 'yeats.txt', {})
        r_subject = fw.get_subject(subject_id)
        self.assertEmpty(r_subject.files[0].info)

        # Delete file
        fw.delete_subject_file(subject_id, 'yeats.txt')
        r_subject = fw.get_subject(subject_id)
        self.assertEmpty(r_subject.files)

        # Delete subject
        fw.delete_subject(subject_id)

    def test_subject_errors(self):
        fw = self.fw

        # Try to create subject without project id
        try:
            subject = flywheel.Subject(code=self.rand_string())
            subject_id = fw.add_subject(subject)
            self.fail('Expected ApiException creating invalid subject!')
        except flywheel.ApiException as e:
            self.assertEqual(e.status, 422)

        # Try to get a subject that doesn't exist
        try:
            fw.get_subject('DOES_NOT_EXIST')
            self.fail('Expected ApiException retrieving invalid subject!')
        except flywheel.ApiException as e:
            self.assertEqual(e.status, 404)

    def test_subject_analysis(self):
        fw = self.fw

        subject = flywheel.Subject(project=self.project_id, code=self.rand_string())

        # Add
        subject_id = fw.add_subject(subject)
        self.assertNotEmpty(subject_id)

        poem = 'When a vast image out of Spiritus Mundi'
        fw.upload_file_to_subject(subject_id, flywheel.FileSpec('yeats.txt', poem))

        file_ref = flywheel.FileReference(
            id=subject_id,
            type='subject',
            name='yeats.txt'
        )

        analysis = flywheel.AnalysisInput(label=self.rand_string(), description=self.rand_string(), inputs=[file_ref])

        # Add
        analysis_id = fw.add_subject_analysis(subject_id, analysis)
        self.assertNotEmpty(analysis_id)

        # Get the list of analyses in the subject
        analyses = fw.get_subject_analyses(subject_id)
        self.assertEqual(len(analyses), 1)

        r_analysis = analyses[0]

        self.assertEqual(r_analysis.id, analysis_id)
        self.assertEmpty(r_analysis.job)

        self.assertTimestampBeforeNow(r_analysis.created)
        self.assertGreaterEqual(r_analysis.modified, r_analysis.created)

        self.assertEqual(len(r_analysis.inputs), 1)
        self.assertEqual(r_analysis.inputs[0].name, 'yeats.txt')

    def sanitize_for_collection(self, subject, info_exists=True):
        # workaround: all-container endpoints skip some fields,
        # single-container does not. this sets up the equality check
        subject.info = {}
        subject.info_exists = info_exists
        subject.analyses = None

        subject.sex = None
        subject.firstname = None
        subject.lastname = None
        subject.info = {}
        subject.info_exists = info_exists


def create_test_subject():
    group_id, project_id = create_test_project()
    return group_id, project_id, SdkTestCase.fw.add_subject({
        'project': project_id,
        'code': SdkTestCase.rand_string_lower(),
        'firstname': SdkTestCase.rand_string(),
        'lastname': SdkTestCase.rand_string(),
        'sex': 'other',
        'age': 57
    })
