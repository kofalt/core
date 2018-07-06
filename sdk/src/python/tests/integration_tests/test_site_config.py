import unittest
from sdk_test_case import SdkTestCase

import flywheel

class UsersTestCases(SdkTestCase):
    def test_get_config(self):
        config = self.fw.get_config()
        self.assertIsNotNone(config)

        self.assertIsNotNone(config.site)
        self.assertIsNotNone(config.modified)
        self.assertIsNotNone(config.created)
        self.assertIsNotNone(config.auth)
        self.assertIsNotNone(config.signed_url)
        self.assertEqual(type(config.signed_url), bool)

        site = config.site
        self.assertIsNotNone(site.name)
        self.assertIsNotNone(site.central_url)
        self.assertIsNotNone(site.api_url)
        self.assertIsNotNone(site.registered)

