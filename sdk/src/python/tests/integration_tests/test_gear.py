import unittest
from sdk_test_case import SdkTestCase

import flywheel


class GearTestCases(SdkTestCase):
    def setUp(self):
        self.gear_id = None

    def tearDown(self):
        if self.gear_id:
            self.fw.delete_gear(self.gear_id)

    def test_gears(self):
        fw = self.fw

        gear = flywheel.Gear(
            name=self.rand_string_lower(), label=self.rand_string(), description=self.rand_string(), version=self.rand_string(), author=self.rand_string(), maintainer=self.rand_string(), license="Other", source="http://example.example", url="http://example.example", config={}, inputs={}
        )

        gear_doc = flywheel.GearDoc(category="utility", gear=gear)

        # Add
        self.gear_id = gear_id = fw.add_gear(gear.name, gear_doc)
        self.assertIsNotNone(gear_id)

        # Get
        r_gear = fw.get_gear(gear_id)
        self.assertEqual(r_gear.gear.name, gear.name)
        self.assertTimestampBeforeNow(r_gear.created)
        self.assertGreaterEqual(r_gear.modified, r_gear.created)
        self.assertFalse(r_gear.is_analysis_gear())

        # Get invocation
        gear_schema = fw.get_gear_invocation(gear_id)
        self.assertNotEmpty(gear_schema)
        self.assertIn("$schema", gear_schema)
        self.assertTrue(gear_schema["$schema"].startswith("http://json-schema.org"))

        # Get All
        gears = fw.get_all_gears()
        self.assertIn(r_gear, gears)

        # Delete
        fw.delete_gear(gear_id)
        self.gear_id = None
        gears = fw.get_all_gears()
        self.assertNotIn(r_gear, gears)


def create_test_gear(category="utility"):
    #
    ## Do not modify the below gear document without checking the other callees!
    #
    gear = flywheel.Gear(
        name=SdkTestCase.rand_string_lower(),
        label=SdkTestCase.rand_string(),
        description=SdkTestCase.rand_string(),
        version=SdkTestCase.rand_string(),
        author=SdkTestCase.rand_string(),
        maintainer=SdkTestCase.rand_string(),
        license="Other",
        source="http://example.example",
        url="http://example.example",
        config={},
        inputs={"any-file": {"base": "file"}},
    )

    gear_doc = flywheel.GearDoc(category=category, gear=gear, exchange=flywheel.GearExchange(git_commit="aex", rootfs_hash="sha384:oy", rootfs_url="http://example.example"))

    return SdkTestCase.fw.add_gear(gear.name, gear_doc)
