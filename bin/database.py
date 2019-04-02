#!/usr/bin/env python

import argparse
import bson
import collections
import copy
import datetime
import dateutil.parser
import json
import logging
import multiprocessing
import os
import re
import sys
import time

from cachetools import cached, LRUCache

from api import config
from api import util
from api.dao import containerutil
from api.dao.containerstorage import ProjectStorage
from api.jobs.jobs import Job
from api.jobs import gears
from api.types import Origin
from api.jobs import batch

from fixes import get_available_fixes, has_unappliable_fixes, apply_available_fixes
from process_cursor import process_cursor

CURRENT_DATABASE_VERSION = 64 # An int that is bumped when a new schema change is made


def get_db_version():
    """Get the current db version, with applied fixes.

    Returns:
        (int, dict): The current database version, and a map of applied fixes
    """
    version = config.get_version()
    if version is None:
        # Attempt to find db version at old location
        version = config.db.version.find_one({'_id': 'version'})
    if version is None or version.get('database') is None:
        return 0, {}
    return version.get('database'), version.get('applied_fixes', {})


def confirm_schema_match():
    """
    Checks version of database schema

    Returns (0)  if DB schema version matches requirements.
    Returns (42) if DB schema version does not match
                 requirements and can be upgraded.
    Returns (43) if DB schema version does not match
                 requirements and cannot be upgraded,
                 perhaps because code is at lower version
                 than the DB schema version.
    """

    db_version, applied_fixes = get_db_version()
    if not isinstance(db_version, int) or db_version > CURRENT_DATABASE_VERSION:
        logging.error('The stored db schema version of %s is incompatible with required version %s',
                       str(db_version), CURRENT_DATABASE_VERSION)
        sys.exit(43)
    elif has_unappliable_fixes(db_version, applied_fixes):
        sys.exit(43)
    elif db_version < CURRENT_DATABASE_VERSION:
        sys.exit(42)
    elif get_available_fixes(db_version, applied_fixes):
        sys.exit(42)
    else:
        sys.exit(0)


def get_bson_timestamp(bson_id):
    return bson_id.generation_time.replace(tzinfo=None)


def drop_index(coll, key):
    """
    Drop the given index, if it exists
    """
    if isinstance(key, str):
        key = [(key, 1)]
    if isinstance(key, tuple):
        key = [key]

    for name, index in config.db[coll].index_information().items():
        if index['key'] == key:
            config.log.info('Dropping %s index named %s, for key %s', coll, name, key)
            config.db[coll].drop_index(key)


def ensure_container_parents(cont, cont_name, parents=None):
    """
    Fix the parents for a container and it's children
    """
    child_cont_name = containerutil.CHILD_FROM_PARENT.get(cont_name)
    if parents is None:
        if cont_name == 'analyses':
            parent_id = cont['parent']['id']
            parent_cont_name = containerutil.pluralize(cont['parent']['type'])
            parent = config.db[parent_cont_name].find_one({'_id': parent_id})
        else:
            parent_cont_name = containerutil.PARENT_FROM_CHILD[cont_name]
            parent_id = cont[containerutil.singularize(parent_cont_name)]
            parent = config.db[parent_cont_name].find_one({'_id': parent_id})

        if parent:
            parents = parent.get('parents', {})
            parents[containerutil.singularize(parent_cont_name)] = parent_id
        else:
            logging.critical('Parent for  {} {} does not exist'.format(cont_name, cont['_id']))
            parents = {}

        config.db[cont_name].update({'_id': cont['_id']}, {'$set': {'parents': parents}})

    parents[cont_name] = cont['_id']
    config.db.analyses.update_many({'parent.id': cont['_id']}, {'$set': {'parents': parents}})
    if child_cont_name is None:
        return True
    config.db[child_cont_name].update_many({cont_name: cont['_id']}, {'$set': {'parents': parents}})
    cursor = config.db[child_cont_name].find({cont_name: cont['_id']})
    process_cursor(cursor, ensure_container_parents, child_cont_name, parents=parents)
    return True

def ensure_parents():
    """
    Ensure that parents exist for all containers

    IMPORTANT NOTE: This doesn't make sure containers that have a parents key are
    accurate or that the individual parent id's are set
    """
    for cont_name in ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses']:
        cursor = config.db[cont_name].find({'parents': None})
        process_cursor(cursor, ensure_container_parents, cont_name)


def upgrade_to_1():
    """
    scitran/core issue #206

    Initialize db version to 1
    """
    config.db.singletons.insert_one({'_id': 'version', 'database': 1})

def upgrade_to_2():
    """
    scitran/core PR #236

    Set file.origin.name to id if does not exist
    Set file.origin.method to '' if does not exist
    """

    def update_file_origins(cont_list, cont_name):
        for container in cont_list:
            updated_files = []
            for file in container.get('files', []):
                origin = file.get('origin')
                if origin is not None:
                    if origin.get('name', None) is None:
                        file['origin']['name'] = origin['id']
                    if origin.get('method', None) is None:
                        file['origin']['method'] = ''
                updated_files.append(file)

            query = {'_id': container['_id']}
            update = {'$set': {'files': updated_files}}
            result = config.db[cont_name].update_one(query, update)

    query = {'$and':[{'files.origin.name': { '$exists': False}}, {'files.origin.id': { '$exists': True}}]}

    update_file_origins(config.db.collections.find(query), 'collections')
    update_file_origins(config.db.projects.find(query), 'projects')
    update_file_origins(config.db.sessions.find(query), 'sessions')
    update_file_origins(config.db.acquisitions.find(query), 'acquisitions')

def upgrade_to_3():
    """
    scitran/core issue #253

    Set first user with admin permissions found as curator if one does not exist
    """
    query = {'curator': {'$exists': False}, 'permissions.access': 'admin'}
    projection = {'permissions.$':1}
    collections = config.db.collections.find(query, projection)
    for coll in collections:
        admin = coll['permissions'][0]['_id']
        query = {'_id': coll['_id']}
        update = {'$set': {'curator': admin}}
        config.db.collections.update_one(query, update)

def upgrade_to_4():
    """
    scitran/core issue #263

    Add '_id' field to session.subject
    Give subjects with the same code and project the same _id
    """

    pipeline = [
        {'$match': { 'subject._id': {'$exists': False}}},
        {'$group' : { '_id' : {'pid': '$project', 'code': '$subject.code'}, 'sids': {'$push': '$_id' }}}
    ]

    subjects = config.db.sessions.aggregate(pipeline)
    for subject in subjects:

        # Subjects without a code and sessions without a subject
        # will be returned grouped together, but all need unique IDs
        if subject['_id'].get('code') is None:
            for session_id in subject['sids']:
                subject_id = bson.ObjectId()
                config.db.sessions.update_one({'_id': session_id},{'$set': {'subject._id': subject_id}})
        else:
            subject_id = bson.ObjectId()
            query = {'_id': {'$in': subject['sids']}}
            update = {'$set': {'subject._id': subject_id}}
            config.db.sessions.update_many(query, update)

def upgrade_to_5():
    """
    scitran/core issue #279

    Ensure all sessions and acquisitions have the same perms as their project
    Bug(#278) discovered where changing a session's project did not update acquisition perms
    """

    projects = config.db.projects.find({})
    for p in projects:
        perms = p.get('permissions', [])

        session_ids = [s['_id'] for s in config.db.sessions.find({'project': p['_id']}, [])]

        config.db.sessions.update_many({'project': p['_id']}, {'$set': {'permissions': perms}})
        config.db.acquisitions.update_many({'session': {'$in': session_ids}}, {'$set': {'permissions': perms}})

def upgrade_to_6():
    """
    scitran/core issue #277

    Ensure all collection modified dates are ISO format
    Bug fixed in 6967f23
    """

    colls = config.db.collections.find({'modified': {'$type': 2}}) # type string
    for c in colls:
        fixed_mod = dateutil.parser.parse(c['modified'])
        config.db.collections.update_one({'_id': c['_id']}, {'$set': {'modified': fixed_mod}})

def upgrade_to_7():
    """
    scitran/core issue #270

    Add named inputs and specified destinations to jobs.

    Before:
    {
        "input" : {
            "container_type" : "acquisition",
            "container_id" : "572baf4e23dcb77ebbe06b3f",
            "filename" : "1_1_dicom.zip",
            "filehash" : "v0-sha384-422bd115d21585d1811d42cd99f1cf0a8511a4b377dd2deeaa1ab491d70932a051926ed99815a75142ad0815088ed009"
        }
    }

    After:
    {
        "inputs" : {
            "dicom" : {
                "container_type" : "acquisition",
                "container_id" : "572baf4e23dcb77ebbe06b3f",
                "filename" : "1_1_dicom.zip"
            }
        },
        "destination" : {
            "container_type" : "acquisition",
            "container_id" : "572baf4e23dcb77ebbe06b3f"
        }
    }
    """

    # The infrastructure runs this upgrade script before populating manifests.
    # For this reason, this one-time script does NOT pull manifests to do the input-name mapping, instead relying on a hard-coded alg name -> input name map.
    # If you have other gears in your system at the time of upgrade, you must add that mapping here.
    input_name_for_gear = {
        'dcm_convert': 'dicom',
        'qa-report-fmri': 'nifti',
        'dicom_mr_classifier': 'dicom',
    }

    jobs = config.db.jobs.find({'input': {'$exists': True}})

    for job in jobs:
        gear_name = job['algorithm_id']
        input_name = input_name_for_gear[gear_name]

        # Move single input to named input map
        input_ = job['input']
        input_.pop('filehash', None)
        inputs = { input_name: input_ }

        # Destination is required, and (for these jobs) is always the same container as the input
        destination = copy.deepcopy(input_)
        destination.pop('filename', None)

        config.db.jobs.update_one(
            {'_id': job['_id']},
            {
                '$set': {
                    'inputs': inputs,
                    'destination': destination
                },
                '$unset': {
                    'input': ''
                }
            }
        )

def upgrade_to_8():
    """
    scitran/core issue #291

    Migrate config, version, gears and rules to singletons collection
    """

    colls = config.db.collection_names()
    to_be_removed = ['version', 'config', 'static']
    # If we are in a bad state (singletons exists but so do any of the colls in to be removed)
    # remove singletons to try again
    if 'singletons' in colls and set(to_be_removed).intersection(set(colls)):
        config.db.drop_collection('singletons')

    if 'singletons' not in config.db.collection_names():
        static = config.db.static.find({})
        if static.count() > 0:
            config.db.singletons.insert_many(static)
        config.db.singletons.insert(config.db.version.find({}))

        configs = config.db.config.find({'latest': True},{'latest':0})
        if configs.count() == 1:
            c = configs[0]
            c['_id'] = 'config'
            config.db.singletons.insert_one(c)

        for c in to_be_removed:
            if c in config.db.collection_names():
                config.db.drop_collection(c)

