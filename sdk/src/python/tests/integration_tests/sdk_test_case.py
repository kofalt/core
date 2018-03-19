import os, random, string
from datetime import datetime, timedelta
import dateutil.tz
import flywheel
import unittest

api_key = os.environ['SdkTestKey']
FLYWHEEL_CLIENT=flywheel.Flywheel(api_key)
ROOT_CLIENT=flywheel.Flywheel(api_key, root=True)

HEX_DIGITS = '0123456789abcdef'
TD_ZERO = timedelta()
TZ_UTC = dateutil.tz.tzutc()

def utcnow():
    # datetime requires tzinfo for comparison
    return datetime.utcnow().replace(tzinfo=TZ_UTC)

class SdkTestCase(unittest.TestCase):
    fw = FLYWHEEL_CLIENT
    fw_root = ROOT_CLIENT

    @classmethod
    def rand_string_lower(self, length=10):
        return self._rand_string(length, string.ascii_lowercase)

    @classmethod
    def rand_string(self, length=10):
        return self._rand_string(length, string.ascii_lowercase + string.ascii_uppercase)

    @classmethod
    def rand_hex(self, length=24):
        return self._rand_string(length, HEX_DIGITS)

    @classmethod
    def _rand_string(self, length, glyphs):
        return ''.join( random.choice(glyphs) for _ in range(length) )

    def assertNotEmpty(self, container):
        if container is None or len(container) == 0:
            raise AssertionError('Expected a non-empty value, got: "' + str(container) + '" instead.')

    def assertEmpty(self, container):
        if container is not None and len(container) > 0:
            raise AssertionError('Expected an empty value, got: "' + str(container) + '" instead.')

    def assertTimestampNear(self, value, expected, toleranceSec=5):
        d_allowed = timedelta(seconds=toleranceSec)
        d_actual = abs(expected - value)
        if d_actual > d_allowed:
            raise AssertionError('Expected time ' + str(value) + ' to be close to ' + str(expected))

    def assertTimestampNearNow(self, value, toleranceSec=5):
        self.assertTimestampNear(value, utcnow(), toleranceSec)
        
    def assertTimestampBefore(self, value, expected, toleranceSec=0):
        if toleranceSec:
            expected = expected + timedelta(seconds=toleranceSec)
        if (expected - value) < TD_ZERO:
            raise AssertionError('Expected time ' + str(value) + ' to be before ' + str(expected))

    def assertTimestampBeforeNow(self, value, toleranceSec=5):
        self.assertTimestampBefore(value, utcnow(), toleranceSec)

    def assertTimestampAfter(self, value, expected, toleranceSec=0):
        if toleranceSec:
            expected = expected - timedelta(seconds=toleranceSec)
        if (expected - value) > TD_ZERO:
            raise AssertionError('Expected time ' + str(value) + ' to be after ' + str(expected))

    def assertDownloadFileTextEquals(self, method, id, filename, expected):
        content = method(id, filename)
        self.assertIsNotNone(content)
        content = content.decode('utf-8')

        self.assertEqual(content, expected)

    def assertDownloadFileTextEqualsWithTicket(self, method, id, filename, expected):
        download_url = method(id, filename)
        
        self.assertIsNotNone(download_url)

        resp = self.fw.api_client.rest_client.GET(download_url, _preload_content=False)
        self.assertIsNotNone(resp)
        try:
            self.assertEqual(resp.status_code, 200)

            content = resp.content
            self.assertIsNotNone(content)
            
            content = content.decode('utf-8')
            
            self.assertEqual(content, expected)
        finally:
            resp.close()




        