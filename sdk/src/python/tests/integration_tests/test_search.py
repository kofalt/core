import unittest
import time
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel


class SearchTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    # Ref https://github.com/flywheel-io/sdk/issues/31
    @unittest.skip("No elastic search container")
    def test_search(self):
        fw = self.fw

        acquisition = fw.get_acquisition(self.acquisition_id)
        self.assertEqual(acquisition.id, self.acquisition_id)

        # Allow time for search to index
        # Ref https://github.com/flywheel-io/sdk/issues/32
        time.sleep(1)

        query = flywheel.SearchQuery(return_type="session", search_string=acquisition.label)
        search_result = fw.search(query)
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result[0]["return_type"], "session")

        query = flywheel.SearchQuery(return_type="acquisition", search_string=acquisition.label)
        search_result = fw.search(query)
        self.assertEqual(len(search_result), 1)
        self.assertEqual(search_result[0]["return_type"], "acquisition")
