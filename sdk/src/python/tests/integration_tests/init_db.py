import binascii
import os
import datetime
import bson

SCITRAN_PERSISTENT_DB_URI = os.environ.get('SCITRAN_PERSISTENT_DB_URI')
SCITRAN_ADMIN_API_KEY = binascii.hexlify(os.urandom(10)).decode('utf-8')
SCITRAN_PERSISTENT_DATA_PATH = os.environ.get('SCITRAN_PERSISTENT_DATA_PATH')

def create_user(db, _id, api_key, **kwargs):
    payload = {
        '_id': _id,
        'email': _id,
        'created': datetime.datetime.utcnow(),
        'modified': datetime.datetime.utcnow(),
        'firstname': 'test',
        'lastname': 'user'
    }
    payload.update(kwargs)

    # Create user
    print('Create user...')
    db.users.replace_one({'_id': _id}, payload, upsert=True)

    # Insert API Key
    print('Create API Key...')
    db.apikeys.replace_one({'_id': api_key}, {
        '_id': api_key,
        'created': datetime.datetime.utcnow(),
        'last_seen': None,
        'type': 'user',
        'origin': {'type': 'user', 'id': _id}
    }, upsert=True)

def create_site(db, path, **kwargs):

    """Create Default Site Settings which include a default storage provider"""

    if not db.get_collection('providers'):
        db.create_collection('providers')

    provider = db.providers.find_one({'label':'Local Storage'})

    if not provider:
        storage_provider = db.providers.insert_one({
            "_id": bson.ObjectId("deadbeefdeadbeefdeadbeef"),
            "origin": {"type":"system", "id":"system"},
            "created":"2019-03-19T18:48:37.790Z",
            "config":{"path": path},
            "modified":"2019-03-19T18:48:37.790Z",
            "label":"Local Storage",
            "provider_class":"storage",
            "provider_type":"osfs"
        })
        storage_provider_id = storage_provider.inserted_id
    else:
        storage_provider_id = provider['_id']

    provider = db.providers.find_one({'label': 'Default Compute Provider'})
    if not provider:
        compute_provider = db.providers.insert_one({
            "origin": {"type":"system", "id":"system"},
            "created": "2019-03-19T18:48:37.790Z",
            "config": {"path":path},
            "modified": "2019-03-19T18:48:37.790Z",
            "label": "Default Compute Provider",
            "provider_class": "compute",
            "provider_type": "static"
        })
        compute_provider_id = compute_provider.inserted_id
    else:
        compute_provider_id = provider['_id']

    db.singletons.update({'_id':'site'},
        {
            "_id": "site",
            "center_gears": [],
            "created": "2019-03-19T18:44:17.701078+00:00",
            "modified": "2019-03-19T18:44:17.701094+00:00",
            "providers": {
                "storage": storage_provider_id,
                'compute': compute_provider_id}
        },
        True)


def init_db():
    # Import on demand
    import pymongo
    import requests

    if not SCITRAN_PERSISTENT_DB_URI:
        raise Exception('Cannot initialize database without SCITRAN_PERSISTENT_DB_URI!')
    if not SCITRAN_PERSISTENT_DATA_PATH:
        raise Exception('Cannot initialize tests without SCITRAN_PERSISTENT_DATA_PATH!')

    db = pymongo.MongoClient(SCITRAN_PERSISTENT_DB_URI).get_default_database()
    create_user(db, 'admin@user.com', SCITRAN_ADMIN_API_KEY, root=True)
    create_site(db, SCITRAN_PERSISTENT_DATA_PATH)

