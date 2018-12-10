import bson
import calendar
import collections
import datetime
import json

FILE_DATA = 'a' * 1024
INPUT_FILE = ('input.txt', FILE_DATA)
EXTRA_FILE = ('extra.txt', FILE_DATA)
OUTPUT_FILE = ('output.txt', FILE_DATA)

def test_collect_todays_usage(data_builder, file_form, as_user, as_admin, as_drone, api_db, default_payload):
    group = data_builder.create_group()
    project = data_builder.create_project(label='usage', group=group)
    session = data_builder.create_session()
    acquisition = data_builder.create_acquisition()
    analysis = as_admin.post('/sessions/' + session + '/analyses', files=file_form(meta={'label': 'test'})).json()['_id']
    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(INPUT_FILE))

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'usage': {
            'base': 'file'
        }
    }
    gear = data_builder.create_gear(gear=gear_doc)

    job = data_builder.create_job(gear_id=gear, inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
    assert as_drone.get('/jobs/next', params={'root': 'true'}).ok
    r = as_drone.post('/engine',
        params={'root': 'true', 'level': 'analysis', 'id': analysis, 'job': job},
        files=file_form(OUTPUT_FILE, meta={'type': 'text', 'value': {'label': 'test'}})
    )
    assert r.ok
    assert as_drone.put('/jobs/' + job, params={'root': 'true'}, json={'state': 'complete'}).ok

    # Set execution time for job (30 minutes)
    result = api_db.jobs.update({'_id': bson.ObjectId(job)}, {'$set': {'profile.total_time_ms': 30 * 60 * 1000}})

    # Run default collection
    now = datetime.datetime.now()
    r = as_admin.get('/report/usage/collect', stream=True)

    status = []
    for line in r.iter_lines():
        if line.strip().startswith('data: '):
            status.append(json.loads(line.strip()[6:]))

    assert r.ok
    assert status[-1]['status'] == 'Complete'

    # Verify collection of "today's" record
    record = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': now.year, 'month': now.month})
    assert record

    day = str(now.day)
    assert day in record['days']

    assert record['project_label'] == 'usage'
    assert record['days'][day]['center_compute_ms'] == 0
    assert record['days'][day]['center_job_count'] == 0
    assert record['days'][day]['center_storage_bytes'] == 0
    assert record['days'][day]['group_compute_ms'] == 30 * 60 * 1000
    assert record['days'][day]['group_job_count'] == 1
    assert record['days'][day]['group_storage_bytes'] == 2 * len(FILE_DATA)
    assert record['days'][day]['session_count'] == 1
    assert record['total']['center_compute_ms'] == 0
    assert record['total']['center_job_count'] == 0
    assert record['total']['center_storage_bytes'] == 0
    assert record['total']['group_compute_ms'] == 30 * 60 * 1000
    assert record['total']['group_job_count'] == 1
    assert record['total']['group_storage_bytes'] == 2 * len(FILE_DATA)
    assert record['total']['sessions'] == 1

    # Verify that re-collection after creating new data in the day does not update
    # (i.e. once a day has been collected, it's a no-op to collect that day again)

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(EXTRA_FILE))
    r = as_admin.get('/report/usage/collect')
    assert r.ok

    record2 = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': now.year, 'month': now.month})
    assert record == record2

