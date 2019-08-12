"""
Gears
"""

from __future__ import absolute_import

import bson.objectid
import copy
import datetime
from dxf import DXF
from jsonschema import Draft4Validator, ValidationError
import gears as gear_tools
import json
from urlparse import urlparse

from .. import config
from ..dao import dbutil

from ..web.errors import APIValidationException, APINotFoundException

log = config.log

def get_gears(all_versions=False, pagination=None, include_invalid=False):
    """
    Fetch the install-global gears from the database
    """
    match = {}
    if not include_invalid:
        match['gear.custom.flywheel.invalid'] = {'$ne': True}

    if all_versions:
        kwargs = {
            # Invalid disables a gear from running entirely.
            # https://github.com/flywheel-io/gears/tree/master/spec#reserved-custom-keys
            'filter': match,

            'sort': [('gear.name', 1), ('created', -1)]
        }
        page = dbutil.paginate_find(config.db.gears, kwargs, pagination)
        return page['results'] if pagination is None else page

    if pagination:
        pagination['pipe_key'] = lambda key: 'original.' + key

    pipe = [
        {'$match': match},
        {'$sort': {
            'gear.name': 1,
            'created': -1,
        }},
        {'$group': {
            '_id': { 'name': '$gear.name' },
            'original': { '$first': '$$CURRENT' }
        }}
    ]

    page = dbutil.paginate_pipe(config.db.gears, pipe, pagination)
    page['results'] = [r['original'] for r in page['results']]
    return page['results'] if pagination is None else page

def get_gear(_id):
    gear = config.db.gears.find_one({'_id': bson.ObjectId(_id)})
    if gear is None:
        raise APINotFoundException('Cannot find gear {}'.format(_id))
    return gear

def get_latest_gear(name):
    gears = config.db.gears.find({'gear.name': name, 'gear.custom.flywheel.invalid': {'$ne': True}}).sort('created', direction=-1).limit(1)
    if gears.count() > 0:
        return gears[0]

def get_gear_version(name, version):
    gear = config.db.gears.find_one({'gear.name': name, 'gear.version': version})
    if gear is None:
        raise APINotFoundException('Cannot find version {} for gear {}'.format(version, name))
    return gear

def get_all_gear_versions(name):
    return list(config.db.gears.find({'gear.name': name}).sort('created', direction=-1))

def requires_read_write_key(gear):
    for x in gear['gear'].get('inputs', {}).keys():
        input_ = gear['gear']['inputs'][x]
        if input_.get('base') == 'api-key' and not input_.get('read-only'):
            return True
    return False

def get_invocation_schema(gear):
    return gear_tools.derive_invocation_schema(gear['gear'])

def add_suggest_info_to_files(gear, files):
    """
    Given a list of files, add information to each file that details those that would work well for each input on a gear.
    """

    invocation_schema = get_invocation_schema(gear)

    schemas = {}
    for x in gear['gear']['inputs']:
        input_ = gear['gear']['inputs'][x]
        if input_.get('base') == 'file':
            schema = gear_tools.isolate_file_invocation(invocation_schema, x)
            schemas[x] = Draft4Validator(schema)

    for f in files:
        f['suggested'] = {}
        for x in schemas:
            f['suggested'][x] = schemas[x].is_valid(f)

    return files

def suggest_for_files(gear, files, context=None):

    invocation_schema = get_invocation_schema(gear)
    schemas = {}
    suggested_inputs = {}

    for x in gear['gear']['inputs']:
        input_ = gear['gear']['inputs'][x]
        if input_.get('base') == 'context':
            if x in context:
                suggested_inputs[x] = [{
                    'base': 'context',
                    'found': True,
                    'value': context[x]['value']
                }]
            else:
                suggested_inputs[x] = [{
                    'base': 'context',
                    'found': False
                }]
        elif input_.get('base') == 'file':
            schema = gear_tools.isolate_file_invocation(invocation_schema, x)
            schemas[x] = Draft4Validator(schema)

    for input_name, schema in schemas.iteritems():
        suggested_inputs[input_name] = []
        for f in files:
            if schema.is_valid(f):
                suggested_inputs[input_name].append({
                    'base': 'file',
                    'name': f.get('name')
                })

    return suggested_inputs

def validate_gear_config(gear, config_):
    if len(gear.get('gear', {}).get('config', {})) > 0:
        invocation = gear_tools.derive_invocation_schema(gear['gear'])
        ci = gear_tools.isolate_config_invocation(invocation)
        validator = Draft4Validator(ci)

        try:
            validator.validate(fill_gear_default_values(gear, config_))
        except ValidationError as err:
            raise APIValidationException(reason='config did not match manifest', cause=err)
    return True

