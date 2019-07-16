import binascii
import os
import datetime
import bson

SCITRAN_PERSISTENT_DB_URI = os.environ.get('SCITRAN_PERSISTENT_DB_URI')
SCITRAN_ADMIN_API_KEY = binascii.hexlify(os.urandom(10)).decode('utf-8')
SCITRAN_DEVICE_API_KEY = binascii.hexlify(os.urandom(10)).decode('utf-8')
SCITRAN_PERSISTENT_DATA_PATH = os.environ.get('SCITRAN_PERSISTENT_DATA_PATH')

def create_user(db, _id, api_key, **kwargs):
    payload = {
        '_id': _id,
        'email': _id,
        'created': datetime.datetime.utcnow(),
        'modified': datetime.datetime.utcnow(),
        'firstname': 'test',
        'lastname': 'user',
        'last_seen': datetime.datetime.utcnow(),
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
        'last_used': datetime.datetime.utcnow(),
        'type': 'user',
        'origin': {'type': 'user', 'id': _id}
    }, upsert=True)

def create_device_key(db, api_key, **kwargs):
    # Insert API Key
    print('Create Device API Key...')
    db.apikeys.replace_one({'_id': api_key}, {
        '_id': api_key,
        'created': datetime.datetime.utcnow(),
        'last_used': datetime.datetime.utcnow(),
        'type': 'device',
        'origin': {'type': 'device', 'id': 'test-device'}
    }, upsert=True)

def create_site(db, path, **kwargs):

    """Create Default Site Settings which include a default storage provider"""

    if not db.get_collection('providers'):
        db.create_collection('providers')

    provider = db.providers.find_one({'label':'Primary Storage'})

    if not provider:
        storage_provider = db.providers.insert_one({
            "_id": bson.ObjectId("deadbeefdeadbeefdeadbeef"),
            "origin": {"type":"system", "id":"system"},
            "created": datetime.datetime.utcnow(),
            "config":{"path": path},
            "modified": datetime.datetime.utcnow(),
            "label":"Primary Storage",
            "provider_class":"storage",
            "provider_type":"local"
        })
        storage_provider_id = storage_provider.inserted_id
    else:
        storage_provider_id = provider['_id']

    provider = db.providers.find_one({'label': 'Default Compute Provider'})
    if not provider:
        compute_provider = db.providers.insert_one({
            "origin": {"type":"system", "id":"system"},
            "created": datetime.datetime.utcnow(),
            "config": {"path":path},
            "modified": datetime.datetime.utcnow(),
            "label": "Default Compute Provider",
            "provider_class": "compute",
            "provider_type": "static"
        })
        compute_provider_id = compute_provider.inserted_id
    else:
        compute_provider_id = provider['_id']

    db.singletons.update({'_id':'site'},
        {
            "$addToSet": {"center_gears": "site-gear"},
            "$set": {
                "providers": {
                    "storage": storage_provider_id,
                    "compute": compute_provider_id
                },
                "modified": datetime.datetime.now()
            },
            "$setOnInsert": {
                'created': datetime.datetime.now()
            }
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
    create_user(db, 'admin@user.com', SCITRAN_ADMIN_API_KEY, roles=['site_admin'])
    create_site(db, SCITRAN_PERSISTENT_DATA_PATH)
    create_device_key(db, SCITRAN_DEVICE_API_KEY)
