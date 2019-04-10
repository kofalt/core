"""Provides Drone-based login credentials"""

class DroneLogin(object):
    """Wrap drone login credentials"""

    def __init__(self, host, secret, method, name, port=None):
        """Initialize the Drone Login info

        :param str host: The hostname of the flywheel instance
        :param str secret: The drone secret
        :param str method: The method (device type)
        :param str name: The name of the device
        :param int port: The optional port (if not 443)
        """
        self.host = host
        self.secret = secret
        self.method = method
        self.name = name
        self.port = port or 443

    def get_headers(self):
        """Get the headers required for authentication.

        :return: A dictionary of auth headers
        :rtype: dict
        """
        return {
            'X-SciTran-Auth': self.secret,
            'X-SciTran-Method': self.method,
            'X-SciTran-Name': self.name
        }
