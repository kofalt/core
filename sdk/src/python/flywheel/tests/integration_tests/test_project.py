import unittest
from sdk_test_case import SdkTestCase
from test_group import create_test_group

import flywheel

class ProjectsTestCases(SdkTestCase):
    def setUp(self):
        self.group_id = create_test_group()

    def tearDown(self):
        self.fw.delete_group(self.group_id)

    def test_projects(self):
        fw = self.fw
        
        project_name = self.rand_string()
        project = flywheel.ProjectInput(label=project_name, group=self.group_id, 
            description="This is a description", info = { 'some-key': 37 })

        # Add
        project_id = fw.add_project(project)
        self.assertNotEmpty(project_id)

        # Get
        r_project = fw.get_project(project_id)
        self.assertEqual(r_project.id, project_id)
        self.assertEqual(r_project.label, project_name)
        self.assertEqual(r_project.description, project.description)
        self.assertIn('some-key', r_project.info)
        self.assertEqual(r_project.info['some-key'], 37)
        self.assertTimestampBeforeNow(r_project.created)
        self.assertGreaterEqual(r_project.modified, r_project.created)

        # Get All
        projects = fw.get_all_projects()
        r_project.info = {}
        # TODO: Should we be setting this, shouldn't it be coming from api?
        r_project.info_exists = True
        r_project.analyses = None
        self.assertIn(r_project, projects)

        # Modify
        new_name = self.rand_string()
        project_mod = flywheel.ProjectInput(label=new_name, info={'another-key': 52})
        fw.modify_project(project_id, project_mod)

        changed_project = fw.get_project(project_id)
        self.assertEqual(changed_project.label, new_name)
        self.assertIn('some-key', changed_project.info)
        self.assertIn('another-key', changed_project.info)
        self.assertEqual(changed_project.info['another-key'], 52)
        self.assertEqual(changed_project.created, r_project.created)
        self.assertGreater(changed_project.modified, r_project.modified)

        # Notes, Tags
        message = 'This is a note'
        fw.add_project_note(project_id, message)
        
        tag = 'example-tag'
        fw.add_project_tag(project_id, tag)

        # Replace Info
        fw.replace_project_info(project_id, { 'foo': 3, 'bar': 'qaz' })

        # Set Info
        fw.set_project_info(project_id, { 'foo': 42, 'hello': 'world' })

        # Check
        r_project = fw.get_project(project_id)

        self.assertEqual(len(r_project.notes), 1)
        self.assertEqual(r_project.notes[0].text, message)
        
        self.assertEqual(len(r_project.tags), 1)
        self.assertEqual(r_project.tags[0], tag)

        self.assertEqual(r_project.info['foo'], 42)
        self.assertEqual(r_project.info['bar'], 'qaz')
        self.assertEqual(r_project.info['hello'], 'world')

        # Delete info fields
        fw.delete_project_info_fields(project_id, ['foo', 'bar'])

        r_project = fw.get_project(project_id)
        self.assertNotIn('foo', r_project.info)
        self.assertNotIn('bar', r_project.info)
        self.assertEqual(r_project.info['hello'], 'world')

        # Delete
        fw.delete_project(project_id)

        projects = fw.get_all_projects()
        self.assertNotIn(r_project, projects)

    def test_project_files(self):
        fw = self.fw
        
        project = flywheel.ProjectInput(label=self.rand_string(), group=self.group_id)
        project_id = fw.add_project(project)

        # Upload a file
        poem = 'The ceremony of innocence is drowned;'
        fw.upload_file_to_project(project_id, flywheel.FileSpec('yeats.txt', poem))

        # Check that the file was added to the project
        r_project = fw.get_project(project_id)
        self.assertEqual(len(r_project.files), 1)
        self.assertEqual(r_project.files[0].name, 'yeats.txt')
        self.assertEqual(r_project.files[0].size, 37)
        self.assertEqual(r_project.files[0].mimetype, 'text/plain')

        # Download the file and check content
        self.assertDownloadFileTextEquals(fw.download_file_from_project_as_data, project_id, 'yeats.txt', poem)
        
        # Test unauthorized download with ticket for the file
        self.assertDownloadFileTextEqualsWithTicket(fw.get_project_download_url, project_id, 'yeats.txt', poem)

        # Test file attributes
        self.assertEqual(r_project.files[0].modality, None)
        self.assertEqual(len(r_project.files[0].measurements), 0)
        self.assertEqual(r_project.files[0].type, 'text')

        resp = fw.modify_project_file(project_id, 'yeats.txt', flywheel.FileUpdate(
            modality='modality',
            measurements=['measurement'],
            type='type'
        ))

        # Check that no jobs were triggered, and attrs were modified
        self.assertEqual(resp.jobs_triggered, 0)

        r_project = fw.get_project(project_id)
        self.assertEqual(r_project.files[0].modality, "modality")
        self.assertEqual(len(r_project.files[0].measurements), 1)
        self.assertEqual(r_project.files[0].measurements[0], 'measurement')
        self.assertEqual(r_project.files[0].type, 'type')

        # Test file info
        self.assertEmpty(r_project.files[0].info)
        fw.replace_project_file_info(project_id, 'yeats.txt', {
            'a': 1,
            'b': 2,
            'c': 3,
            'd': 4
        })

        fw.set_project_file_info(project_id, 'yeats.txt', {
            'c': 5
        })

        r_project = fw.get_project(project_id)
        self.assertEqual(r_project.files[0].info['a'], 1)
        self.assertEqual(r_project.files[0].info['b'], 2)
        self.assertEqual(r_project.files[0].info['c'], 5)
        self.assertEqual(r_project.files[0].info['d'], 4)
    
        fw.delete_project_file_info_fields(project_id, 'yeats.txt', ['c', 'd'])  
        r_project = fw.get_project(project_id)
        self.assertEqual(r_project.files[0].info['a'], 1)
        self.assertEqual(r_project.files[0].info['b'], 2)
        self.assertNotIn('c', r_project.files[0].info)
        self.assertNotIn('d', r_project.files[0].info)

        fw.replace_project_file_info(project_id, 'yeats.txt', {})
        r_project = fw.get_project(project_id)
        self.assertEmpty(r_project.files[0].info)

        # Delete file
        fw.delete_project_file(project_id, 'yeats.txt')
        r_project = fw.get_project(project_id)
        self.assertEmpty(r_project.files)

        # Delete project
        fw.delete_project(project_id)

# TODO: Root mode tests


def create_test_project():
    group_id = create_test_group()
    return group_id, SdkTestCase.fw.add_project({
        'group': group_id, 
        'label': SdkTestCase.rand_string()
    })
        



