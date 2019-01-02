import bson
import calendar
import collections
import csv
import datetime
import json

from StringIO import StringIO

FILE_DATA = 'a' * 1024
INPUT_FILE = ('input.txt', FILE_DATA)
EXTRA_FILE = ('extra.txt', FILE_DATA)
OUTPUT_FILE = ('output.txt', FILE_DATA)

def consistency_check(rec, expected):
    assert rec['days'] == expected['days']

    assert rec['session_count'] == expected['session_count']
    assert rec['center_compute_ms'] == expected['center_compute_ms']
    assert rec['group_compute_ms'] == expected['group_compute_ms']
    assert rec['center_job_count'] == expected['center_job_count']
    assert rec['group_job_count'] == expected['group_job_count']
    assert rec['center_storage_byte_day'] == expected['center_storage_bytes']
    assert rec['group_storage_byte_day'] == expected['group_storage_bytes']

    assert rec['total_job_count'] == rec['center_job_count'] + rec['group_job_count']
    assert rec['total_compute_ms'] == rec['center_compute_ms'] + rec['group_compute_ms']
    assert rec['total_storage_byte_day'] == rec['center_storage_byte_day'] + rec['group_storage_byte_day']

def update_created(db, ctype, cid, dt, files=0):
    """Update the creation date of the given container"""
    update = {'$set': {'created': dt}}
    for i in range(files):
        update['$set']['files.{}.created'.format(i)] = dt

    db[ctype].update({'_id': bson.ObjectId(cid)}, update)

def update_job(db, job_id, dt, duration=(30*60*1000)):
    """Update the completion date of the given job"""
    # Fake some numbers
    update = {'$set': {
        'created': dt,
        'modified': dt,
        'profile.total_time_ms': duration,
        'transitions.running': dt,
        'transitions.complete': dt
    }}
    db.jobs.update_one({'_id': bson.ObjectId(job_id)}, update)

def test_usage_report_parameters(as_admin):
    r = as_admin.get('/report/usage/collect?year&month')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=a&month=b')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?month=11')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018&month=11')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018&month=13')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018&month=0')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018&month=2&day=31')
    assert r.status_code == 400
    r = as_admin.get('/report/usage/collect?year=2018&month=2&day=0')
    assert r.status_code == 400

    r = as_admin.get('/report/usage?year=2018')
    assert r.status_code == 400
    r = as_admin.get('/report/usage?month=11')
    assert r.status_code == 400

    r = as_admin.get('/report/daily-usage?year=2018')
    assert r.status_code == 400
    r = as_admin.get('/report/daily-usage?month=1')
    assert r.status_code == 400

    # Today
    today = datetime.datetime.now()
    r = as_admin.get('/report/usage/collect?year={}&month={}&day={}'.format(today.year, today.month, today.day))
    assert r.status_code == 400

    # Future date and time
    tomorrow = today + datetime.timedelta(days=1)
    r = as_admin.get('/report/usage/collect?year={}&month={}&day={}'.format(tomorrow.year, tomorrow.month, tomorrow.day))
    assert r.status_code == 400

