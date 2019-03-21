import os
import copy
import json
import logging
import pymongo
import datetime
import elasticsearch

from flywheel_common.storage import create_flywheel_fs
from flywheel_common import logging as flylogging

from . import util
from .dao.dbutil import try_replace_one, try_update_one

logging.basicConfig(
    format='%(asctime)s %(name)16.16s %(filename)24.24s %(lineno)5d:%(levelname)4.4s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
)
log = flylogging.getContextLogger('scitran.api')

logging.getLogger('scitran.api').addHandler(logging.StreamHandler())

# Increment counters for root logger. Increments for warning and higher
from .metrics.log_handler import MetricsLogHandler
logging.getLogger().addHandler(MetricsLogHandler())

# NOTE: Keep in sync with environment variables in sample.config file.
DEFAULT_CONFIG = {
    'core': {
        'debug': False,
        'log_level': 'info',
        'access_log_enabled': False,
        'drone_secret': None,
    },
    'site': {
        'id': 'local',
        'name': 'Local',
        'api_url': 'https://localhost/api',
        'redirect_url': 'https://localhost',
        'central_url': 'https://sdmc.scitran.io/api',
        'registered': False,
        'ssl_cert': None,
        'inactivity_timeout': None,
        'upload_maximum_bytes': '10737418240',
    },
    'queue': {
        'max_retries': 3,
        'retry_on_fail': False
    },
    'auth': {
        'google': {
            "id_endpoint" : "https://www.googleapis.com/oauth2/v3/userinfo",
            "client_id" : "979703271380-q85tbsupddmb7996q30244368r7e54lr.apps.googleusercontent.com",
            "token_endpoint" : "https://accounts.google.com/o/oauth2/token",
            "verify_endpoint" : "https://www.googleapis.com/oauth2/v1/tokeninfo",
            "refresh_endpoint" : "https://www.googleapis.com/oauth2/v4/token",
            "auth_endpoint" : "https://accounts.google.com/o/oauth2/auth"
        }
    },
    'features': {
        # Permanent API features should exist here
        'job_tickets': True,   # Job completion tickets, which allow a new success/failure flow and advanced profiling.
        'job_ask': True,       # Job queue /jobs/ask route.
        'multiproject': False  # Multiproject support
    },
    'persistent': {
        'db_uri':     'mongodb://localhost:27017/scitran',
        'db_log_uri': 'mongodb://localhost:27017/logs',
        'db_connect_timeout': '2000',
        'db_server_selection_timeout': '3000',
        'data_path': os.path.join(os.path.dirname(__file__), '../persistent/data'),
        'elasticsearch_host': 'localhost:9200',
        'fs_url': None,
        'support_legacy_fs': True,
    },
    'master_subject_code': {
        'size': '6',
        'prefix': 'fw',
        'chars': 'BCDFGHJKLMNPQRSTVWXYZ123456789',
        'verify_config': None
    },
}

def apply_env_variables(config):
    # Overwrite default config values with SCITRAN env variables if available

    # Load auth config from file if available
    if 'SCITRAN_AUTH_CONFIG_FILE' in os.environ:
        file_path = os.environ['SCITRAN_AUTH_CONFIG_FILE']
        with open(file_path) as config_file:
            environ_config = json.load(config_file)
        config['auth'] = environ_config.get('auth', DEFAULT_CONFIG['auth'])

    for outer_key, scoped_config in config.iteritems():
        if outer_key in ('auth', 'features'):
            # Auth is loaded via file
            continue
        try:
            for inner_key in scoped_config:
                key = 'SCITRAN_' + outer_key.upper() + '_' + inner_key.upper()
                if key in os.environ:
                    value = os.environ[key]
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.lower() == 'none':
                        value = None
                    config[outer_key][inner_key] = value
        except Exception: # pylint: disable=broad-except
            # ignore uniterable keys like `created` and `modified`
            pass

    # Set feature flags based on FLYWHEEL_FEATURE_xx
    feature_prefix = 'FLYWHEEL_FEATURE_'
    for key, value in os.environ.items():
        if not key.startswith(feature_prefix):
            continue
        feature_key = key[len(feature_prefix):].lower()
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        config['features'][feature_key] = value

    return config

