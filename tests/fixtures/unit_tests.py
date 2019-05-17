import mock
import os

import attrdict
import mongomock
import pytest
import urllib
from requests.structures import CaseInsensitiveDict

import api.config

SCITRAN_CORE_DRONE_SECRET = os.environ["SCITRAN_CORE_DRONE_SECRET"]


@pytest.fixture(scope="session")
def session(app):
    """Return session Object which used by as_{drone, admin, public, user} fixtures"""

    def _session():
        return ApiAccessor(app)

    return _session


@pytest.fixture(scope="session")
def api_db(app):
    """Return mongo client mock for the api db"""
    return api.config.db


@pytest.fixture(scope="session")
def log_db(app):
    """Return mongo client mock for the log db"""
    return api.config.log_db


@pytest.fixture(scope="session")
def es(app):
    """Return Elasticsearch mock (MagickMock instance)"""
    return api.config.es


@pytest.yield_fixture(scope="session")
def app():
    """Return api instance that uses mocked os.environ, ElasticSearch and MongoClient"""
    test_env = {"SCITRAN_CORE_DRONE_SECRET": SCITRAN_CORE_DRONE_SECRET, "TERM": "xterm"}  # enable terminal features - useful for pdb sessions
    env_patch = mock.patch.dict(os.environ, test_env, clear=True)
    env_patch.start()
    es_patch = mock.patch("elasticsearch.Elasticsearch")
    es_patch.start()
    mongo_patch = mock.patch("pymongo.MongoClient", new=mongomock.MongoClient)
    mongo_patch.start()
    # NOTE db and log_db is created at import time in api.config
    # reloading the module is needed to use the mocked MongoClient

    # Hack because of the containerhandler's import time instantiation
    # with this the containerhandler will use the same mock db instance
    import api.config

    reload(api.config)
    import api.web.start

    yield api.web.start.app_factory()
    mongo_patch.stop()
    es_patch.stop()
    env_patch.stop()


@pytest.fixture(scope="session")
def config(app):
    """Return app config accessor"""
    # NOTE depends on the app fixture as it's reloading the config module
    # NOTE the config fixture is session scoped (consider parallel tests)
    # NOTE use dict notation for assignment (eg `config['key'] = 'v'` - AttrDict limitation)
    return attrdict.AttrDict(api.config.__config)


class ApiAccessor(object):
    def __init__(self, app, **defaults):
        self.app = app
        self.defaults = defaults
        self.headers = CaseInsensitiveDict({})
        self.params = {}

    def __getattr__(self, name):
        """Return convenience HTTP method for `name`"""
        if name in ("head", "get", "post", "put", "delete"):

            def http_method(path, **kwargs):
                # NOTE using WebOb requests in unit tests is fundamentally different
                # to using a requests.Session in integration tests. See also:
                # http://webapp2.readthedocs.io/en/latest/guide/testing.html#app-get-response
                # https://github.com/Pylons/webob/blob/master/webob/request.py
                for key, value in self.defaults.items():
                    kwargs.setdefault(key, value)

                headers = CaseInsensitiveDict({})
                headers.update(self.headers)
                headers.update(kwargs.get("headers", {}))
                kwargs["headers"] = headers

                if self.params:
                    query_string = urllib.urlencode(self.params)
                    url = "/api" + path + "?" + query_string
                else:
                    url = "/api" + path

                kwargs["method"] = name.upper()

                response = self.app.get_response(url, **kwargs)
                response.ok = response.status_code == 200
                return response

            return http_method
        raise AttributeError
