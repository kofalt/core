import unittest

import mock
from testfixtures import LogCapture

import api.web.request

class TestRequest(unittest.TestCase):
    def setUp(self):
        self.log_capture = LogCapture()
        self.request = api.web.request.SciTranRequest({})

    def tearDown(self):
        LogCapture.uninstall_all()

    def test_request_id(self):
        self.assertEqual(len(self.request.id), 19)

