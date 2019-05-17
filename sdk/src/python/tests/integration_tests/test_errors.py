import unittest
from sdk_test_case import SdkTestCase

import flywheel


class ErrorTestCases(SdkTestCase):
    def test_error_message(self):
        try:
            self.fw.add_job({})  # Invalid request
            self.fail("Expected an error creating invalid job")
        except flywheel.ApiException as e:
            self.assertNotEmpty(e.body)
            self.assertEqual(e.detail, "Job must specify gear")