def fill_gear_default_values(gear, config_):
    """
    Given a gear and a config map, fill any missing keys using defaults from the gear's config
    """

    config_ = copy.deepcopy(config_) or {}

    for k,v in gear['gear'].get('config', {}).iteritems():
        if 'default' in v:
            config_.setdefault(k, v['default'])

    return config_

def count_file_inputs(geardoc):
    return len([inp for inp in geardoc['gear']['inputs'].values() if inp['base'] == 'file'])

def filter_optional_inputs(geardoc):
    filtered_gear_doc = copy.deepcopy(geardoc)
    inputs = filtered_gear_doc['gear']['inputs'].iteritems()
    filtered_gear_doc['gear']['inputs'] = {inp: inp_val for inp, inp_val in inputs if not inp_val.get('optional')}
    return filtered_gear_doc

def insert_gear(doc):
    gear_tools.validate_manifest(doc['gear'])
    installed_gears = get_all_gear_versions(doc['gear']['name'])

    # This can be mongo-escaped and re-used later
    if doc.get("invocation-schema"):
        del(doc["invocation-schema"])

    now = datetime.datetime.utcnow()

    doc['created']  = now
    doc['modified'] = now

    result = config.db.gears.insert(doc)

    if installed_gears:
        installed_gear_ids = [str(gear['_id']) for gear in installed_gears]
        auto_update_rules(doc['_id'], installed_gear_ids)

    return result

def remove_gear(_id):
    result = config.db.gears.delete_one({"_id": bson.ObjectId(_id)})

    if result.deleted_count != 1:
        raise Exception("Deleted failed " + str(result.raw_result))

def upsert_gear(doc):
    check_for_gear_insertion(doc)

    return insert_gear(doc)

def check_for_gear_insertion(doc):
    gear_tools.validate_manifest(doc['gear'])

    # Remove previous gear if name & version combo already exists

    conflict = config.db.gears.find_one({
        'gear.name': doc['gear']['name'],
        'gear.version': doc['gear']['version']
    })

    if conflict is not None:
        raise Exception('Gear "' + doc['gear']['name'] + '" version "' + doc['gear']['version'] + '" already exists, consider changing the version string.')

def auto_update_rules(gear_id, installed_gear_ids):
    config.db.project_rules.update_many({'gear_id': {'$in': installed_gear_ids}, 'auto_update': True}, {"$set": {'gear_id': str(gear_id)}})

def get_registry_connectivity():
    """
    Format config values for registry authentication.
    """

    c = config.get_config()
    pw = c['core']['drone_secret']
    url =  urlparse(c['site']['redirect_url'])

    if url.port is None or url.port == 443:
        host = url.hostname
    else:
        host = url.hostname + ':' + str(url.port)

    api_key = ''
    username = 'device.flywheel'

    if url.port is None or url.port == 443:
        api_key = url.hostname + ':' + pw
    else:
        api_key = url.hostname + ':' + str(url.port) + ':' + pw

    return host, username, api_key

def confirm_registry_asset(repo, pointer):
    """
    Validates a registry asset by querying the remote registry.

    Returns the registry manifest at the given pointer, and a pullable image string.
    """

    host, username, api_key = get_registry_connectivity()

    image = host + '/' + repo + '@' + pointer
    log.debug('Validating image ' + image + '...')

    # Authenticate via callable
    def auth(dxf, response):
        log.debug('Authenticating to registry...')
        dxf.authenticate(username, api_key, response=response)
        log.debug('Auth           to registry successful')

    # Connects over internal network with override host and autogenerated TLS
    dxf = DXF(host, repo, auth, tlsverify=False)

    # Fetch and sanity check the blob size
    blob_id = str(dxf.get_digest(pointer))
    if dxf.blob_size(blob_id) > (10 * 1000* 1000): # 10 MB to bytes
        raise Exception('Manifest is larger than 10 MB. Possible registry error?')

    # Pull and assemble the manifest
    raw_blob, _ = dxf.pull_blob(blob_id, size=True)
    manifest = json.loads(''.join(raw_blob))

    # Compatibility checks for the gears platform
    if manifest['architecture'] != 'amd64':
        raise Exception("Architecture must be amd64")

    if manifest['os'] != 'linux':
        raise Exception("Os must be linux")

    return manifest, image