def upgrade_to_9():
    """
    scitran/core issue #292

    Remove all session and acquisition timestamps that are empty strings
    """

    config.db.acquisitions.update_many({'timestamp':''}, {'$unset': {'timestamp': ''}})
    config.db.sessions.update_many({'timestamp':''}, {'$unset': {'timestamp': ''}})

def upgrade_to_10():
    """
    scitran/core issue #301

    Makes the following key renames, all in the jobs table.
    FR is a FileReference, CR is a ContainerReference:

    job.algorithm_id  --> job.name

    FR.container_type --> type
    FR.container_id   --> id
    FR.filename       --> name

    CR.container_type --> type
    CR.container_id   --> id
    """

    def switch_keys(doc, x, y):
        doc[y] = doc[x]
        doc.pop(x, None)


    jobs = config.db.jobs.find({'destination.container_type': {'$exists': True}})

    for job in jobs:
        switch_keys(job, 'algorithm_id', 'name')

        for key in job['inputs'].keys():
            inp = job['inputs'][key]

            switch_keys(inp, 'container_type', 'type')
            switch_keys(inp, 'container_id',   'id')
            switch_keys(inp, 'filename',       'name')


        dest = job['destination']
        switch_keys(dest, 'container_type', 'type')
        switch_keys(dest, 'container_id',   'id')

        config.db.jobs.update(
            {'_id': job['_id']},
            job
        )

def upgrade_to_11():
    """
    scitran/core issue #362

    Restructures job objects' `inputs` field from a dict with arbitrary keys
    into a list where the key becomes the field `input`
    """

    jobs = config.db.jobs.find({'inputs.type': {'$exists': False}})

    for job in jobs:

        inputs_arr = []
        for key, inp in job['inputs'].iteritems():
            inp['input'] = key
            inputs_arr.append(inp)

        config.db.jobs.update(
            {'_id': job['_id']},
            {'$set': {'inputs': inputs_arr}}
        )

def upgrade_to_12():
    """
    scitran/core PR #372

    Store job inputs on job-based analyses
    """

    sessions = config.db.sessions.find({'analyses.job': {'$exists': True}})

    for session in sessions:
        for analysis in session.get('analyses'):
            if analysis.get('job'):
                job = Job.get(analysis['job'])
                files = analysis.get('files', [])
                files[:] = [x for x in files if x.get('output')] # remove any existing inputs and insert fresh

                for i in getattr(job, 'inputs', {}):
                    fileref = job.inputs[i]
                    contref = containerutil.create_containerreference_from_filereference(job.inputs[i])
                    file_ = contref.find_file(fileref.name)
                    if file_:
                        file_['input'] = True
                        files.append(file_)

                q = {'analyses._id': analysis['_id']}
                u = {'$set': {'analyses.$.job': job.id_, 'analyses.$.files': files}}
                config.db.sessions.update_one(q, u)

def upgrade_to_13():
    """
    scitran/core PR #403

    Clear schema path from db config in order to set abs path to files
    """
    config.db.singletons.find_one_and_update(
        {'_id': 'config', 'persistent.schema_path': {'$exists': True}},
        {'$unset': {'persistent.schema_path': ''}})

def upgrade_to_14():
    """schema_path is no longer user configurable"""
    config.db.singletons.find_one_and_update(
        {'_id': 'config', 'persistent.schema_path': {'$exists': True}},
        {'$unset': {'persistent.schema_path': ''}})

def upgrade_to_15():
    """
    scitran/pull issue #417

    First remove all timestamps that are empty or not mongo date or string format.
    Then attempt to convert strings to dates, removing those that cannot be converted.
    Mongo $type maps: String = 2, Date = 9
    """
    query = {}
    query['$or'] = [
                    {'timestamp':''},
                    {'$and': [
                        {'timestamp': {'$exists': True}},
                        {'timestamp': {'$not': {'$type':2}}},
                        {'timestamp': {'$not': {'$type':9}}}
                    ]}
                ]
    unset = {'$unset': {'timestamp': ''}}

    config.db.sessions.update_many(query, unset)
    config.db.acquisitions.update_many(query, unset)

    query =  {'$and': [
                {'timestamp': {'$exists': True}},
                {'timestamp': {'$type':2}}
            ]}
    sessions = config.db.sessions.find(query)
    for s in sessions:
        try:
            fixed_timestamp = dateutil.parser.parse(s['timestamp'])
        except:
            config.db.sessions.update_one({'_id': s['_id']}, {'$unset': {'timestamp': ''}})
            continue
        config.db.sessions.update_one({'_id': s['_id']}, {'$set': {'timestamp': fixed_timestamp}})

    acquisitions = config.db.acquisitions.find(query)
    for a in acquisitions:
        try:
            fixed_timestamp = dateutil.parser.parse(a['timestamp'])
        except:
            config.db.sessions.update_one({'_id': a['_id']}, {'$unset': {'timestamp': ''}})
            continue
        config.db.sessions.update_one({'_id': a['_id']}, {'$set': {'timestamp': fixed_timestamp}})

def upgrade_to_16():
    """
    Fixes file.size sometimes being a floating-point rather than integer.
    """

    acquisitions = config.db.acquisitions.find({'files.size': {'$type': 'double'}})
    for x in acquisitions:
        for y in x.get('files', []):
            if y.get('size'):
                y['size'] = int(y['size'])
        config.db.acquisitions.update({"_id": x['_id']}, x)

    sessions = config.db.sessions.find({'files.size': {'$type': 'double'}})
    for x in sessions:
        for y in x.get('files', []):
            if y.get('size'):
                y['size'] = int(y['size'])
        config.db.sessions.update({"_id": x['_id']}, x)

    projects = config.db.projects.find({'files.size': {'$type': 'double'}})
    for x in projects:
        for y in x.get('files', []):
            if y.get('size'):
                y['size'] = int(y['size'])
        config.db.projects.update({"_id": x['_id']}, x)

    sessions = config.db.sessions.find({'analyses.files.size': {'$type': 'double'}})
    for x in sessions:
        for y in x.get('analyses', []):
            for z in y.get('files', []):
                if z.get('size'):
                    z['size'] = int(z['size'])
        config.db.sessions.update({"_id": x['_id']}, x)

def upgrade_to_17():
    """
    scitran/core issue #557

    Reassign subject ids after bug fix in packfile code that did not properly match subjects
    """

    pipeline = [
        {'$group' : { '_id' : {'pid': '$project', 'code': '$subject.code'}, 'sids': {'$push': '$_id' }}}
    ]

    subjects = config.db.sessions.aggregate(pipeline)
    for subject in subjects:

        # Subjects without a code and sessions without a subject
        # will be returned grouped together, but all need unique IDs
        if subject['_id'].get('code') is None:
            for session_id in subject['sids']:
                subject_id = bson.ObjectId()
                config.db.sessions.update_one({'_id': session_id},{'$set': {'subject._id': subject_id}})
        else:
            subject_id = bson.ObjectId()
            query = {'_id': {'$in': subject['sids']}}
            update = {'$set': {'subject._id': subject_id}}
            config.db.sessions.update_many(query, update)

def upgrade_to_18():
    """
    scitran/core issue #334

    Move singleton gear doc to its own table
    """

    gear_doc = config.db.singletons.find_one({"_id": "gears"})

    if gear_doc is not None:
        gear_list = gear_doc.get('gear_list', [])
        for gear in gear_list:
            try:
                gears.upsert_gear(gear)
            except Exception as e:
                logging.error("")
                logging.error("Error upgrading gear:")
                logging.error(type(e))
                logging.error("Gear will not be retained. Document follows:")
                logging.error(gear)
                logging.error("")

        config.db.singletons.remove({"_id": "gears"})

def upgrade_to_19():
    """
    scitran/core issue #552

    Add origin information to job object
    """

    update = {
        '$set': {
            'origin' : {'type': str(Origin.unknown), 'id': None}
        }
    }
    config.db.jobs.update_many({'origin': {'$exists': False}}, update)

def upgrade_to_20():
    """
    scitran/core issue #602

    Change dash to underscore for consistency
    """

    query = {'last-seen': {'$exists': True}}
    update = {'$rename': {'last-seen':'last_seen' }}

    config.db.devices.update_many(query, update)

def upgrade_to_21():
    """
    scitran/core issue #189 - Data Model v2

    Field `metadata` renamed to `info`
    Field `file.instrument` renamed to `file.modality`
    Acquisition fields `instrument` and `measurement` removed
    """

    def update_project_template(template):
        new_template = {'acquisitions': []}
        for a in template.get('acquisitions', []):
            new_a = {'minimum': a['minimum']}
            properties = a['schema']['properties']
            if 'measurement' in properties:
                m_req = properties['measurement']['pattern']
                m_req = re.sub('^\(\?i\)', '', m_req)
                new_a['files']=[{'measurement':  m_req, 'minimum': 1}]
            if 'label' in properties:
                l_req = properties['label']['pattern']
                l_req = re.sub('^\(\?i\)', '', l_req)
                new_a['label'] = l_req
            new_template['acquisitions'].append(new_a)

        return new_template

    def dm_v2_updates(cont_list, cont_name):
        for container in cont_list:

            query = {'_id': container['_id']}
            update = {'$rename': {'metadata': 'info'}}

            if cont_name == 'projects' and container.get('template'):
                new_template = update_project_template(json.loads(container.get('template')))
                update['$set'] = {'template': new_template}


            if cont_name == 'sessions':
                update['$rename'].update({'subject.metadata': 'subject.info'})


            measurement = None
            modality = None
            info = None
            if cont_name == 'acquisitions':
                update['$unset'] = {'instrument': '', 'measurement': ''}
                measurement = container.get('measurement', None)
                modality = container.get('instrument', None)
                info = container.get('metadata', None)
                if info:
                    config.db.acquisitions.update_one(query, {'$set': {'metadata': {}}})


            # From mongo docs: '$rename does not work if these fields are in array elements.'
            files = container.get('files')
            if files is not None:
                updated_files = []
                for file_ in files:
                    file_['info'] = {}
                    if 'metadata' in file_:
                        file_['info'] = file_.pop('metadata', None)
                    if 'instrument' in file_:
                        file_['modality'] = file_.pop('instrument', None)
                    if measurement:
                        # Move the acquisition's measurement to all files
                        if file_.get('measurements'):
                            file_['measurements'].append(measurement)
                        else:
                            file_['measurements'] = [measurement]
                    if info and file_.get('type', '') == 'dicom':
                        # This is going to be the dicom header info
                        updated_info = info
                        updated_info.update(file_['info'])
                        file_['info'] = updated_info
                    if modality and not file_.get('modality'):
                        file_['modality'] = modality

                    updated_files.append(file_)
                if update.get('$set'):
                    update['$set']['files'] =  updated_files
                else:
                    update['$set'] = {'files': updated_files}

            result = config.db[cont_name].update_one(query, update)

    query = {'$or':[{'files.metadata': { '$exists': True}},
                    {'metadata': { '$exists': True}},
                    {'files.instrument': { '$exists': True}}]}

    dm_v2_updates(config.db.collections.find(query), 'collections')

    query['$or'].append({'template': { '$exists': True}})
    dm_v2_updates(config.db.projects.find({}), 'projects')

    query['$or'].append({'subject': { '$exists': True}})
    dm_v2_updates(config.db.sessions.find(query), 'sessions')

    query['$or'].append({'instrument': { '$exists': True}})
    query['$or'].append({'measurement': { '$exists': True}})
    dm_v2_updates(config.db.acquisitions.find(query), 'acquisitions')