def test_usage_report_permissions(as_user, as_public):
    r = as_user.get('/report/usage/collect')
    assert r.status_code == 403
    r = as_public.get('/report/usage/collect')
    assert r.status_code == 403

    r = as_user.get('/report/usage?year=2018&month=10')
    assert r.status_code == 403
    r = as_public.get('/report/usage?year=2018&month=10')
    assert r.status_code == 403

    r = as_user.get('/report/daily-usage?year=2018&month=10')
    assert r.status_code == 403
    r = as_public.get('/report/daily-usage?year=2018&month=10')
    assert r.status_code == 403


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

    job = data_builder.create_job(gear_id=gear, tags=['usage'], inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
    assert as_drone.get('/jobs/next', params={'root': 'true', 'tags': 'usage'}).ok
    r = as_drone.post('/engine',
        params={'root': 'true', 'level': 'analysis', 'id': analysis, 'job': job},
        files=file_form(OUTPUT_FILE, meta={'type': 'text', 'value': {'label': 'test'}})
    )
    assert r.ok
    assert as_drone.put('/jobs/' + job, params={'root': 'true'}, json={'state': 'complete'}).ok

    # Set execution time for job (30 minutes)
    result = api_db.jobs.update({'_id': bson.ObjectId(job)}, {'$set': {'profile.total_time_ms': 30 * 60 * 1000}})

    # Run default collection
    today = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday = today - datetime.timedelta(days=1)

    update_created(api_db, 'sessions', session, today)
    update_created(api_db, 'acquisitions', acquisition, today, files=1)
    update_created(api_db, 'analyses', analysis, today, files=1)
    update_job(api_db, job, today)
    r = as_admin.get('/report/usage/collect?year={}&month={}&day={}'.format(yesterday.year, yesterday.month, yesterday.day))

    status = []
    for line in r.iter_lines():
        if line.strip().startswith('data: '):
            status.append(json.loads(line.strip()[6:]))

    assert r.ok
    assert status[-1]['status'] == 'Complete'

    # Yesterday's
    record = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': yesterday.year, 'month': yesterday.month})
    day = str(yesterday.day)
    assert day in record['days']

    assert record['project_label'] == 'usage'
    assert record['days'][day]['center_compute_ms'] == 0
    assert record['days'][day]['center_job_count'] == 0
    assert record['days'][day]['center_storage_bytes'] == 0
    assert record['days'][day]['group_compute_ms'] == 0
    assert record['days'][day]['group_job_count'] == 0
    assert record['days'][day]['group_storage_bytes'] == 0
    assert record['days'][day]['session_count'] == 0
    assert record['total']['center_compute_ms'] == 0
    assert record['total']['center_job_count'] == 0
    assert record['total']['center_storage_bytes'] == 0
    assert record['total']['group_compute_ms'] == 0
    assert record['total']['group_job_count'] == 0
    assert record['total']['group_storage_bytes'] == 0
    assert record['total']['session_count'] == 0

    # Verify collection of "today's" record
    r = as_admin.get('/report/usage/collect')
    assert r.ok

    record = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': today.year, 'month': today.month})
    assert record

    day = str(today.day)
    assert day in record['days']

    if today.month == yesterday.month:
        expected_days = 2
    else:
        expected_days = 1

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
    assert record['total']['session_count'] == 1
    assert record['total']['days'] == expected_days

    # Verify that re-collection after creating new data in the day does not update
    # (i.e. once a day has been collected, it's a no-op to collect that day again)

    as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(EXTRA_FILE))
    r = as_admin.get('/report/usage/collect')
    assert r.ok

    record2 = api_db.usage_data.find_one({'group': group, 'project': bson.ObjectId(project), 'year': today.year, 'month': today.month})
    assert record == record2

    # Get yesterday's daily usage, by project
    r = as_admin.get('/report/daily-usage?group={}&project={}&year={}&month={}'.format(group, project, yesterday.year, yesterday.month))
    assert r.ok
    rows = r.json()

    row = next((row for row in r.json() if row['day'] == yesterday.day), None)
    assert row is not None

    assert row['year'] == yesterday.year
    assert row['month'] == yesterday.month
    assert row['day'] == yesterday.day
    assert row['group'] == group
    assert row['project'] == project
    assert row['project_label'] == 'usage'
    assert row['center_compute_ms'] == 0
    assert row['center_job_count'] == 0
    assert row['center_storage_bytes'] == 0
    assert row['group_compute_ms'] == 0
    assert row['group_job_count'] == 0
    assert row['group_storage_bytes'] == 0
    assert row['session_count'] == 0

    # Get yesterday's daily usage, by project
    r = as_admin.get('/report/daily-usage?group={}&project={}&year={}&month={}'.format(group, project, today.year, today.month))
    assert r.ok
    rows = r.json()

    row = next((row for row in r.json() if row['day'] == today.day), None)

    assert row is not None
    assert row['year'] == today.year
    assert row['month'] == today.month
    assert row['day'] == today.day
    assert row['group'] == group
    assert row['project'] == project
    assert row['project_label'] == 'usage'
    assert row['center_compute_ms'] == 0
    assert row['center_job_count'] == 0
    assert row['center_storage_bytes'] == 0
    assert row['group_compute_ms'] == 30 * 60 * 1000
    assert row['group_job_count'] == 1
    assert row['group_storage_bytes'] == 2 * len(FILE_DATA)
    assert row['session_count'] == 1


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


            # Add session
            session = data_builder.create_session(project=project)
            as_admin.post('/sessions/' + session + '/files', files=file_form(INPUT_FILE))

            # Add acquisition
            acquisition = data_builder.create_acquisition(session=session)
            as_drone.post('/acquisitions/' + acquisition + '/files', files=file_form(INPUT_FILE))
            as_admin.post('/acquisitions/' + acquisition + '/files', files=file_form(EXTRA_FILE))

            # Run center-pays job
            center_job = data_builder.create_job(gear_id=center_gear, tags=['usage'], inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
            assert as_drone.get('/jobs/next', params={'root': 'true', 'tags': 'usage'}).ok
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

            group_job = data_builder.create_job(gear_id=group_gear, tags=['usage'], inputs={'usage': {'type': 'acquisition', 'id': acquisition, 'name': 'input.txt'}})
            assert as_drone.get('/jobs/next', params={'root': 'true', 'tags': 'usage'}).ok
            r = as_drone.post('/engine',
                params={'root': 'true', 'level': 'analysis', 'id': analysis, 'job': group_job},
                files=file_form(OUTPUT_FILE, meta={'type': 'text', 'value': {'label': 'test'}})
            )
            assert r.ok
            assert as_drone.put('/jobs/' + group_job, params={'root': 'true'}, json={'state': 'complete'}).ok

            # Set execution time for job (30 minutes)
            update_created(api_db, 'sessions', session, dt, files=1)
            update_created(api_db, 'acquisitions', acquisition, dt, files=3)
            update_created(api_db, 'analyses', analysis, dt, files=1)
            update_job(api_db, center_job, dt)
            update_job(api_db, group_job, dt)

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

        previous_day = None
        previous_month = None
        year = 2018

        # We're collecting over 5 days and verifying the collection records
        for i in range(5):
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
            assert record['total'] == total

        # Run the usage report for both months
        for month in [10, 11]:
            r = as_admin.get('/report/usage?year={}&month={}'.format(year, month))
            assert r.ok

            report = [row for row in r.json() if row['group'] == group]
            assert len(report) == 2

            expected_rec = expected[(year, month)]

            assert report[0]['group'] == group
            assert report[0]['project'] == None
            assert report[0]['project_label'] == None
            consistency_check(report[0], expected_rec)

            assert report[1]['group'] == group
            assert report[1]['project'] == project
            assert report[1]['project_label'] == 'usage'
            consistency_check(report[1], expected_rec)

        # Collect daily usage report for october
        r = as_admin.get('/report/daily-usage?year={}&month=10&csv=true'.format(year, group))
        assert r.ok

        body = StringIO(r.text)
        rows = [row for row in csv.DictReader(body) if row['group'] == group]
        assert len(rows) == 3

        for i, day in enumerate([29, 30, 31]):
            row = rows[i]
            expected_row = expected[(year, 10, day)]

            assert row['year'] == str(year)
            assert row['month'] == '10'
            assert row['day'] == str(day)
            assert row['group'] == group
            assert row['project'] == project
            assert row['project_label'] == 'usage'

            assert int(row['session_count']) == expected_row['session_count']
            assert int(row['center_job_count']) == expected_row['center_job_count']
            assert int(row['group_job_count']) == expected_row['group_job_count']
            assert int(row['center_compute_ms']) == expected_row['center_compute_ms']
            assert int(row['group_compute_ms']) == expected_row['group_compute_ms']
            assert int(row['center_storage_bytes']) == expected_row['center_storage_bytes']
            assert int(row['group_storage_bytes']) == expected_row['group_storage_bytes']

    finally:
        # Cleanup site
        if previous_site is not None:
            api_db.singletons.update({'_id': 'site'}, previous_site)
        else:
            api_db.singletons.remove({'_id': 'site'})
