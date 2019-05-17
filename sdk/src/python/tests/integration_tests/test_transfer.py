import unittest
from sdk_test_case import SdkTestCase

import flywheel


class TransferTestCases(SdkTestCase):
    def test_bad_uploads(self):
        fw = self.fw

        acquisition_id = "INVALID_ACQUISITION_ID"

        # invalid file spec
        self.assertRaises(RuntimeError, fw.upload_file_to_acquisition, acquisition_id, flywheel.FileSpec(None))

        # Non-existant upload path
        self.assertRaises(IOError, fw.upload_file_to_acquisition, acquisition_id, flywheel.FileSpec("/dev/null/does-not-exist"))

        # Invalid upload path
        poem = "Are full of passionate intensity."
        try:
            fw.upload_file_to_acquisition(acquisition_id, flywheel.FileSpec("yeats.txt", poem))
            self.fail("Expected ApiException when uploading to nonexistent location")
        except flywheel.ApiException as e:
            self.assertEqual(e.status, 404)

    def test_bad_downloads(self):
        fw = self.fw

        acquisition_id = "INVALID_ACQUISITION_ID"

        # Non-existant download target
        self.assertRaises(IOError, fw.download_file_from_acquisition, acquisition_id, "does-not-exist", "/dev/null/does-not-exist")

        # Invalid download path
        try:
            fw.download_file_from_acquisition_as_data("DOES_NOT_EXIST", "does-not-exist")
            self.fail("Expected ApiException when downloading from nonexistent location")
        except flywheel.ApiException as e:
            self.assertEqual(e.status, 404)
