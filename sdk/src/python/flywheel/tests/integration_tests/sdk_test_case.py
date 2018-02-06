import os, random, string
from datetime import datetime, timedelta
import dateutil.tz
import flywheel
import unittest

api_key = os.environ['SdkTestKey']
FLYWHEEL_CLIENT=flywheel.Flywheel(api_key)

HEX_DIGITS = '0123456789abcdef'
TD_ZERO = timedelta()
TZ_UTC = dateutil.tz.tzutc()

def utcnow():
    # datetime requires tzinfo for comparison
    return datetime.utcnow().replace(tzinfo=TZ_UTC)

class SdkTestCase(unittest.TestCase):
    fw = FLYWHEEL_CLIENT

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
        