def upgrade_to_22():
    """
    Add created and modified timestamps to gear docs

    Of debatable value, since infra will load gears on each boot.
    """

    logging.info('Upgrade v22, phase 1 of 3, upgrading gears...')

    # Add timestamps to gears.
    for gear in config.db.gears.find({}):
        now = datetime.datetime.utcnow()

        gear['created']  = now
        gear['modified'] = now

        config.db.gears.update({'_id': gear['_id']}, gear)

        # Ensure there cannot possibly be two gears of the same name with the same timestamp.
        # Plus or minus monotonic time.
        # A very silly solution, but we only ever need to do this once, on a double-digit number of documents.
        # Not worth the effort to, eg, rewind time and do math.
        time.sleep(1)
        logging.info('  Updated gear ' + str(gear['_id']) + ' ...')
        sys.stdout.flush()


    logging.info('Upgrade v22, phase 2 of 3, upgrading jobs...')

    # Now that they're updated, fetch all gears and hold them in memory.
    # This prevents extra database queries during the job upgrade.

    all_gears = list(config.db.gears.find({}))
    gears_map = { }

    for gear in all_gears:
        gear_name = gear['gear']['name']

        gears_map[gear_name] = gear

    # A dummy gear for missing refs
    dummy_gear = {
        'category' : 'converter',
        'gear' : {
            'inputs' : {
                'do-not-use' : {
                    'base' : 'file'
                }
            },
            'maintainer' : 'Noone <nobody@example.example>',
            'description' : 'This gear or job was referenced before gear versioning. Version information is not available for this gear.',
            'license' : 'BSD-2-Clause',
            'author' : 'Noone',
            'url' : 'https://example.example',
            'label' : 'Deprecated Gear',
            'flywheel' : '0',
            'source' : 'https://example.example',
            'version' : '0.0.0',
            'custom' : {
                'flywheel': {
                    'invalid': True
                }
            },
            'config' : {},
            'name' : 'deprecated-gear'
        },
        'exchange' : {
            'git-commit' : '0000000000000000000000000000000000000000',
            'rootfs-hash' : 'sha384:000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
            'rootfs-url' : 'https://example.example/does-not-exist.tgz'
        }
    }

    maximum = config.db.jobs.count()
    upgraded = 0

    # Blanket-assume gears were the latest in the DB pre-gear versioning.
    for job in config.db.jobs.find({}):

        # Look up latest gear by name, lose job name key
        gear_name = job['name']
        gear = gears_map.get(gear_name)

        if gear is None:
            logging.info('Job doc ' + str(job['_id']) + ' could not find gear ' + gear_name + ', creating...')

            new_gear = copy.deepcopy(dummy_gear)
            new_gear['gear']['name'] = gear_name

            # Save new gear, store id in memory
            resp = config.db.gears.insert_one(new_gear)
            new_id = resp.inserted_id
            new_gear['_id'] = str(new_id)

            # Insert gear into memory map
            gears_map[gear_name] = new_gear

            logging.info('Created gear  ' + gear_name + ' with id ' + str(new_id) + '. Future jobs with this gear name with not alert.')

            gear = new_gear

        if gear is None:
            raise Exception("We don't understand python scopes ;( ;(")

        # Store gear ID
        job.pop('name', None)
        job['gear_id'] = str(gear['_id'])

        # Save
        config.db.jobs.update({'_id': job['_id']}, job)

        upgraded += 1
        if upgraded % 1000 == 0:
            logging.info('  Processed ' + str(upgraded) + ' jobs of ' + str(maximum) + '...')


    logging.info('Upgrade v22, phase 3 of 3, upgrading batch...')

    maximum = config.db.batch.count()
    upgraded = 0

    for batch in config.db.batch.find({}):

        # Look up latest gear by name, lose job name key
        gear = gears.get_gear_by_name(batch['gear'])
        batch.pop('gear', None)

        # Store gear ID
        batch['gear_id'] = str(gear['_id'])

        # Save
        config.db.batch.update({'_id': batch['_id']}, batch)

        upgraded += 1
        if upgraded % 1000 == 0:
            logging.info('  Processed ' + str(upgraded) + ' batch of ' + str(maximum) + '...')


    logging.info('Upgrade v22, complete.')

def upgrade_to_23():
    """
    scitran/core issue #650

    Support multiple auth providers
    Config 'auth' key becomes map where keys are auth_type
    """

    db_config = config.db.singletons.find_one({'_id': 'config'})
    if db_config:
        auth_config = db_config.get('auth', {})
        if auth_config.get('auth_type'):
            auth_type = auth_config.pop('auth_type')
            config.db.singletons.update_one({'_id': 'config'}, {'$set': {'auth': {auth_type: auth_config}}})

def upgrade_to_24():
    """
    scitran/core issue #720

    Migrate gear rules to the project level
    """

    global_rules = config.db.singletons.find_one({"_id" : "rules"})
    project_ids  = list(config.db.projects.find({},{"_id": "true"}))

    if global_rules is None:
        global_rules = {
            'rule_list': []
        }

    logging.info('Upgrade v23, migrating ' + str(len(global_rules['rule_list'])) + ' gear rules...')

    count = 0
    for old_rule in global_rules['rule_list']:

        logging.info(json.dumps(old_rule))

        gear_name = old_rule['alg']
        rule_name = 'Migrated rule ' + str(count)

        any_stanzas = []
        all_stanzas = []

        for old_any_stanza in old_rule.get('any', []):
            if len(old_any_stanza) != 2:
                raise Exception('Confusing any-rule stanza ' + str(count) + ': ' + json.dumps(old_any_stanza))

            any_stanzas.append({ 'type': old_any_stanza[0], 'value': old_any_stanza[1] })

        for old_all_stanza in old_rule.get('all', []):
            if len(old_all_stanza) != 2:
                raise Exception('Confusing all-rule stanza ' + str(count) + ': ' + json.dumps(old_all_stanza))

            all_stanzas.append({ 'type': old_all_stanza[0], 'value': old_all_stanza[1] })

        # New rule object
        new_rule = {
            'alg': gear_name,
            'name': rule_name,
            'any': any_stanzas,
            'all': all_stanzas
        }

        # Insert rule on every project
        for project in project_ids:
            project_id = project['_id']

            new_rule_obj = copy.deepcopy(new_rule)
            new_rule_obj['project_id'] = str(project_id)

            config.db.project_rules.insert_one(new_rule_obj)

        logging.info('Upgrade v23, migrated rule ' + str(count) + ' of ' + str(len(global_rules)) + '...')
        count += 1

    # Remove obsolete singleton
    config.db.singletons.remove({"_id" : "rules"})
    logging.info('Upgrade v23, complete.')

def upgrade_to_25():
    """
    scitran/core PR #733

    Migrate refresh token from authtokens to seperate collection
    """

    auth_tokens = config.db.authtokens.find({'refresh_token': {'$exists': True}})

    for a in auth_tokens:
        refresh_doc = {
            'uid': a['uid'],
            'token': a['refresh_token'],
            'auth_type': a['auth_type']
        }
        config.db.refreshtokens.insert(refresh_doc)

    config.db.authtokens.update_many({'refresh_token': {'$exists': True}}, {'$unset': {'refresh_token': ''}})

def upgrade_to_26_closure(job):

    gear = config.db.gears.find_one({'_id': bson.ObjectId(job['gear_id'])}, {'gear.name': 1})

    # This logic WILL NOT WORK in parallel mode
    if gear is None:
        logging.info('No gear found for job ' + str(job['_id']))
        return True
    if gear.get('gear', {}).get('name', None) is None:
        logging.info('No gear found for job ' + str(job['_id']))
        return True

    # This logic WILL NOT WORK in parallel mode

    gear_name = gear['gear']['name']

    # Checks if the specific gear tag already exists for the job
    if gear_name in job['tags']:
        return True

    result = config.db.jobs.update_one({'_id': job['_id']}, {'$addToSet': {'tags': gear_name }})

    if result.modified_count == 1:
        return True
    else:
        return 'Parallel failed: update doc ' + str(job['_id']) + ' resulted modified ' + str(result.modified_count)


def upgrade_to_26():
    """
    scitran/core #734

    Add job tags back to the job document, and use a faster cursor-walking update method
    """
    cursor = config.db.jobs.find({})
    process_cursor(cursor, upgrade_to_26_closure)


def upgrade_to_27():
    """
    scitran/core PR #768

    Fix project templates that reference `measurement` instead of `measurements`
    Update all session compliance for affected projects
    """

    projects = config.db.projects.find({'template.acquisitions.files.measurement': {'$exists': True}})

    storage = ProjectStorage()

    for p in projects:
        template = p.get('template', {})
        for a in template.get('acquisitions', []):
            for f in a.get('files', []):
                if f.get('measurement'):
                    f['measurements'] = f.pop('measurement')
        config.log.debug('the template is now {}'.format(template))
        config.db.projects.update_one({'_id': p['_id']}, {'$set': {'template': template}})
        storage.recalc_sessions_compliance(project_id=str(p['_id']))

