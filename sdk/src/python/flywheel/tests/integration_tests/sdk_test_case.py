import os, random, string
import flywheel
import unittest

api_key = os.environ['SdkTestKey']
FLYWHEEL_CLIENT=flywheel.Flywheel(api_key)

HEX_DIGITS = '0123456789abcdef'

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

    def assertContains(self, container, item):
        if item not in container:
            raise AssertionError('Item ' + str(item) + ' not found in container')

        
