import unittest
import tempfile
import os

from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition
from test_gear import create_test_gear

import flywheel


class MixinTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()
        self.gear_id = None

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

        if self.gear_id is not None:
            self.fw.delete_gear(self.gear_id)

    def test_update(self):
        fw = self.fw

        project = fw.get_project(self.project_id)
        # Two styles of updates
        project.update(label="My Project")
        project.update({"description": "This is my test project"})

        r_project = project.reload()
        self.assertEqual(r_project.label, "My Project")
        self.assertEqual(r_project.description, "This is my test project")

    def test_child_mixins(self):
        fw = self.fw

        # Upload file to project
        poem = b"When a vast image out of Spiritus Mundi"
        fw.upload_file_to_project(self.project_id, flywheel.FileSpec("yeats.dat", poem))

        # TODO: Test Analyses

        # GROUP
        r_group = fw.get_group(self.group_id)
        projects = r_group.projects()

        self.assertIsNotNone(projects)
        self.assertEqual(len(projects), 1)
        r_project = projects[0]

        self.assertEqual(r_project.id, self.project_id)
        self.assertEqual(r_project.container_type, "project")

        sessions = r_project.sessions()
        self.assertEqual(1, len(sessions))
        r_session = sessions[0]
        self.assertEqual(r_session.id, self.session_id)
        self.assertEqual(r_session.project, self.project_id)

        # Assert that file has a parent
        self.assertEqual(1, len(r_project.files))
        self.assertEqual(r_project.files[0].parent, r_project)

        # Test load files
        r_project._files = None

        project_files = r_project.get_files()
        self.assertEqual(1, len(project_files))
        r_file = project_files[0]
        self.assertEqual(r_file.parent, r_project)
        self.assertEqual(r_file.name, "yeats.dat")
        self.assertEqual(r_file.size, len(poem))

        # Read file
        data = r_file.read()
        self.assertEqual(data, poem)

        # Get url
        ticket_url1 = r_file.url()
        self.assertIsNotNone(ticket_url1)
        ticket_url2 = r_file.url()
        self.assertNotEqual(ticket_url1, ticket_url2)

        # Download file
        fd, path = tempfile.mkstemp()
        os.close(fd)

        try:
            r_file.download(path)

            with open(path, "rb") as f:
                data = f.read()
            self.assertEqual(data, poem)
        finally:
            os.remove(path)

        # Read acquisitions
        acquisitions = r_session.acquisitions()
        self.assertIsNotNone(acquisitions)
        self.assertEqual(len(acquisitions), 1)

        r_acquisition = acquisitions[0]
        self.assertEqual(r_acquisition.id, self.acquisition_id)
        self.assertEqual(r_acquisition.session, self.session_id)

    def test_tag_mixins(self):
        fw = self.fw

        for container_type in ["group", "project", "session", "acquisition"]:
            cid = getattr(self, "{0}_id".format(container_type), None)
            self.assertIsNotNone(cid)

            getter = getattr(self.fw, "get_{0}".format(container_type), None)
            self.assertIsNotNone(getter)

            container = getter(cid)
            self.assertIsNotNone(container)

            initial_tags = container.tags
            self.assertFalse(bool(initial_tags))

            container.add_tag("tag1")
            container.add_tag("tag2")

            container = getter(cid)
            self.assertEqual(2, len(container.tags))
            self.assertIn("tag1", container.tags)
            self.assertIn("tag2", container.tags)

            # Rename and delete
            container.rename_tag("tag2", "tag3")
            container.delete_tag("tag1")

            container = getter(cid)
            self.assertEqual(["tag3"], container.tags)