def upgrade_to_28():
    """
    Fixes session.subject.age sometimes being a floating-point rather than integer.
    """

    sessions = config.db.sessions.find({'subject.age': {'$type': 'double'}})
    logging.info('Fixing {} subjects with age stored as double ...'.format(sessions.count()))
    for session in sessions:
        try:
            session['subject']['age'] = int(session['subject']['age'])
        except:
            session['subject']['age'] = None

        config.db.sessions.update({'_id': session['_id']}, session)




def upgrade_to_29_closure(user):

    avatars = user['avatars']
    if avatars.get('custom') and not 'https:' in avatars['custom']:
        if user['avatar'] == user['avatars']['custom']:
            if(user['avatars'].get('provider') == None):
                config.db.users.update_one({'_id': user['_id']},
                    {'$unset': {'avatar': ""}})
            else:
                config.db.users.update_one({'_id': user['_id']},
                    {'$set': {'avatar': user['avatars'].get('provider')}}
                )
        logging.info('Deleting custom ...')
        config.db.users.update_one({'_id': user['_id']},
            {'$unset': {"avatars.custom": ""}}
        )
    return True


def upgrade_to_29():
    """
    Enforces HTTPS urls for user avatars
    """

    users = config.db.users.find({})
    process_cursor(users, upgrade_to_29_closure)

def upgrade_to_30_closure_analysis(coll_item, coll):
    analyses = coll_item.get('analyses', [])

    for analysis_ in analyses:
        files = analysis_.get('files', [])
        for file_ in files:
            if 'created' not in file_:
                file_['created'] = analysis_.get('created', datetime.datetime(1970, 1, 1))
    result = config.db[coll].update_one({'_id': coll_item['_id']}, {'$set': {'analyses': analyses}})
    if result.modified_count == 1:
        return True
    else:
        return "File timestamp creation failed for:" + str(coll_item)

def upgrade_to_30_closure_coll(coll_item, coll):
    files = coll_item.get('files', [])
    for file_ in files:
        if 'created' not in file_:
            file_['created'] = coll_item.get('created', datetime.datetime(1970, 1, 1))
    result = config.db[coll].update_one({'_id': coll_item['_id']}, {'$set': {'files': files}})
    if result.modified_count == 1:
        return True
    else:
        return "File timestamp creation failed for:" + str(coll_item)