def apply_runtime_features(config):
    """Apply any features that must be determined at runtime"""
    config['features']['signed_url'] = storage.is_signed_url()
    return config

# Create config for startup, will be merged with db config when db is available
__config = apply_env_variables(copy.deepcopy(DEFAULT_CONFIG))
__config_persisted = False
__last_update = datetime.datetime.utcfromtimestamp(0)

if not os.path.exists(__config['persistent']['data_path']):
    os.makedirs(__config['persistent']['data_path'])
log.debug('Persistent data path: %s', __config['persistent']['data_path'])

if not __config['persistent']['fs_url']:
    _path = os.path.join(__config['persistent']['data_path'], 'v1')
    if not os.path.exists(_path):
        os.makedirs(_path)
    __config['persistent']['fs_url'] = 'osfs://' + _path
log.debug('Persistent fs url: %s', __config['persistent']['fs_url'])

db = pymongo.MongoClient(
    __config['persistent']['db_uri'],
    j=True, # Requests only return once write has hit the DB journal
    connectTimeoutMS=__config['persistent']['db_connect_timeout'],
    serverSelectionTimeoutMS=__config['persistent']['db_server_selection_timeout'],
    connect=False, # Connect on first operation to avoid multi-threading related errors
).get_default_database()
log.debug(str(db))

log_db = pymongo.MongoClient(
    __config['persistent']['db_log_uri'],
    j=True, # Requests only return once write has hit the DB journal
    connectTimeoutMS=__config['persistent']['db_connect_timeout'],
    serverSelectionTimeoutMS=__config['persistent']['db_server_selection_timeout'],
    connect=False, # Connect on first operation to avoid multi-threading related errors
).get_default_database()
log.debug(str(log_db))

es = elasticsearch.Elasticsearch([__config['persistent']['elasticsearch_host']])

# validate the lists of json schemas
schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../swagger/schemas')

def create_or_recreate_ttl_index(coll_name, index_name, ttl):
    if coll_name in db.collection_names():
        index_list = db[coll_name].index_information()
        if index_list:
            for index in index_list:
                # search for index by given name
                # example: "timestamp_1": {"key": [["timestamp", 1]], ...}
                if index_list[index]['key'][0][0] == index_name:
                    if index_list[index].get('expireAfterSeconds', None) != ttl:
                        # drop existing, recreate below
                        db[coll_name].drop_index(index)
                        break
                    else:
                        # index exists with proper ttl, bail
                        return
    db[coll_name].create_index(index_name, expireAfterSeconds=ttl)


