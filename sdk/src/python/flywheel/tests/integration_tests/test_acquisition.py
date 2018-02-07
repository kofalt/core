import unittest
from sdk_test_case import SdkTestCase
from test_session import create_test_session

import flywheel

class AcquisitionsTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id = create_test_session()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_acquisitions(self):
        fw = self.fw
        
        acquisition_name = self.rand_string()
        acquisition = flywheel.AcquisitionInput(label=acquisition_name, session=self.session_id) 

        # Add
        acquisition_id = fw.add_acquisition(acquisition)
        self.assertNotEmpty(acquisition_id)

        # Get
        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(r_acquisition.id, acquisition_id)
        self.assertEqual(r_acquisition.label, acquisition_name)
        self.assertTimestampBeforeNow(r_acquisition.created)
        self.assertGreaterEqual(r_acquisition.modified, r_acquisition.created)

        # Get All
        acquisitions = fw.get_all_acquisitions()
        self.sanitize_for_collection(r_acquisition, info_exists=False)
        self.assertIn(r_acquisition, acquisitions)

        # Modify
        new_name = self.rand_string()
        acquisition_mod = flywheel.ProjectInput(label=new_name, info={'another-key': 52})
        fw.modify_acquisition(acquisition_id, acquisition_mod)

        changed_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(changed_acquisition.label, new_name)
        self.assertEqual(changed_acquisition.created, r_acquisition.created)
        self.assertGreater(changed_acquisition.modified, r_acquisition.modified)

        # Notes, Tags
        message = 'This is a note'
        fw.add_acquisition_note(acquisition_id, message)
        
        tag = 'example-tag'
        fw.add_acquisition_tag(acquisition_id, tag)

        # Replace Info
        fw.replace_acquisition_info(acquisition_id, { 'foo': 3, 'bar': 'qaz' })

        # Set Info
        fw.set_acquisition_info(acquisition_id, { 'foo': 42, 'hello': 'world' })

        # Check
        r_acquisition = fw.get_acquisition(acquisition_id)

        self.assertEqual(len(r_acquisition.notes), 1)
        self.assertEqual(r_acquisition.notes[0].text, message)
        
        self.assertEqual(len(r_acquisition.tags), 1)
        self.assertEqual(r_acquisition.tags[0], tag)

        self.assertEqual(r_acquisition.info['foo'], 42)
        self.assertEqual(r_acquisition.info['bar'], 'qaz')
        self.assertEqual(r_acquisition.info['hello'], 'world')

        # Delete info fields
        fw.delete_acquisition_info_fields(acquisition_id, ['foo', 'bar'])

        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertNotIn('foo', r_acquisition.info)
        self.assertNotIn('bar', r_acquisition.info)
        self.assertEqual(r_acquisition.info['hello'], 'world')

        # Delete
        fw.delete_acquisition(acquisition_id)

        acquisitions = fw.get_all_acquisitions()
        self.sanitize_for_collection(r_acquisition)
        self.assertNotIn(r_acquisition, acquisitions)

    def test_acquisition_files(self):
        fw = self.fw
        
        acquisition = flywheel.AcquisitionInput(label=self.rand_string(), session=self.session_id)
        acquisition_id = fw.add_acquisition(acquisition)

        # Upload a file
        poem = 'Turning and turning in the widening gyre'
        fw.upload_file_to_acquisition(acquisition_id, flywheel.FileSpec('yeats.txt', poem))

        # Check that the file was added to the acquisition
        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(len(r_acquisition.files), 1)
        self.assertEqual(r_acquisition.files[0].name, 'yeats.txt')
        self.assertEqual(r_acquisition.files[0].size, 40)
        self.assertEqual(r_acquisition.files[0].mimetype, 'text/plain')

        # Download the file and check content
        self.assertDownloadFileTextEquals(fw.download_file_from_acquisition_as_data, acquisition_id, 'yeats.txt', poem)
        
        # Test unauthorized download with ticket for the file
        self.assertDownloadFileTextEqualsWithTicket(fw.get_acquisition_download_url, acquisition_id, 'yeats.txt', poem)

        # Test file attributes
        self.assertEqual(r_acquisition.files[0].modality, None)
        self.assertEqual(len(r_acquisition.files[0].measurements), 0)
        self.assertEqual(r_acquisition.files[0].type, 'text')

        resp = fw.modify_acquisition_file(acquisition_id, 'yeats.txt', flywheel.FileUpdate(
            modality='modality',
            measurements=['measurement'],
            type='type'
        ))

        # Check that no jobs were triggered, and attrs were modified
        self.assertEqual(resp.jobs_triggered, 0)

        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(r_acquisition.files[0].modality, "modality")
        self.assertEqual(len(r_acquisition.files[0].measurements), 1)
        self.assertEqual(r_acquisition.files[0].measurements[0], 'measurement')
        self.assertEqual(r_acquisition.files[0].type, 'type')

        # Test file info
        self.assertEmpty(r_acquisition.files[0].info)
        fw.replace_acquisition_file_info(acquisition_id, 'yeats.txt', {
            'a': 1,
            'b': 2,
            'c': 3,
            'd': 4
        })

        fw.set_acquisition_file_info(acquisition_id, 'yeats.txt', {
            'c': 5
        })

        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(r_acquisition.files[0].info['a'], 1)
        self.assertEqual(r_acquisition.files[0].info['b'], 2)
        self.assertEqual(r_acquisition.files[0].info['c'], 5)
        self.assertEqual(r_acquisition.files[0].info['d'], 4)
    
        fw.delete_acquisition_file_info_fields(acquisition_id, 'yeats.txt', ['c', 'd'])  
        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEqual(r_acquisition.files[0].info['a'], 1)
        self.assertEqual(r_acquisition.files[0].info['b'], 2)
        self.assertNotIn('c', r_acquisition.files[0].info)
        self.assertNotIn('d', r_acquisition.files[0].info)

        fw.replace_acquisition_file_info(acquisition_id, 'yeats.txt', {})
        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEmpty(r_acquisition.files[0].info)

        # Delete file
        fw.delete_acquisition_file(acquisition_id, 'yeats.txt')
        r_acquisition = fw.get_acquisition(acquisition_id)
        self.assertEmpty(r_acquisition.files)

        # Delete acquisition
        fw.delete_acquisition(acquisition_id)

    def sanitize_for_collection(self, acquisition, info_exists=True):
        # workaround: all-container endpoints skip some fields, single-container does not. this sets up the equality check 
        acquisition.info = {}
        acquisition.info_exists = info_exists
        acquisition.analyses = None

def create_test_acquisition():
    group_id, project_id, session_id = create_test_session()
    return group_id, project_id, session_id, SdkTestCase.fw.add_acquisition({
        'session': session_id, 
        'label': SdkTestCase.rand_string()
    })