def upgrade_to_30():
    """
    scitran/core issue #759

    give created timestamps that are missing are given based on the parent object's timestamp
    """

    cursor = config.db.collections.find({'analyses.files.name': {'$exists': True},
                                         'analyses.files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_analysis, context = 'collections')

    cursor = config.db.sessions.find({'analyses.files.name': {'$exists': True},
                                      'analyses.files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_analysis, context = 'sessions')

    cursor = config.db.sessions.find({'files.name': {'$exists': True}, 'files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_coll, context = 'sessions')

    cursor = config.db.collections.find({'files.name': {'$exists': True}, 'files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_coll, context = 'collections')

    cursor = config.db.acquisitions.find({'files.name': {'$exists': True}, 'files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_coll, context = 'acquisitions')

    cursor = config.db.projects.find({'files.name': {'$exists': True}, 'files.created': {'$exists': False}})
    process_cursor(cursor, upgrade_to_30_closure_coll, context = 'projects')

def upgrade_to_31():
    config.db.sessions.update_many({'subject.firstname_hash': {'$exists': True}}, {'$unset': {'subject.firstname_hash':""}})
    config.db.sessions.update_many({'subject.lastname_hash': {'$exists': True}}, {'$unset': {'subject.lastname_hash':""}})

def upgrade_to_32_closure(coll_item, coll):
    permissions = coll_item.get('permissions', [])
    for permission_ in permissions:
        if permission_.get('site', False):
            del permission_['site']
    result = config.db[coll].update_one({'_id': coll_item['_id']}, {'$set': {'permissions' : permissions}})
    if result.modified_count == 0:
        return "Failed to remove site field"
    return True

def upgrade_to_32():
    for coll in ['acquisitions', 'groups', 'projects', 'sessions']:
        cursor = config.db[coll].find({'permissions.site': {'$exists': True}})
        process_cursor(cursor, upgrade_to_32_closure, context = coll)
    config.db.sites.drop()

def upgrade_to_33_closure(cont, cont_name):
    cont_type = cont_name[:-1]
    if cont.get('analyses'):
        for analysis in cont['analyses']:
            analysis['_id'] = bson.ObjectId(analysis['_id'])
            analysis['parent'] = {'type': cont_type, 'id': cont['_id']}
            analysis['permissions'] = cont['permissions']
            for key in ('public', 'archived'):
                if key in cont:
                    analysis[key] = cont[key]
        config.db['analyses'].insert_many(cont['analyses'])
    config.db[cont_name].update_one(
        {'_id': cont['_id']},
        {'$unset': {'analyses': ''}})
    return True

def upgrade_to_33():
    """
    scitran/core issue #808 - make analyses use their own collection
    """
    for cont_name in ['projects', 'sessions', 'acquisitions', 'collections']:
        cursor = config.db[cont_name].find({'analyses': {'$exists': True}})
        process_cursor(cursor, upgrade_to_33_closure, context=cont_name)

def upgrade_to_34():
    """
    Changes group.roles -> groups.permissions

    scitran/core #662
    """
    config.db.groups.update_many({'roles': {'$exists': True}}, {'$rename': {'roles': 'permissions'}})
    config.db.groups.update_many({'name': {'$exists': True}}, {'$rename': {'name': 'label'}})

def upgrade_to_35_closure(batch_job):
    if batch_job.get('state') in ['cancelled', 'running', 'complete', 'failed']:
        return True
    batch_id = batch_job.get('_id')
    config.db.jobs.update_many({'_id': {'$in': batch_job.get('jobs',[])}}, {'$set': {'batch':batch_id}})
    new_state = batch.check_state(batch_id)
    if new_state:
        result = config.db.batch.update_one({'_id': batch_id}, {'$set': {"state": new_state}})
        if result.modified_count != 1:
            raise Exception('Batch job not updated')
    else:
        result = config.db.batch.update_one({'_id': batch_id}, {'$set': {"state": "running"}})
        if result.modified_count != 1:
            raise Exception('Batch job not updated')
    return True

def upgrade_to_35():
    """
    scitran/core issue #710 - give batch stable states
    """
    cursor = config.db.batch.find({})
    process_cursor(cursor, upgrade_to_35_closure)


def upgrade_to_36_closure(acquisition):

    for f in acquisition['files']:
        if not f.get('mimetype'):
            logging.debug('file with name {} did not have mimetype'.format(f['name']))
            f['mimetype'] = util.guess_mimetype(f['name'])

    result = config.db.acquisitions.update_one({'_id': acquisition['_id']}, {'$set': {'files': acquisition['files']}})
    if result.modified_count != 1:
        raise Exception('Acquisition file not updated')

    return True


def upgrade_to_36():
    """
    scitran/core issue #931 - mimetype not set on packfile uploads
    """
    cursor = config.db.acquisitions.find({'files': { '$gt': [] }, 'files.mimetype': None})
    process_cursor(cursor, upgrade_to_36_closure)

def upgrade_to_37():
    """
    scitran/core issue #916 - group-permission level site info needs to be removed from all levels
    """
    for coll in ['acquisitions', 'groups', 'projects', 'sessions', 'analyses']:
        cursor = config.db[coll].find({'permissions.site': {'$exists': True}})
        process_cursor(cursor, upgrade_to_32_closure, context = coll)


def upgrade_to_38_closure(user):

    # if user has existing API key in correct db location, remove API key stored on user and move on
    # otherwise, migrate api key to new location

    api_key = user['api_key']
    doc = config.db.apikeys.find_one({'uid': user['_id'], 'type': 'user'})

    if not doc:

        # migrate existing API key

        new_api_key_doc = {
            '_id': api_key['key'],
            'created': api_key['created'],
            'last_used': api_key['last_used'],
            'uid': user['_id'],
            'type': 'user'
        }

        config.db.apikeys.insert(new_api_key_doc)

    config.db.users.update_one({'_id': user['_id']}, {'$unset': {'api_key': 0}})

    return True


def upgrade_to_38():
    """
    Move existing user api keys to new 'apikeys' collection
    """
    cursor = config.db.users.find({'api_key': {'$exists': True }})
    process_cursor(cursor, upgrade_to_38_closure)


def upgrade_to_39_closure(job):
    """
    Done in python because:
    " the source and target field for $rename must not be on the same path "
    """

    config_ = job.pop('config', {})
    config.db.jobs.update({'_id': job['_id']}, {'$set': {'config': {'config': config_}}})

    return True

def upgrade_to_39():
    """
    Move old jobs without extra config down one level to match new jobs
    with additional keys.

    Before:
    {
        'config': {
            'a': 'b'
        }
    }

    After:
    {
        'config': {
            'config': {
                'a': 'b'
            }
        }
    }
    """
    cursor = config.db.jobs.find({'config': {'$exists': True }, 'config.config': {'$exists': False }})
    process_cursor(cursor, upgrade_to_39_closure)


def upgrade_to_40_closure(acquisition):
    config.db.acquisitions.update_one({'_id':acquisition['_id']},{'$set':{'timestamp':dateutil.parser.parse(acquisition['timestamp'])}})
    return True

def upgrade_to_40():
    """
    Convert all string acquisition timestamps to type date
    """
    cursor = config.db.acquisitions.find({'timestamp':{'$type':'string'}})
    process_cursor(cursor, upgrade_to_40_closure)


def upgrade_to_41_closure(cont, cont_name):

    files = cont.get('files', [])
    for f in files:
        if 'tags' not in f:
            f['tags'] = []
        if 'measurements' not in f:
            f['measurements'] = []
        if 'origin' not in f:
            f['origin'] = {
                'type': str(Origin.unknown),
                'id': None
            }
        if 'mimetype' not in f:
            f['mimetype'] = util.guess_mimetype(f.get('name'))
        if 'modality' not in f:
            f['modality'] = None
    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})
    return True


def upgrade_to_41():
    """
    scitran/core issue #1042 - some "expected" file default keys are not present

    These are the fields that are created on every file object in upload.py
    """

    for cont_name in ['groups', 'projects', 'sessions', 'acquisitions', 'collections', 'analyses']:
        cursor = config.db[cont_name].find({'files': { '$elemMatch': { '$or': [
            {'tags':          {'$exists': False }},
            {'measurements':  {'$exists': False }},
            {'origin':        {'$exists': False }},
            {'mimetype':      {'$exists': False }},
            {'modality':      {'$exists': False }}
        ]}}})
        process_cursor(cursor, upgrade_to_41_closure, context=cont_name)


def upgrade_to_42_closure(cont, cont_name):
    archived = cont.pop('archived')
    update = {'$unset': {'archived': True}}
    if archived:
        cont['tags'] = cont.get('tags', []) + ['hidden']
        update['$set'] = {'tags': cont['tags']}
    config.db[cont_name].update_one({'_id': cont['_id']}, update)
    return True

def upgrade_to_42():
    """
    Change container flag "archived" to container tag "hidden"
    """
    for cont_name in ['groups', 'projects', 'sessions', 'acquisitions']:
        cursor = config.db[cont_name].find({'archived': {'$exists': True}})
        process_cursor(cursor, upgrade_to_42_closure, cont_name)


def upgrade_to_43_closure(analysis):
    inputs = [f for f in analysis['files'] if f.get('input')]
    outputs = [f for f in analysis['files'] if f.get('output')]
    for f in inputs + outputs:
        f.pop('input', None)
        f.pop('output', None)
    config.db.analyses.update_one({'_id': analysis['_id']}, {'$set': {'inputs': inputs, 'files': outputs}})
    return True

def upgrade_to_43():
    """
    Remove analysis files' input/output tags and store them separately instead:
       - inputs under `analysis.inputs`
       - outputs under `analysis.files`
    """
    cursor = config.db.analyses.find({'files': {'$exists': True, '$ne': []}})
    process_cursor(cursor, upgrade_to_43_closure)


def upgrade_to_44():
    """
    A rerun of scitran/core issue #263

    A rerun was necessary because a bug was found when moving a session to a new project:
    the subject id should change but it was not, causing subject linking where there should be none

    Add '_id' field to session.subject
    Give subjects with the same code and project the same _id
    """

    pipeline = [
        {'$group' : { '_id' : {'pid': '$project', 'code': '$subject.code'}, 'sids': {'$push': '$_id' }}}
    ]

    subjects = config.db.sessions.aggregate(pipeline)
    for subject in subjects:

        # Subjects without a code and sessions without a subject
        # will be returned grouped together, but all need unique IDs
        if subject['_id'].get('code') is None:
            for session_id in subject['sids']:
                subject_id = bson.ObjectId()
                config.db.sessions.update_one({'_id': session_id},{'$set': {'subject._id': subject_id}})
        else:
            subject_id = bson.ObjectId()
            query = {'_id': {'$in': subject['sids']}}
            update = {'$set': {'subject._id': subject_id}}
            config.db.sessions.update_many(query, update)


def upgrade_files_to_45(cont, context):
    """
    if the file has a modality, we try to find a matching classification
    key and value for each measurement in the modality's classification map

    if there is no modality or the modality cannot be found in the modalities
    collection, all measurements are added to the custom key
    """
    conversionTable = {
        "anatomy_inplane":  { "Contrast": ["T1"],               "Intent": ["Structural"],    "Features": ["In-Plane"] },
        "anatomy_ir":       {                                   "Intent": ["Structural"]                              },
        "anatomy_pd":       { "Contrast": ["PD"],               "Intent": ["Structural"]                              },
        "anatomy_t1w":      { "Contrast": ["T1"],               "Intent": ["Structural"]                              },
        "anatomy_t2w":      { "Contrast": ["T2"],               "Intent": ["Structural"]                              },
        "calibration":      {                                   "Intent": ["Calibration"]                             },
        "coil_survey":      { "Contrast": ["B1"],               "Intent": ["Calibration"]                             },
        "diffusion":        { "Contrast": ["Diffusion"],        "Intent": ["Structural"]                              },
        "diffusion_map":    { "Contrast": ["Diffusion"],        "Intent": ["Structural"],     "Features": ["Derived"] },
        "field_map":        { "Contrast": ["B0"],               "Intent": ["Fieldmap"]                                },
        "functional":       { "Contrast": ["T2*"],              "Intent": ["Functional"]                              },
        "functional_map":   {                                   "Intent": ["Functional"],     "Features": ["Derived"] },
        "high_order_shim":  {                                   "Intent": ["Shim"]                                    },
        "localizer":        { "Contrast": ["T2"],               "Intent": ["Localizer"]                               },
        "non-image":        {                                   "Intent": ["Non-Image"]                               },
        "perfusion":        { "Contrast": ["Perfusion"],                                                              },
        "spectroscopy":     { "Contrast": ["Spectroscopy"]                                                            },
        "screenshot":       {                                   "Intent": ["Screenshot"]                              }
    }

    files = cont['files']
    mr_modality = context['mr_modality']
    cont_name = context['cont_name']

    for f in cont['files']:
        modality = f.get('modality')
        measurements = f.pop('measurements', None)

        # If the file's modality is MR or if they have a measurement in the conversion table above, this is a special case
        if (modality and modality.upper() == 'MR') or any([conversionTable.get(measurement) for measurement in measurements]):

            f['modality'] = modality = 'MR' # Ensure uppercase for storage
            classification = {}
            m_class = mr_modality['classification']

            for m in measurements:
                if conversionTable.get(m):

                    # If the measurement is in the left side of the conversion table, apply those settings
                    for k, v in conversionTable[m].iteritems():
                        classification[k] = classification.get(k,[]) + v

                else:
                    # Otherwise try to find it's case insensitive match in MR's classification
                    for k, v_array in m_class.iteritems():
                        for v in v_array:
                            if v.lower() == m.lower():
                                classification[k] = classification.get(k,[]) + [v]


            # Make sure every value is only in the list once
            for k, v_array in classification.iteritems():
                classification[k] = list(set(v_array))

            f['classification'] = classification


        # No matter what put the file's measurements in to the custom field if it has any
        if measurements:
            if not f.get('classification'):
                f['classification'] = {}
            f['classification']['Custom'] = measurements


    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})

    return True

def upgrade_rules_to_45(rule):

    def adjust_type(r):
        if r['type'] == 'file.measurements':
            r['type'] = 'file.classification'
        elif r['type'] == 'container.has-measurements':
            r['type'] = 'container.has-classification'

    for r in rule.get('any', []):
        adjust_type(r)

    for r in rule.get('all', []):
        adjust_type(r)

    config.db.project_rules.replace_one({'_id': rule['_id']}, rule)

    return True

def upgrade_templates_to_45(project):
    """
    Set any measurements keys to classification
    """

    template = project['template']

    for a in template.get('acquisitions', []):
        for f in a.get('files', []):
            if 'measurements' in f:
                cl = f.pop('measurements')
                f['classification'] = cl

    config.db.projects.update_one({'_id': project['_id']}, {'$set': {'template': template}})

    return True

def upgrade_to_45():
    """
    Update classification for all files with existing measurements field
    """

    # Seed modality collection:
    mr_modality = {
            "_id": "MR",
            "classification": {
                "Contrast": ["B0", "B1", "T1", "T2", "T2*", "PD", "MT", "ASL", "Perfusion", "Diffusion", "Spectroscopy", "Susceptibility", "Velocity", "Fingerprinting"],
                "Intent": ["Localizer", "Shim", "Calibration", "Fieldmap", "Structural", "Functional", "Screenshot", "Non-Image"],
                "Features": ["Quantitative", "Multi-Shell", "Multi-Echo", "Multi-Flip", "Multi-Band", "Steady-State", "3D", "Compressed-Sensing", "Eddy-Current-Corrected", "Fieldmap-Corrected", "Gradient-Unwarped", "Motion-Corrected", "Physio-Corrected", "Derived", "In-Plane", "Phase", "Magnitude"]
            }
        }
    if not config.db.modalities.find_one({'_id': 'MR'}):
        config.db.modalities.insert(mr_modality)

    for cont_name in ['groups', 'projects', 'collections', 'sessions', 'acquisitions', 'analyses']:

        cursor = config.db[cont_name].find({'files.measurements': {'$exists': True }})
        context = {'cont_name':cont_name, 'mr_modality':mr_modality}
        process_cursor(cursor, upgrade_files_to_45, context=context)


    cursor = config.db.project_rules.find({'$or': [
        {'all.type': {'$in': ['file.measurements', 'container.has-measurements']}},
        {'any.type': {'$in': ['file.measurements', 'container.has-measurements']}}
    ]})

    process_cursor(cursor, upgrade_rules_to_45)

    cursor = config.db.projects.find({'template': {'$exists': True }})
    process_cursor(cursor, upgrade_templates_to_45)


def upgrade_to_46():
    """
    Update gears to ensure they all have the created timestamp, will be set
    to EPOCH if they don't have it
    """
    config.db.gears.update_many({"created":{"$exists":False}}, {'$set': {'created': datetime.datetime(1970,1,1), 'modified': datetime.datetime.utcnow()}})


def upgrade_to_47():
    """
    Use ObjectId for device._id (part of device key authentication)
    """
    for device in config.db.devices.find({'_id': {'$type': 'string'}}):
        config.db.devices.delete_one({'_id': device['_id']})
        device['label'] = device.pop('_id')    # Save old _id string as label
        device['type'] = device.pop('method', device['label'])  # Rename method to type (engine, reaper, etc.)
        device['_id'] = bson.ObjectId()        # Generate oid
        config.db.devices.insert_one(device)


def upgrade_files_to_48(cont, cont_name):
    """
    Issue #1200
    In db upgrade 47, we changed how device objects are stored in the database:
    Thier `_id` became their `label` and the were given an ObjectId as their new `_id`

    With that new format, origins added to files after the change had a (str'd) ObjectId
    as their `origin.id`, while old still had the human readable string label. This update
    will move all old origins to the new format, marking the ones that we cannot transition
    to unknown/null.
    """

    devices = config.db.devices.find({})
    device_id_by_name = {d['label']: str(d['_id']) for d in devices}
    files = cont.get('files', [])

    for f in files:
        if f.get('origin') and f['origin'].get('type') == 'device':
            if not bson.ObjectId.is_valid(f['origin']['id']):

                # Old style device origin, try to find it in the table
                if f['origin']['id'] in device_id_by_name:
                    f['origin']['id'] = device_id_by_name[f['origin']['id']]

                else:
                    # This device must have either changed ids, or is no longer in the system
                    # Create a device for this _id and insert it into the devices tables
                    device = {
                        '_id':      bson.ObjectId(),
                        'label':    f['origin']['id'],
                        'type':     f['origin'].get('method', 'unknown'),
                        'name':     f['origin'].get('name')
                    }
                    config.db.devices.insert_one(device)
                    device_id_by_name[device['label']] = str(device['_id'])

                    f['origin']['id'] = str(device['_id'])


    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})

    return True


def upgrade_to_48():
    """
    Update old device origin id to new
    """

    for cont_name in ['groups', 'projects', 'collections', 'sessions', 'acquisitions', 'analyses']:

        cursor = config.db[cont_name].find({'files.origin.type': 'device'})
        process_cursor(cursor, upgrade_files_to_48, cont_name)

def upgrade_files_to_49(cont, cont_name):

    files = cont.get('files', [])

    for f in files:
        if f.get('classification') and 'Contrast' in f['classification']:
            f['classification']['Measurement'] = f['classification'].pop('Contrast')


    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})

    return True



def upgrade_to_49():
    """
    Rename `Contrast` to `Measurement` for a more accurate classification description
    """
    mr_modality = config.db.modalities.update(
        {'_id': 'MR', 'classification.Contrast': {'$exists': True}},
        {'$rename': {'classification.Contrast': 'classification.Measurement'}}
    )

    for cont_name in ['groups', 'projects', 'collections', 'sessions', 'acquisitions', 'analyses']:
        cursor = config.db[cont_name].find({'files.classification.Contrast': {'$exists': True}})
        process_cursor(cursor, upgrade_files_to_49, cont_name)

def upgrade_files_to_50(cont, cont_name):
    """
    For any file where measurements had moved to Custom classification, move it back to measurements
    """
    old_measurements = {
        "anatomy_inplane",
        "anatomy_ir",
        "anatomy_pd",
        "anatomy_t1w",
        "anatomy_t2w",
        "calibration",
        "coil_survey",
        "diffusion",
        "diffusion_map",
        "field_map",
        "functional",
        "functional_map",
        "high_order_shim",
        "localizer",
        "non-image",
        "perfusion",
        "spectroscopy",
        "screenshot"
    }

    files = cont['files']

    for f in files:
        classification = f.get('classification')
        if not classification:
            continue

        custom = classification.get('Custom', [])
        if custom:
            measurements = []
            # Pop old measurements back into the measurements field
            for value in old_measurements:
                if value in custom:
                    custom.remove(value)
                    measurements.append(value)

            # If we updated measurements, add it to the file
            if measurements:
                f['measurements'] = measurements

            # Remove Custom if custom is now empty
            if not custom:
                classification.pop('Custom')

    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})
    return True

