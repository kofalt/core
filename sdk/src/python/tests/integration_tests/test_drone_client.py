import os
import unittest

import flywheel
import pytest
from six.moves.urllib.parse import urlparse

import init_db
from sdk_test_case import SdkTestCase


class DroneClientTestCases(SdkTestCase):
    def test_drone_client(self):
        if self.fw_drone is None:
            pytest.skip('Cannot test drone_client outside of test container')

        status = self.fw_drone.get_auth_status()
        self.assertTrue(status.is_device)
