import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel

class ResolverTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_resolver(self):
        fw = self.fw
        group_id = self.group_id

        # Upload file acquisition
        poem = 'The Second Coming! Hardly are those words out'
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec('yeats.txt', poem))

        # Resolve group children
        result = fw.resolve([group_id])

        self.assertEqual(len(result.path), 1)
        r_group = result.path[0]
        self.assertEqual(r_group.id, group_id)

        self.assertEqual(len(result.children), 1)
        r_project = result.children[0]
        self.assertEqual(r_project.id, self.project_id)

        # Resolve project children
        result = fw.resolve('{0}/{1}'.format(group_id, r_project.label))
        self.assertEqual(len(result.path), 2)
        self.assertEqual(result.path[0], r_group)
        self.assertEqual(result.path[1], r_project)

        self.assertEqual(len(result.children), 1)
        r_session = result.children[0]
        self.assertEqual(r_session.project, self.project_id)
        self.assertEqual(r_session.id, self.session_id)

        # Resolve session children (using id string)
        result = fw.resolve('{0}/{1}/<id:{2}>'.format(group_id, r_project.label, self.session_id))
        self.assertEqual(len(result.path), 3)
        self.assertEqual(result.path[0], r_group)
        self.assertEqual(result.path[1], r_project)
        self.assertEqual(result.path[2], r_session)

        self.assertEqual(len(result.children), 1)
        r_acquisition = result.children[0]
        self.assertEqual(r_acquisition.session, self.session_id)
        self.assertEqual(r_acquisition.id, self.acquisition_id)

        # Finally, resolve acquisition files
        result = fw.resolve([group_id, r_project.label, r_session.label, r_acquisition.label])
        self.assertEqual(len(result.path), 4)
        self.assertEqual(result.path[0], r_group)
        self.assertEqual(result.path[1], r_project)
        self.assertEqual(result.path[2], r_session)
        self.assertEqual(result.path[3], r_acquisition)

        self.assertEqual(len(result.children), 1)
        r_file = result.children[0]
        self.assertEqual(r_file.name, 'yeats.txt')
        self.assertEqual(r_file.size, len(poem))

    def test_resolver_permissions(self):
        fw = self.fw
        group_id = self.group_id

        # Change project permission
        r_project = fw.get_project(self.project_id)
        self.assertEqual(len(r_project.permissions), 1)
        user_id = r_project.permissions[0].id

        fw.delete_project_user_permission(self.project_id, user_id)

        # Resolve group
        result = fw.resolve([group_id])

        self.assertEqual(len(result.path), 1)
        r_group = result.path[0]
        self.assertEmpty(result.children)

        # Try to resolve project
        try:
            fw.resolve([group_id, r_project.label])
            self.fail('Expected ApiException')
        except flywheel.ApiException as e:
            self.assertEqual(e.status, 403)

        # Try to resolve project as root
        result = self.fw_root.resolve([group_id])

        self.assertEqual(len(result.path), 1)
        self.assertEqual(len(result.children), 1)
        r_project = result.children[0]
        self.assertEqual(r_project.id, self.project_id)

        # Resolve project children
        result = self.fw_root.resolve('{0}/{1}'.format(group_id, r_project.label))
        self.assertEqual(len(result.path), 2)
        self.assertEqual(result.path[0], r_group)
        self.assertEqual(result.path[1], r_project)

        self.assertEqual(len(result.children), 1)
        r_session = result.children[0]
        self.assertEqual(r_session.project, self.project_id)
        self.assertEqual(r_session.id, self.session_id)