def upgrade_to_50():
    """
    Move measurement values from custom back to measurements field for legacy support
    """
    for cont_name in ['groups', 'projects', 'collections', 'sessions', 'acquisitions', 'analyses']:
        # Only operate on files with custom classification values
        cursor = config.db[cont_name].find({'files.classification.Custom': {'$exists': True, '$ne': []}})
        process_cursor(cursor, upgrade_files_to_50, cont_name)

def upgrade_to_51():
    """
    Get rid of permissions on analyses
    """
    config.db.analyses.update_many({}, {"$unset": {"permissions": ""}})

def upgrade_job_to_52(job, gears):
    job_id = job.get('_id')
    gear_id = str(job.get('gear_id'))
    gear_doc = gears.get(gear_id)

    if not gear_doc:
        logging.warn('Unable to upgrade job {} to 52 - gear {} does not exist!'.format(job['_id'], gear_id))
        return True

    gear = gear_doc.get('gear', {})
    update_doc = {'$set': {
        'gear_info': {
            'category': gear_doc.get('category'),
            'name': gear.get('name'),
            'version': gear.get('version')
        }
    }}
    config.db.jobs.update_one({'_id': job_id}, update_doc)
    update_doc['$set']['gear_info']['id'] = gear_id
    config.db.analyses.update_one({'job': str(job_id)}, update_doc)
    return True

def upgrade_to_52():
    """
    Copy gear category, name and version to job and analysis
    """
    # Preload gears
    gears = {}
    for gear in config.db.gears.find():
        gears[str(gear['_id'])] = gear

    cursor = config.db.jobs.find()
    process_cursor(cursor, upgrade_job_to_52, gears)

def upgrade_to_53():
    """
    Update rules to reference gears by id (`gear_id`) instead of name (`alg`)
    """

    cursor = config.db.gears.aggregate([
        {'$sort': {'gear.name': 1,
                   'created': -1}},
        {'$group': {'_id': '$gear.name',
                    'latest': {'$first': '$_id'}}}])
    gear_name_to_id = {gear['_id']: str(gear['latest']) for gear in cursor}

    for rule in config.db.project_rules.find({'alg': {'$exists': True}}):
        config.db.project_rules.update_one(
            {'_id': rule['_id']},
            {'$set': {'gear_id': gear_name_to_id[rule['alg']], 'auto_update': True},
             '$unset': {'alg': True}})

def upgrade_children_to_54(cont, cont_name):
    CHILD_MAP ={
        "projects": "sessions",
        "sessions": "acquisitions"
    }
    if cont_name == 'projects':
        config.db.projects.update_one({'_id': cont['_id']}, {'$set': {'parents': {'group': cont['group']}}})
        cont['parents'] = {'group': cont['group']}

    cont_type = containerutil.singularize(cont_name)
    parents = cont.get('parents', {})
    parents[cont_type] = cont['_id']
    config.db['analyses'].update_many({'parent.id': cont['_id']}, {'$set': {'parents': parents}})

    if cont_name != 'acquisitions':
        child_name = CHILD_MAP[cont_name]
        config.db[child_name].update_many({cont_type: cont['_id']}, {'$set': {'parents': parents}})

        cursor = config.db[child_name].find({cont_type: cont['_id']})
        process_cursor(cursor, upgrade_children_to_54, child_name)

    return True

def upgrade_api_keys_to_54(cont):
    config.db.apikeys.update_one({'_id': cont['_id']},
                                 {'$set': {'origin': {'type': cont['type'],
                                                      'id': cont['uid']}},
                                  '$unset': {'uid': ''}})
    return True

def upgrade_to_54():
    """
    Set parents for all projects, sessions, acquisitions, and analyses
    Apikeys have origins
    """

    cursor = config.db.projects.find({})
    process_cursor(cursor, upgrade_children_to_54, 'projects')

    cursor = config.db.apikeys.find({})
    process_cursor(cursor, upgrade_api_keys_to_54)


def upgrade_to_55(dry_run=False):
    """Move subjects into their own collection"""

    def extract_subject(session):
        """Extract and return augmented subject document, leave subject reference on session"""
        subject = session.pop('subject')
        if 'parents' not in session:
            # TODO find and address code that lets parent-less containers through to mongo
            logging.warning('adding missing parents key on session %s', session['_id'])
            session['parents'] = {'group': session['group'], 'project': session['project']}
        subject.update({
            'parents': session['parents'],
            'project': session['project'],
            'permissions': session['permissions']
        })
        if subject.get('age'):
            session['age'] = subject.pop('age')
        session['subject'] = subject['_id']
        containerutil.attach_raw_subject(session, subject, additional_fields=['info'])
        return subject

    def merge_dict(a, b):
        """Merge dict a and b in place, into a"""
        for k in b:
            if k not in a:  # add new key
                a[k] = b[k]
            elif a[k] == b[k]:  # skip unchanged
                pass
            elif b[k] in ('', None):  # skip setting empty
                pass
            elif a[k] in ('', None):  # replace null without storing history, alerting
                a[k] = b[k]
            elif type(a[k]) == type(b[k]) == dict:  # recurse in dict
                merge_dict(a[k], b[k])
            else:  # handle conflict
                logging.warning('merge conflict on key %s on subject %s', k, a.get('_id') or b.get('_id'))
                a[k] = b[k]

    session_groups = config.db.sessions.aggregate([
        {'$match': {'deleted': {'$exists': False}}},
        {'$group': {'_id': {'project': '$project', 'code': '$subject.code'},
                    'sessions': {'$push': '$$ROOT'}}},
        {'$sort': collections.OrderedDict([('_id.project', 1), ('_id.code', 1)])},
    ])

    inserted_subject_ids = []
    for session_group in session_groups:
        logging.info('project: {} / subject: {!r} ({} session{})'.format(
            session_group['_id'].get('project'),
            session_group['_id'].get('code'),
            len(session_group['sessions']), 's' if len(session_group['sessions']) != 1 else ''))
        # sort sessions by 'created' to merge subjects in chronological order (TBD modified instead)
        sessions = list(sorted(session_group['sessions'], key=lambda s: s['created']))
        # make sure subjects w/ missing/empty code are assigned different ids (see also updates 17 and 44)
        if session_group['_id'].get('code') in ('', None):
            for session in sessions:
                if session['subject']['_id'] in inserted_subject_ids:
                    session['subject']['_id'] = bson.ObjectId()
                subject = extract_subject(session)
                subject.update({'created': session['created'], 'modified': session['modified']})
                if not dry_run:
                    config.db.subjects.insert_one(subject)
                    config.db.sessions.update_one({'_id': session['_id']}, {'$set': session})
                inserted_subject_ids.append(subject['_id'])
            continue
        # (subjects collection requires, but) project/code based session groups aren't guaranteed to:
        # - have the same subject id on all sessions in any group
        # - have a unique subject id across all groups
        # pick a subject id from the group that hasn't been inserted yet (ie. used for another group), else generate it
        subject_ids = [session['subject']['_id'] for session in sessions]
        subject_id = next((_id for _id in subject_ids if _id not in inserted_subject_ids), bson.ObjectId())
        merged_subject = {}
        for session in sessions:
            session['subject']['_id'] = subject_id
            subject = extract_subject(session)
            merge_dict(merged_subject, subject)

        # Move top-level history keys to info block to not clutter new subject object
        for k in merged_subject.keys():
            if k.endswith('_history'):
                merged_subject.setdefault('info', {}) # only set it if we have to
                merged_subject['info'][k] = merged_subject.pop(k)

        min_created = min(s['created'] for s in sessions)
        max_modified = max(s['modified'] for s in sessions)
        subject.update({'created': min_created, 'modified': max_modified})
        if not dry_run:
            config.db.subjects.insert_one(merged_subject)
        inserted_subject_ids.append(subject_id)
        for session in sessions:
            if not dry_run:
                config.db.sessions.update_one({'_id': session['_id']}, {'$set': session})
        parents_update = {'$set': {'parents.subject': subject_id}}
        session_ids = [s['_id'] for s in sessions]
        acquisition_ids = [a['_id'] for a in config.db.acquisitions.find({'session': {'$in': session_ids}})]
        config.db.sessions.update_many({'_id': {'$in': session_ids}}, parents_update)
        config.db.acquisitions.update_many({'_id': {'$in': acquisition_ids}}, parents_update)
        config.db.analyses.update_many({'parent.id': {'$in': session_ids + acquisition_ids}}, parents_update)

