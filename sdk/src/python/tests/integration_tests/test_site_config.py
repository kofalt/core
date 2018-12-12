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

    def test_site_settings(self):
        settings = self.fw.get_site_settings()
        self.assertIsNotNone(settings)

        gears = settings.get('center_gears')
        if gears is None:
            gears = []

        self.fw.modify_site_settings({
            'center_gears': ['test']
        })

        try:
            settings2 = self.fw.get_site_settings()
            self.assertIsNotNone(settings2.get('center_gears'))
            self.assertIn('test', settings2['center_gears'])

        finally:
            self.fw.modify_site_settings({
                'center_gears': gears
            })
