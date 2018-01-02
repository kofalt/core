from gen import swagger_client

class Flywheel:
    def __init__(self, api_key):
        self.api_key = api_key

        self._config = swagger_client.Configuration()
        self._config.api_key['Authorization'] = 'scitran-user ' + api_key

        self._apiclient = swagger_client.ApiClient(self._config)

        self._users = None

    @property
    def users(self):
    	if self._users is None:
    		self._users = swagger_client.UsersApi(self._apiclient)

    	return self._users






