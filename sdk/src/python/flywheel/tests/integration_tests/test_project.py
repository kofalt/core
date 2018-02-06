import unittest
from sdk_test_case import SdkTestCase
from test_groups import create_test_group

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

def create_test_project():
    group_id = SdkTestCase.rand_string_lower()
    return SdkTestCase.fw.add_group(flywheel.GroupInput(group_id))
        



