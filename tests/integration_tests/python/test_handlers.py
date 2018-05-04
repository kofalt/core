import os

from api.config import release_version_file_path


def test_roothandler(as_public):
    r = as_public.get('')
    assert r.ok
    assert '<title>SciTran API</title>' in r.text


def test_schemahandler(as_public):
    r = as_public.get('/schemas/non/existent.json')
    assert r.status_code == 404

    r = as_public.get('/schemas/definitions/user.json')
    assert r.ok
    schema = r.json()
    assert all(attr in schema['definitions'] for attr in ('email', 'firstname', 'lastname'))


def test_config_version(as_user, api_db):
    # get database version when no version document exists, It hasn;t been set yet in the tests
    r = as_user.get('/version')
    assert r.status_code == 404
    api_db.singletons.insert_one({"_id":"version","database":3})

    # Start with non-existent file
    try:
        os.remove(release_version_file_path)
    except:
        pass

    # get database schema version
    r = as_user.get('/version')
    assert r.ok
    assert r.json()['database'] == 3
    assert r.json()['release'] == ''

    # Check api version when api_version.txt does not exist
    with open(release_version_file_path, 'w') as f:
        f.write('2.1.0')

    r = as_user.get('/version')
    assert r.ok
    assert r.json()['database'] == 3
    assert r.json()['release'] == '2.1.0'

    api_db.singletons.find_one_and_delete({'_id':'version'})
    os.remove(release_version_file_path)