def initialize_db():
    log.info('Initializing database, creating indexes in background')

    # Create indexes in background
    kwargs = { 'background': True }

    db.users.create_index('api_key.key', **kwargs)
    db.users.create_index('deleted', **kwargs)
    db.apikeys.create_index([('type', 1), ('origin.id', 1)], **kwargs)
    db.queries.create_index('creator', **kwargs)
    db.projects.create_index([('group', 1), ('label', 1)], **kwargs)
    # The following two indexes hardly depend on that the `deleted` field is a timestamp not just a boolean flag,
    # otherwise we couldn't have multiple deleted subjects with the same code which is required
    # because deleting a subject and creating a new one with the same code is a valid usecase.
    db.subjects.create_index([('project', 1), ('code', 1), ('deleted', 1)],
        partialFilterExpression={'code': {'$exists': True}}, unique=True, **kwargs)
    db.subjects.create_index([('project', 1), ('master_code', 1), ('deleted', 1)],
        partialFilterExpression={'master_code': {'$exists': True}}, unique=True, **kwargs)
    db.sessions.create_index([('project', 1), ('label', 1)], **kwargs)
    db.sessions.create_index([('subject', 1), ('label', 1)], **kwargs)
    db.sessions.create_index('uid', **kwargs)
    db.sessions.create_index('created', **kwargs)
    db.acquisitions.create_index([('session', 1), ('label', 1)], **kwargs)
    db.acquisitions.create_index('uid', **kwargs)
    db.acquisitions.create_index('collections', **kwargs)
    db.analyses.create_index([('parent.type', 1), ('parent.id', 1)], **kwargs)
    db.jobs.create_index([('inputs.id', 1), ('inputs.type', 1)], **kwargs)
    db.jobs.create_index([('state', 1), ('now', 1), ('modified', 1)], **kwargs)
    db.jobs.create_index('related_container_ids', **kwargs)
    db.jobs.create_index('created', **kwargs)
    db.jobs.create_index('modified', **kwargs)
    db.jobs.create_index('parents', **kwargs)
    db.jobs.create_index('tags', **kwargs)
    db.jobs.create_index([('destination.type', 1), ('destination.id', 1)], **kwargs)
    db.jobs.create_index([('inputs.type', 1), ('inputs.id', 1)], **kwargs)
    db.gears.create_index('name', **kwargs)
    db.gears.create_index('gear.custom.flywheel.invalid', **kwargs)
    db.batch.create_index('jobs', **kwargs)
    db.project_rules.create_index('project_id', **kwargs)
    db.data_views.create_index('parent', **kwargs)
    db.master_subject_codes.create_index(
        [('first_name', 1), ('last_name', 1), ('date_of_birth', 1), ('patient_id', 1)],
        unique=True, **kwargs)
    db.master_subject_codes.create_index('patient_id',
        partialFilterExpression={'patient_id': {'$exists': True}},
        unique=True, **kwargs)

    # Create indexes on container collection
    for coll in ['groups', 'projects', 'subjects', 'sessions', 'acquisitions', 'analyses', 'collections']:
        db[coll].create_index('deleted', **kwargs)
        db[coll].create_index('permissions', **kwargs)

    for coll in ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses']:
        db[coll].create_index('parents', **kwargs)

    if __config['core']['access_log_enabled']:
        log_db.access_log.create_index('context.ticket_id', **kwargs)
        log_db.access_log.create_index([('timestamp', pymongo.DESCENDING)], **kwargs)

    # Mongo TTL indexes are measured in seconds.
    # Ref: http://api.mongodb.com/python/current/api/pymongo/collection.html#pymongo.collection.Collection.create_index
    #
    # IMPORTANT: if the TTL field is missing, documents will not expire.
    create_or_recreate_ttl_index('authtokens',  'timestamp', 30 * 24 * 60 * 60) # 30 days
    create_or_recreate_ttl_index('uploads',     'timestamp',       1 * 60 * 60) #  1 hour
    create_or_recreate_ttl_index('downloads',   'timestamp',            1 * 60) #  1 minute
    # IMPORTANT: this controls job orphan logic. Ref queue.py
    create_or_recreate_ttl_index('job_tickets', 'timestamp',       6 * 60 * 60) #  6 hours
    create_or_recreate_ttl_index('gear_tickets', 'timestamp', 1 * 24 * 60 * 60) #  1 day

    from .site import site_settings
    site_settings.initialize()

    now = datetime.datetime.utcnow()
    try_update_one(db,
                   'groups', {'_id': 'unknown'},
                   {'$setOnInsert': {'created': now, 'modified': now, 'label': 'Unknown', 'permissions': []}},
                   upsert=True)