def test_usage_report(data_builder, file_form, as_user, as_admin, as_drone, api_db, default_payload):
    # Test multiple days that cross a monthly boundary
    # Test center vs group gears
    # Test reaper vs analysis vs uploaded data
    group = data_builder.create_group()
    project = data_builder.create_project(label='usage', group=group)

    gear_doc = default_payload['gear']['gear']
    gear_doc['inputs'] = {
        'usage': {
            'base': 'file'
        }
    }
    group_gear = data_builder.create_gear(gear=gear_doc)

    gear_doc['name'] = 'usage-report-center-gear'
    center_gear = data_builder.create_gear(gear=gear_doc)

    previous_site = api_db.singletons.find_one_and_update({'_id': 'site'}, {'$set': {'center_gears': ['usage-report-center-gear']}}, upsert=True)

    try:
        def populate_day(year, month, day):
            dt = datetime.datetime.now().replace(year=year, month=month, day=day)

            def update_created(ctype, cid, files=0):
                update = {'$set': {'created': dt}}
                for i in range(files):
                    update['$set']['files.{}.created'.format(i)] = dt

                api_db[ctype].update({'_id': bson.ObjectId(cid)}, update)

            def update_job(job_id):
                # Fake some numbers
                update = {'$set': {
                    'created': dt,
                    'modified': dt,
                    'profile.total_time_ms': 30 * 60 * 1000,
                    'transitions.running': dt,
                    'transitions.complete': dt
                }}
                api_db.jobs.update_one({'_id': bson.ObjectId(job_id)}, update)

            # Add session
            session = data_builder.create_session(project=project)
            as_admin.post('/sessions/' + session + '/files', files=file_form(INPUT_FILE))

            # Add acquisition
            acquisition = data_builder.create_acquisition(session=session)
            as_drone.post('/acquisitions/' + acquisition + '/files', files=file_form(INPUT_FILE))
            as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(EXTRA_FILE))

            # Run center-pays job
            center_job = data_builder.create_job(gear_id=center_gear, inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
            assert as_drone.get('/jobs/next', params={'root': 'true'}).ok
            r = as_drone.post('/engine',
                params={'root': 'true', 'level': 'acquisition', 'id': acquisition, 'job': center_job},
                files=file_form(OUTPUT_FILE, meta={'acquisition': {'files': [{'name': 'output.txt', 'type': 'text'}]}})
            )
            assert r.ok
            assert as_drone.put('/jobs/' + center_job, params={'root': 'true'}, json={'state': 'complete'}).ok

            r = as_admin.get('/acquisitions/' + acquisition)
            assert r.ok
            r_acq = r.json()
            assert len(r_acq['files']) == 3

            # Add analysis via job
            analysis = as_admin.post('/sessions/' + session + '/analyses', files=file_form(meta={'label': 'test'})).json()['_id']

            group_job = data_builder.create_job(gear_id=group_gear, inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
            assert as_drone.get('/jobs/next', params={'root': 'true'}).ok
            r = as_drone.post('/engine',
                params={'root': 'true', 'level': 'analysis', 'id': analysis, 'job': group_job},
                files=file_form(OUTPUT_FILE, meta={'type': 'text', 'value': {'label': 'test'}})
            )
            assert r.ok
            assert as_drone.put('/jobs/' + group_job, params={'root': 'true'}, json={'state': 'complete'}).ok

            # Set execution time for job (30 minutes)
            update_created('sessions', session, files=1)
            update_created('acquisitions', acquisition, files=3)
            update_created('analyses', analysis, files=1)
            update_job(center_job)
            update_job(group_job)

            return {
                'center_compute_ms': 30 * 60 * 1000,
                'center_job_count': 1,
                'center_storage_bytes': 2 * len(FILE_DATA),
                'group_compute_ms': 30 * 60 * 1000,
                'group_job_count': 1,
                'group_storage_bytes': 3 * len(FILE_DATA),
                'session_count': 1
            }

        expected = collections.OrderedDict()

        # Ensure file_job_origin is empty before starting
        api_db.file_job_origin.remove({})

        previous_day = None
        previous_month = None

        # We're collecting over 5 days and verifying the collection records
        for i in range(5):
            year = 2018
            day = 1 + ((28 + i) % 31)

            if day < 25:
                month = 11
            else:
                month = 10

            # Generate data
            day_stats = populate_day(year, month, day)

            date_key = (year, month, day)
            total_key = (year, month)

            expected[date_key] = day_stats
            total = expected.get(total_key)

            if previous_day:
                day_stats['center_storage_bytes'] += previous_day['center_storage_bytes']
                day_stats['group_storage_bytes'] += previous_day['group_storage_bytes']
                day_stats['session_count'] += previous_day['session_count']

            if not previous_month:
                previous_day = day_stats
            elif previous_month != month:
                previous_day = None

            # Collect usage data
            r = as_admin.get('/report/usage/collect?year={}&month={}&day={}'.format(year, month, day))
            assert r.ok

            if not total:
                total = day_stats.copy()
                total['days'] = 1
                expected[total_key] = total
            else:
                total['center_compute_ms'] += day_stats['center_compute_ms']
                total['group_compute_ms'] += day_stats['group_compute_ms']
                total['center_job_count'] += day_stats['center_job_count']
                total['group_job_count'] += day_stats['group_job_count']
                total['center_storage_bytes'] += day_stats['center_storage_bytes']
                total['group_storage_bytes'] += day_stats['group_storage_bytes']
                total['session_count'] = day_stats['session_count']
                total['days'] += 1

            # Verify collection of "today's" record
            record = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': year, 'month': month})
            assert record
            assert record['days'].get(str(day)) == day_stats
            total = total.copy()
            total['sessions'] = total.pop('session_count')
            assert record['total'] == total

        # Now, build the usage report

        # Then build the billing report


    finally:
        # Cleanup site
        if previous_site is not None:
            api_db.singletons.update({'_id': 'site'}, previous_site)
        else:
            api_db.singletons.remove({'_id': 'site'})