def set_job_retried(job):
    config.db.jobs.update_one({'_id': bson.ObjectId(job['previous_job_id'])}, {'$set': {'retried': job['created']}})
    return True

def upgrade_to_56():
    jobs = config.db.jobs.find({'previous_job_id': {'$exists': True}}, {'previous_job_id': 1, 'created': 1})
    process_cursor(jobs, set_job_retried)

def upgrade_children_to_57(cont, cont_name):
    CHILD_MAP ={
        "subjects": "sessions",
        "sessions": "acquisitions"
    }

    cont_type = containerutil.singularize(cont_name)

    # Handle subject without parents
    if cont_type == 'subject':
        subject_group = config.db.projects.find_one({'_id': cont['project']})
        if subject_group:
            group_id = subject_group['group']
        parents = {'project': cont['project'], 'group': group_id}
        config.db.subjects.update({'_id': cont['_id']}, {'$set': {'parents': parents}})
    else:
        parents = cont.get('parents', {})

    parents[cont_type] = cont['_id']
    config.db['analyses'].update_many({'parent.id': cont['_id']}, {'$set': {'parents': parents}})

    if cont_name != 'acquisitions':
        child_name = CHILD_MAP[cont_name]
        config.db[child_name].update_many({cont_type: cont['_id']}, {'$set': {'parents': parents}})

        cursor = config.db[child_name].find({cont_type: cont['_id']})
        process_cursor(cursor, upgrade_children_to_57, child_name)

    return True

def upgrade_to_57():
    cursor = config.db.subjects.find({'parents': {'$exists': False}})
    process_cursor(cursor, upgrade_children_to_57, 'subjects')

def modality_maker():
    modalities = [m['_id'] for m in config.db.modalities.find({})]
    lower_modalities = [m.lower() for m in modalities]
    def upgrade_files_to_new_modalities(cont, cont_name):
        files = cont.get('files', [])
        file_updated = False
        for file_ in files:
            if file_.get('classification', {}).get('Custom') and not file_.get('modality'):
                try:
                    modality_index = lower_modalities.index(file_['classification'].get('Custom')[0].lower())
                    file_updated = True
                    file_['modality'] = modalities[modality_index]
                except ValueError:
                    continue
        if file_updated:
            config.db[cont_name].update_one({'_id': cont['_id']}, {"$set": {'files': files}})
        return True
    return upgrade_files_to_new_modalities

def upgrade_to_58():
    """
    Add new modalities and check if files belong to any of them
    """
    new_modalities = [
    {
        '_id': 'CT',
        'classification': {}
    },
    {
        '_id': 'PET',
        'classification': {}
    },
    {
        '_id': 'US',
        'classification': {}
    },
    {
        '_id': 'EEG',
        'classification': {}
    },
    {
        '_id': 'iEEG',
        'classification': {}
    },
    {
        '_id': 'X-ray',
        'classification': {}
    },
    {
        '_id': 'ECG',
        'classification': {}
    },
    {
        '_id': 'MEG',
        'classification': {}
    },
    {
        '_id': 'NIRS',
        'classification': {}
    }
    ]

    for modality in new_modalities:
        if not config.db.modalities.find_one({'_id': modality['_id']}):
            config.db.modalities.insert(modality)

    closure = modality_maker()
    for cont_name in ['projects', 'sessions', 'acquisitions', 'analyses']:
        cursor = config.db[cont_name].find({'files': {'$elemMatch': {'modality': {'$in': ['', None]},
                                                                     '$and': [{'classification.Custom': {'$ne': []}},
                                                                              {'classification.Custom': {'$exists': True}}]}}})
        process_cursor(cursor, closure, cont_name)


def upgrade_bash_files_to_59(cont, cont_name):
    """"""
    files = cont.get('files', [])
    dirty = False
    for file_ in files:
        _, extension = os.path.splitext(file_['name'])
        if extension == '.sh':
            dirty = True
            file_['type'] = 'source code'
    if dirty:
        config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'files': files}})
    return True

def upgrade_to_59():
    """
    Set files with ext .sh to type source code
    """
    for cont_name in ["projects", "sessions", "acquisitions", "analyses"]:
        cursor = config.db[cont_name].find({"files.type": None, "files.name": {"$regex": "\\.sh$"}})
        process_cursor(cursor, upgrade_bash_files_to_59, cont_name)


def add_subject_created_timestamps(cont):
    sessions = list(config.db.sessions.find({'subject': cont['_id']}))
    min_created = min([s['created'] for s in sessions] + [get_bson_timestamp(cont['_id'])])
    update = {'created': min_created}
    if not cont.get('modified'):
        update['modified'] = max([s['modified'] for s in sessions] + [datetime.datetime.now(None)])
    config.db.subjects.update_one({'_id': cont['_id']}, {'$set': update})
    return True


def give_session_parents(cont):
    parents = {
        'group': cont['group'],
        'project': cont['project'],
        'subject': cont['subject']
    }

    config.db.sessions.update_one({'_id': cont['_id']}, {'$set': {'parents': parents}})


    parents['session'] = cont['_id']
    config.db.analyses.update_many({'parent.id': cont['_id']}, {'$set': {'parents': parents}})


    config.db.acquisitions.update_many({'session': cont['_id']}, {'$set': {'parents': parents}})
    return True

def upgrade_to_60(dry_run=False):
    """
    This upgrade formalizes subjects on deleted sessions that were skipped in 55
    If the subject already was formalized, a new one tagged with a '-deleted' sufffix
    to the subject code is created.

    The upgrade also adds in teh created timestamp for subjects that didn't get one.

    It also adds in the parent keys for sessions that didn't have one
    """
    def extract_subject(session):
        """Extract and return augmented subject document, leave subject reference on session"""
        subject = session.pop('subject')
        if 'parents' not in session:
            # TODO find and address code that lets parent-less containers through to mongo
            logging.warning('adding missing parents key on session %s', session['_id'])
            session['parents'] = {'group': session['group'], 'project': session['project']}
        subject.update({
            'parents': session['parents'],
            'project': session['project'],
            'permissions': session['permissions']
        })
        if subject.get('age'):
            session['age'] = subject.pop('age')
        session['subject'] = subject['_id']
        containerutil.attach_raw_subject(session, subject, additional_fields=['info'])
        return subject

    def merge_dict(a, b):
        """Merge dict a and b in place, into a"""
        for k in b:
            if k not in a:  # add new key
                a[k] = b[k]
            elif a[k] == b[k]:  # skip unchanged
                pass
            elif b[k] in ('', None):  # skip setting empty
                pass
            elif a[k] in ('', None):  # replace null without storing history, alerting
                a[k] = b[k]
            elif type(a[k]) == type(b[k]) == dict:  # recurse in dict
                merge_dict(a[k], b[k])
            else:  # handle conflict
                logging.warning('merge conflict on key %s on subject %s', k, a.get('_id') or b.get('_id'))
                a[k] = b[k]

    session_groups = config.db.sessions.aggregate([
        {'$match': {'deleted': {'$exists': True}, 'subject': {'$type': 'object'}}},
        {'$group': {'_id': {'project': '$project', 'code': '$subject.code'},
                    'sessions': {'$push': '$$ROOT'}}},
        {'$sort': collections.OrderedDict([('_id.project', 1), ('_id.code', 1)])},
    ])

    inserted_subject_ids = []
    for session_group in session_groups:
        logging.info('project: {} / subject: {!r} ({} session{})'.format(
            session_group['_id'].get('project'),
            session_group['_id'].get('code'),
            len(session_group['sessions']), 's' if len(session_group['sessions']) != 1 else ''))
        # sort sessions by 'created' to merge subjects in chronological order (TBD modified instead)
        sessions = list(sorted(session_group['sessions'], key=lambda s: s['created']))
        # make sure subjects w/ missing/empty code are assigned different ids (see also updates 17 and 44)
        if session_group['_id'].get('code') in ('', None):
            for session in sessions:
                session['subject']['_id'] = bson.ObjectId()
                subject = extract_subject(session)
                subject.update({'created': session['created'], 'modified': session['modified']})
                if not dry_run:
                    config.db.subjects.insert_one(subject)
                    config.db.sessions.update_one({'_id': session['_id']}, {'$set': session})
                inserted_subject_ids.append(subject['_id'])
            continue
        # (subjects collection requires, but) project/code based session groups aren't guaranteed to:
        # - have the same subject id on all sessions in any group
        # - have a unique subject id across all groups
        # pick a subject id from the group that hasn't been inserted yet (ie. used for another group), else generate it
        subject_ids = [session['subject']['_id'] for session in sessions]
        subject_id = next((_id for _id in subject_ids if _id not in inserted_subject_ids), bson.ObjectId())
        merged_subject = {}
        for session in sessions:
            session['subject']['_id'] = subject_id
            subject = extract_subject(session)
            merge_dict(merged_subject, subject)

        # Move top-level history keys to info block to not clutter new subject object
        for k in merged_subject.keys():
            if k.endswith('_history'):
                merged_subject.setdefault('info', {}) # only set it if we have to
                merged_subject['info'][k] = merged_subject.pop(k)

        min_created = min(s['created'] for s in sessions)
        max_modified = max(s['modified'] for s in sessions)
        min_deleted = min(s['deleted'] for s in sessions)
        merged_subject.update({'created': min_created, 'modified': max_modified, 'deleted': min_deleted})
        if not dry_run:
            if config.db.subjects.find_one({'project': session_group['_id']['project'], 'code': subject['code']}):
                # If the subject already exists, create a new one with a new id, suffixed with -deleted
                merged_subject['code'] = '{}-deleted'.format(subject['code'])
                merged_subject['_id'] = bson.ObjectId()
                for session in sessions:
                    session['subject'] = merged_subject['_id']
            elif config.db.subjects.find_one({'_id': merged_subject['_id']}):
                merged_subject['_id'] = bson.ObjectId()
                for session in sessions:
                    session['subject'] = merged_subject['_id']
            config.db.subjects.insert_one(merged_subject)

        inserted_subject_ids.append(subject_id)
        if not dry_run:
            for session in sessions:
                config.db.sessions.update_one({'_id': session['_id']}, {'$set': session})
            parents_update = {'$set': {'parents.subject': subject_id}}
            session_ids = [s['_id'] for s in sessions]
            acquisition_ids = [a['_id'] for a in config.db.acquisitions.find({'session': {'$in': session_ids}})]
            config.db.sessions.update_many({'_id': {'$in': session_ids}}, parents_update)
            config.db.acquisitions.update_many({'_id': {'$in': acquisition_ids}}, parents_update)
            config.db.analyses.update_many({'parent.id': {'$in': session_ids + acquisition_ids}}, parents_update)



    cursor = config.db.subjects.find({'created': None})
    logging.info("Adding in created timestamps for subjects")
    process_cursor(cursor, add_subject_created_timestamps)

    cursor = config.db.sessions.find({'$or': [{'parents': None}, {'parents.subject': None}]})
    logging.info("Adding in parents key for sessions")
    process_cursor(cursor, give_session_parents)



