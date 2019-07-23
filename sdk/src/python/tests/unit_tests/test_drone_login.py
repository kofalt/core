import unittest
from unittest import mock
import flywheel


class DroneLoginTestCases(unittest.TestCase):
    def test_create_drone_client_should_use_insecure_protocol_if_insecure(self):
        status = {
            'is_device': True,
            'origin': {'id': 'device_id'},
            'key': 'device_key'
        }
        with mock.patch('requests.Session') as m:
            m.get = mock.MagicMock(json=mock.MagicMock(return_value=status), ok=True)
            flywheel.create_drone_client('host', 'secret', 'method', 'name',
                                         insecure=True)
            m.get.assert_called_with('http://host:443/api/auth/status')

if __name__ == '__main__':
    unittest.main()