def get_config():
    global __last_update, __config, __config_persisted #pylint: disable=global-statement
    now = datetime.datetime.utcnow()
    if not __config_persisted:
        initialize_db()
        log.info('Persisting configuration')

        db_config = db.singletons.find_one({'_id': 'config'})
        if db_config is not None:
            startup_config = copy.deepcopy(__config)
            startup_config = util.deep_update(startup_config, db_config)
            # Precedence order for config is env vars -> db values -> default
            __config = apply_env_variables(startup_config)
        else:
            __config['created'] = now
        __config['modified'] = now

        # Attempt to set the config object, ignoring duplicate key problems.
        # This worker might have lost the race - in which case, be grateful about it.
        #
        # Ref:
        # https://github.com/scitran/core/issues/212
        # https://github.com/scitran/core/issues/844
        _, success = try_replace_one(db, 'singletons', {'_id': 'config'}, __config, upsert=True)
        if not success:
            log.debug('Worker lost config upsert race; ignoring.')

        __config = apply_runtime_features(__config)
        __config_persisted = True
        __last_update = now
    elif now - __last_update > datetime.timedelta(seconds=120):
        log.debug('Refreshing configuration from database')
        __config = db.singletons.find_one({'_id': 'config'})
        __config = apply_runtime_features(__config)
        __last_update = now
    return __config

def get_public_config():
    cfg = get_config()

    auth = copy.deepcopy(cfg.get('auth'))
    for values in auth.itervalues():
        values.pop('client_secret', None)

    return {
        'created': __config.get('created'),
        'modified': __config.get('modified'),
        'site': __config.get('site'),
        'auth': auth,
        'signed_url': cfg['features']['signed_url'],  # Legacy note: clients expect top-level signed_url key
        'features': cfg['features']
    }

def get_version():
    version_object = db.singletons.find_one({'_id': 'version'})
    if not version_object:
        return version_object

    version_object['release'] = get_release_version()
    version_object['cli_version'] = os.environ.get('CLI_VERSION', '')
    version_object['flywheel_release'] = os.environ.get('FLYWHEEL_RELEASE', '')

    return version_object

def is_multiproject_enabled():
    return get_feature('multiproject', False)

def get_item(outer, inner):
    return get_config()[outer][inner]


def get_auth(auth_type):
    return get_config()['auth'][auth_type]


def get_feature(key, dflt=None):
    return get_config()['features'].get(key, dflt)

# Application version file path
release_version_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../api_version.txt')
release_version = ''

def get_release_version():
    """Get the semantic application release version (may be none)"""
    global release_version #pylint: disable=global-statement
    if not release_version and os.path.isfile(release_version_file_path):
        try:
            with open(release_version_file_path, 'r') as f:
                release_version = f.read().strip()
        except IOError:
            pass
    return release_version

# Storage configuration
#primary_storage = create_flywheel_fs(__config['persistent']['fs_url'])
# primary_storage = create_flywheel_fs(__config['persistent']['data_path'])

# local_fs must be PyFS with osfs for using the local get_fs functions for file manipulation
#local_fs = create_flywheel_fs('osfs://' + __config['persistent']['data_path'])
# This is used for the base of the temp_fs path
local_fs_url = __config['persistent']['data_path']

#local_fs = get_provider_instance({
#    'provider_class': 'storage',
#    'provider_type': 'osfs',
#    'config': {'path': __config['persistent']['data_path']}
#})


support_legacy_fs = __config['persistent']['support_legacy_fs']

### Temp fix for 3-way split storages, where files exist in
# 1. $SCITRAN_PERSISTENT_DATA_PATH/v0/ha/sh/v0-hash  (before abstract fs)
# 2. $SCITRAN_PERSISTENT_DATA_PATH/v1/uu/id/uuid     (using abstract fs, without fs_url - defaulting to data_path/v1)
# 3. $SCITRAN_PERSISTENT_FS_URL/uu/id/uuid           (using abstract fs, with fs_url)
data_path2 = __config['persistent']['data_path'] + '/v1'
if os.path.exists(data_path2):
    log.warning('Path %s exists - enabling 3-way split storage support', data_path2)
    local_fs2 = create_flywheel_fs('osfs://' + data_path2)

else:
    local_fs2 = None
###


