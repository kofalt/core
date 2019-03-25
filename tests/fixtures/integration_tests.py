import copy
import os
import shutil

import attrdict
import fs.move
import fs.path
import pymongo
import pytest
import requests

from api import config, files, util

# load required envvars w/ the same name
SCITRAN_PERSISTENT_DB_LOG_URI = os.environ['SCITRAN_PERSISTENT_DB_LOG_URI']
SCITRAN_PERSISTENT_DB_URI = os.environ['SCITRAN_PERSISTENT_DB_URI']
SCITRAN_SITE_API_URL = os.environ['SCITRAN_SITE_API_URL']


@pytest.fixture(scope='session')
def session():
    """Return session Object which used by as_{drone, admin, public, user} fixtures"""
    def session():
        return BaseUrlSession()
    return session


@pytest.fixture(scope='session')
def api_db():
    """Return mongo client for the api db"""
    return pymongo.MongoClient(SCITRAN_PERSISTENT_DB_URI).get_database()


@pytest.fixture(scope='session')
def set_env():
    """Set environment variables for the duration of a session"""
    initial_state = os.environ.copy()
    # set desired environment
    os.environ['FLYWHEEL_RELEASE'] = 'emerald.x.y.z'

    yield set_env

    # return to initial state
    os.environ['FLYWHEEL_RELEASE'] = initial_state.get('FLYWHEEL_RELEASE', '')


@pytest.fixture(scope='function')
def ensure_version_singleton(api_db):
    original = api_db.singletons.find_one({'_id': 'version'})
    api_db.singletons.update({'_id': 'version'}, {'db_version': 1}, upsert=True)

    yield ensure_version_singleton

    if original is not None:
        api_db.singletons.update({'_id': 'version'}, original)
    else:
        api_db.singletons.remove({'_id': 'version'})


@pytest.fixture(scope='session')
def log_db():
    """Return mongo client for the log db"""
    return pymongo.MongoClient(SCITRAN_PERSISTENT_DB_LOG_URI).get_database()


@pytest.fixture(scope='function')
def with_user(data_builder, randstr, as_public):
    """Return AttrDict with new user, api-key and api-accessor"""
    api_key = randstr()
    user = data_builder.create_user(api_key=api_key, root=False)
    session = copy.deepcopy(as_public)
    session.headers.update({'Authorization': 'scitran-user ' + api_key})
    return attrdict.AttrDict(user=user, api_key=api_key, session=session)

@pytest.fixture(scope='function')
def site_providers(api_db, data_builder):
    current_site_settings = api_db.singletons.find_one({'_id': 'site'})

    # Set site providers
    providers = {
        'compute': data_builder.get_or_create('compute_provider'),
    }
    api_db.singletons.update({'_id': 'site'}, {'providers': providers}, upsert=True)

    yield providers

    if current_site_settings:
        api_db.singletons.update({'_id': 'site'}, current_site_settings)
    else:
        api_db.singletons.remove({'_id': 'site'})


class BaseUrlSession(requests.Session):
    """Requests session subclass using core api's base url"""
    def __init__(self, *args, **kwargs):
        super(BaseUrlSession, self).__init__(*args, **kwargs)
        self.headers.update({ 'X-Accept-Feature': 'beta' })

    def request(self, method, url, **kwargs):
        return super(BaseUrlSession, self).request(method, SCITRAN_SITE_API_URL + url, **kwargs)

