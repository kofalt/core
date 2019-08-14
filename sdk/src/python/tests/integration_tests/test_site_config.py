import unittest
from sdk_test_case import SdkTestCase

import flywheel

class SiteConfigTestCases(SdkTestCase):
    def setUp(self):
        self.gear_id = None

    def tearDown(self):
        if self.gear_id:
            self.fw.delete_gear(self.gear_id)

    def test_get_config(self):
        config = self.fw.get_config()
        self.assertIsNotNone(config)

        self.assertIsNotNone(config.site)
        self.assertIsNotNone(config.modified)
        self.assertIsNotNone(config.created)
        self.assertIsNotNone(config.auth)
        self.assertIsNotNone(config.signed_url)
        self.assertEqual(type(config.signed_url), bool)

        # Multiproject should exist and be enabled for integration tests
        self.assertIsNotNone(config.features)
        self.assertIsNotNone(config.features.multiproject)
        self.assertTrue(config.features.job_ask)

        site = config.site
        self.assertIsNotNone(site.name)
        self.assertIsNotNone(site.central_url)
        self.assertIsNotNone(site.api_url)
        self.assertIsNotNone(site.registered)

    def test_site_settings(self):
        # Add a test gear
        gear = flywheel.Gear(
            name=self.rand_string_lower(),
            label=self.rand_string(),
            description=self.rand_string(),
            version=self.rand_string(),
            author=self.rand_string(),
            maintainer=self.rand_string(),
            license='Other',
            source='http://example.example',
            url='http://example.example',
            config={},
            inputs={}
        )

        gear_doc = flywheel.GearDoc(
            category='utility',
            gear=gear
        )

        self.gear_id = self.fw.add_gear(gear.name, gear_doc)

        # Get current settings
        settings = self.fw.get_site_settings()
        self.assertIsNotNone(settings)

        # We need to set the gears back to only site-gear but we cant since its not fully valid
        # gears = settings.get('center_gears')
        #if gears is None:
        #    gears = []
        gears = []

        self.fw.modify_site_settings({
            'center_gears': [gear.name]
        })

        try:
            settings2 = self.fw.get_site_settings()
            self.assertIsNotNone(settings2.get('center_gears'))
            self.assertIn(gear.name, settings2['center_gears'])

        finally:
            self.fw.modify_site_settings({
                'center_gears': gears
            })