def add_timestamp(cont, cont_name):
    config.db[cont_name].update_one({'_id': cont['_id']}, {'$set': {'timestamp': get_bson_timestamp(cont['_id'])}})
    return True


def upgrade_to_61():
    '''
    Give all job_tickets a timestamp so that mongo removes old ones
    '''
    cursor = config.db.job_tickets.find({'timestamp': None})
    process_cursor(cursor, add_timestamp, 'job_tickets')


@cached(cache=LRUCache(maxsize=10000))
def get_ref_62(ctype, cid):
    ctype = containerutil.pluralize(ctype)
    return config.db[ctype].find_one({'_id': bson.ObjectId(cid)}, {'parents': True})

def set_job_containers_62(cont, cont_name):
    # Collect references
    refs = set()
    containers = []
    update = {}
    dest_ref = cont.get('destination', {})

    # Some very old legacy jobs have a dictionary rather than a list,
    # And for whatever reason were never upgraded by upgrade 11
    safe_inputs = cont.get('inputs', [])
    if not isinstance(safe_inputs, list):
        if safe_inputs:
            logging.error('Encountered a non-empty, non-list set of inputs on job: %s', cont['_id'])

        # Convert inputs to an array. See upgrade_to_11
        if isinstance(safe_inputs, dict):
            safe_inputs = []
            for key, inp in cont['inputs'].iteritems():
                inp['input'] = key
                safe_inputs.append(inp)

            update['inputs'] = safe_inputs
        else:
            logging.critical('Unknown input format, type=%s', type(safe_inputs))
            safe_inputs = []

    # Retrieve each reference once
    for ref in [dest_ref] + safe_inputs:
        if 'id' not in ref:
            # Invalid reference, ignore
            containers.append(None)
            continue

        cid = ref['id']
        if cid not in refs:
            containers.append(get_ref_62(ref['type'], cid))
            refs.add(cid)

    # Destination is first, and sets the group/project (if dest still exists)
    dest = containers[0]
    if dest is not None:
        update['parents'] = dest.get('parents', {})
        dest_type = dest_ref.get('type')
        dest_id = dest_ref.get('id')
        if dest_type and dest_id:
            update['parents'][dest_type] = bson.ObjectId(dest_id)

    # Now add all parents of all references to the refs set
    for c in containers:
        if not c:
            continue

        for parent_id in c.get('parents', {}).itervalues():
            refs.add(str(parent_id))

    update['related_container_ids'] = list(refs)
    config.db.jobs.update_one({'_id': cont['_id']}, {
        '$set': update,
        '$unset': { 'group': 1, 'project': 1 }
    })
    return True

def upgrade_to_62():
    """Update all jobs to populate group, project and related_container_ids"""
    # Fix parents before proceeding
    ensure_parents()

    # Drop group/project index in favor of parents
    drop_index('jobs', 'group')
    drop_index('jobs', 'project')

    # Update all jobs, set parents
    cursor = config.db.jobs.find({})
    process_cursor(cursor, set_job_containers_62, 'jobs')

def upgrade_template_to_list(cont):
    if cont.get('template'):
        template = cont.pop('template', None)
        if template is not None:
            cont['templates'] = [template]
        config.db.projects.find_one_and_update({'_id': cont['_id']}, {'$set': cont, '$unset': {'template': ''}})
    return True


def upgrade_to_63():
    '''
    All project templates should be list of templates
    '''
    cursor = config.db.projects.find({'template': {'$exists': True}})
    process_cursor(cursor, upgrade_template_to_list)

###
### BEGIN RESERVED UPGRADE SECTION
###

# Due to performance concerns with database upgrades, some upgrade implementations might be postposed.
# The team contract is that if you write an upgrade touch one of the tables mentioned below, you MUST also implement any reserved upgrades.
# This way, we can bundle changes together that need large cursor iterations and save multi-hour upgrade times.



###
### END RESERVED UPGRADE SECTION
###

def upgrade_to_64():
    '''
    All project templates should be list of templates
    '''

    config.db.create_collection('providers')

    provider = config.db.providers.insert_one({
        "origin": {"type":"system","id":"system"},
        "created": datetime.datetime.now(),
        "config":{"path":config.local_fs_url},
        "modified": datetime.datetime.now(),
        "label":"Local Storage",
        "provider_class":"storage",
        "provider_type":"osfs"
    })

    config.db.singletons.insert_one({
        "_id": "site",
        "center_gears": [],
        "created": datetime.datetimne.now(),
        "modified": datetime.datetime.now(),
        "providers": {"storage": provider.inserted_id}
    })
    
    # validate that all files have _ids
    config.db.acquisitions.files.find_one(
        {'_id': {'$exists': None}}
    )

    #Check if any file does not have a vaild _id
    if config.db.acquistions.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all aquistion files have a file._id'
    if config.db.analysis.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all analysis files have a file._id'
    if config.db.acquistions.find_one({'inputs': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all aquistion files have a file._id'
    if config.db.collections.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all collection files have a file._id'
    if config.db.projects.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all project files have a file._id'
    if config.db.sessions.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all session files have a file._id'
    if config.db.subjects.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all subject files have a file._id'
    if config.db.gears.find_one({'files': {'$elemMatch': { "_id": {'$exists': False }}}}):
        raise 'Not all subject files have a file._id'

    # TODO: update all files to have the provider id.  
    config.db.acquisitions.update_many(
        {'files._id': {'$exists': True}},
        {'$set': {'files.$.provider_id': provider.inserted_id}})
    config.db.analysis.update_many(
        {'files._id': {'$exists': True}},
        {'$set': {'files.$.provider_id': provider.inserted_id}})
    config.db.analysis.update_many(
        {'inputs._id': {'$exists': True}},
        {'$set': {'inputs.$.provider_id': provider.inserted_id}})
    config.db.collections.update_many(
        {'files._id': {'$exists': True}},
        {'$set': {'files.$.provider_id': provider.inserted_id}})
    config.db.projects.update_many(
        {'files._id': {'$exists': True}},
        {'$set': {'files.$.provider_id': provider.inserted_id}})
    config.db.sessions.update_many(
        {'files._id': {'$exists': True}},
        {'$set': {'files.$.provider_id': provider.inserted_id}})
    config.db.subject.update_many(
        {},
        {'$set': {'files.$.provider_id': provider.inserted_id}})

    config.db.gears.update_many(
        {'exchange.rootfs-id': {'$exists': True}},
        {'$set': {'exchange.rootfs-provider-id': provider.inserted_id}})

def upgrade_schema(force_from = None):
    """
    Upgrades db to the current schema version

    Returns (0) if upgrade is successful
    """

    db_version, applied_fixes = get_db_version()
    available_fixes = get_available_fixes(db_version, applied_fixes)

    if force_from:
        if isinstance(db_version,int) and db_version >= force_from:
            db_version = force_from
        else:
            logging.error('Cannot force from future version %s. Database only at version %s', str(force_from), str(db_version))
            sys.exit(43)


    if not isinstance(db_version, int) or db_version > CURRENT_DATABASE_VERSION:
        logging.error('The stored db schema version of %s is incompatible with required version %s',
                       str(db_version), CURRENT_DATABASE_VERSION)
        sys.exit(43)
    elif db_version == CURRENT_DATABASE_VERSION and not available_fixes:
        logging.error('Database already up to date.')
        sys.exit(43)

    update_doc = {}

    try:
        while db_version < CURRENT_DATABASE_VERSION:
            # Apply fixes before performing the next schema update
            apply_available_fixes(db_version, applied_fixes, update_doc)

            db_version += 1
            upgrade_script = 'upgrade_to_'+str(db_version)
            logging.info('Upgrading to version {} ...'.format(db_version))
            globals()[upgrade_script]()
            logging.info('Upgrade to version {} complete.'.format(db_version))

        # Last round of fixes for the current db version
        apply_available_fixes(db_version, applied_fixes, update_doc)
    except KeyError as e:
        logging.exception('Attempted to upgrade using script that does not exist: {}'.format(e))
        sys.exit(1)
    except Exception as e:
        logging.exception('Incremental upgrade of db failed')
        sys.exit(1)
    else:
        update_doc['database'] = CURRENT_DATABASE_VERSION
        config.db.singletons.update_one({'_id': 'version'}, {'$set': update_doc})
        sys.exit(0)

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("function", help="function to be called from database.py")
        parser.add_argument("-f", "--force_from", help="force database to upgrade from previous version", type=int)
        parser.add_argument("-F", "--fix-id", help="ID of fix to run if applying a fix")
        args = parser.parse_args()

        if args.function == 'confirm_schema_match':
            confirm_schema_match()
        elif args.function == 'upgrade_schema':
            if args.force_from:
                upgrade_schema(args.force_from)
            else:
                upgrade_schema()
        elif args.function == 'ensure_parents':
            ensure_parents()
        elif args.function == 'apply_fix':
            if not args.fix_id:
                logging.error('fix-id is required for apply_fix')
                sys.exit(1)
            # Raises if invalid fix_id is specified
            fixes.get_fix_function(args.fix_id)()
            # And update the database to indicate that we applied this fix
            config.db.singletons.update_one({'_id': 'version'}, {'$set': {
                'applied_fixes.{}'.format(args.fix_id): datetime.datetime.now() }})
        else:
            logging.error('Unknown method name given as argv to database.py')
            sys.exit(1)
    except Exception as e:
        logging.exception('Unexpected error in database.py')
        sys.exit(1)
