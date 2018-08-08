import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel


class ContainersTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_get_container(self):
        cgroup = self.fw.get_container(self.group_id)
        cproject = self.fw.get_container(self.project_id)
        csession = self.fw.get_container(self.session_id)
        cacquisition = self.fw.get_container(self.acquisition_id)

        group = self.fw.get_group(self.group_id)
        project = self.fw.get_project(self.project_id)
        session = self.fw.get_session(self.session_id)
        acquisition = self.fw.get_acquisition(self.acquisition_id)

        self.assertEqual(dict(cgroup), dict(group))
        self.assertEqual(dict(cproject), dict(project))
        self.assertEqual(dict(csession), dict(session))
        self.assertEqual(dict(cacquisition), dict(acquisition))

    def test_modify_container(self):
        self.fw.modify_container(self.acquisition_id, {"label": "NewName"})

        cacquisition = self.fw.get_container(self.acquisition_id)
        acquisition = self.fw.get_acquisition(self.acquisition_id)

        self.assertEqual(cacquisition.label, "NewName")
        self.assertEqual(dict(cacquisition), dict(acquisition))

    def test_delete_container(self):
        self.fw.delete_container(self.session_id)

        sessions = self.fw.get_project_sessions(self.project_id)
        self.assertTrue(len(sessions) == 0)
