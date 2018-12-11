import bson
import datetime

from pymongo.operations import UpdateOne
from pymongo.errors import BulkWriteError

from .report import Report
from .. import config
from ..auth import has_privilege, Privilege

from ..web.errors import APIReportParamsException
from ..jobs import file_job_origin

log = config.log

BULK_UPDATE_BLOCK_SIZE = 100

# Tuple of collection name, file size key
FILE_COLLECTIONS = ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses']

class UsageReport(Report):
    """
    Creates a site usage report, aggregated by group and project.

    Specify a year/month to get a report for that time period.

    Report includes:
        - Count of sessions
        - Count of complete jobs, grouped by data/analysis
        - Aggregation of gear execution time in hours, grouped by center/group
        - Aggregation of total storage size in megabytes, grouped by center/group

    Collection is done nightly, and stored in the usage_data database collection, using the below structure:
        group: The group id
        project: The project id
        project_label: The project label (at last collection)
        year: The collection year
        month: The collection month
        days: A map of day_of_month to collection record for that date, as follows:
            session_count: The number of sessions that exist at time of collection
            center_job_count: The number of jobs ran attributed to the center
            group_job_count: The number of jobs ran attributed to the group
            center_storage_bytes: The size of storage usage allocated to the center, in byte-days
            group_storage_bytes: The size of storage usage allocated to the group, in byte-days
            center_compute_ms: The amount of compute used attributed to the center, in seconds
            group_compute_ms: The amount of compute used attributed to the group, in seconds
        total: A usage total (to-date), same format as the day record, with additional:
            days: The number of days collated for this month

    NOTE: Storage is reported in byte days (i.e. how many bytes were in use for that day)
    """
    required_role = Privilege.is_admin
    can_collect = True
    columns = [
        'group', 'project', 'project_label', 'session_count',
        'center_job_count', 'group_job_count', 'total_job_count',
        'center_compute_ms', 'group_compute_ms', 'total_compute_ms',
        'center_storage_byte_day', 'group_storage_byte_day', 'total_storage_byte_day',
        'days'
    ]

    def __init__(self, params):
        """
        Initialize a Usage Report

        Possible keys in :params:
        :year:      The 4-digit requested report year
        :month:     The 1-indexed requested report month
        :day:       The day of the month (used for collection only)
        """
        super(UsageReport, self).__init__(params)

        self._center_gears = None

        try:
            # Get date parameters, validating ints
            if 'year' in params:
                self.year = int(params['year'])
            else:
                self.year = None

            if 'month' in params:
                self.month = int(params['month'])
            else:
                self.month = None

            if 'day' in params:
                self.day = int(params['day'])
            else:
                self.day = None
        except (TypeError, ValueError) as e:
            raise APIReportParamsException('Invalid date specified: {}'.format(e))

    @property
    def center_gears(self):
        # TODO: Use configured gear names
        if self._center_gears is None:
            record = config.db.singletons.find_one({'_id': 'site'})
            if record and record['center_gears']:
                self._center_gears = record['center_gears']

        if self._center_gears is None:
            self._center_gears = [ 'dicom-mr-classifier', 'dcm2niix', 'mriqc' ]

        return self._center_gears

    def user_can_generate(self, uid):
        """
        User generating report must be site admin
        """
        has_privilege(roles, self.required_role)
        return True

    def build(self):
        # Take year, month (or current year month)
        if self.year or self.month:
            # Require both values be set
            if not self.year or not self.month:
                raise APIReportParamsException('Must specify both year and month')
        else:
            now = datetime.datetime.now()
            self.year = now.year
            self.month = now.month

        # Generate report on current year/month
        query = {'year': self.year, 'month': self.month}
        # Remove unwanted fields via projection
        projection = {'_id': 0, 'year': 0, 'month': 0, 'days': 0}
        sort = [('group', 1), ('project_label', 1)]

        records = [] # Sequential list of records
        group_record = {} # Current group record

        # Run the query, project just totals
        for row in config.db.usage_data.find(query, projection, sort=sort):
            group = row['group']

            if group_record and group_record['group'] != group:
                # Total the prior group record
                self._total_record(group_record)
                group_record = None

            if not group_record:
                # Create group roll-up record
                group_record = self._default_record(group, None, None)
                records.append(group_record)

            # Produce the project record by flattening the total record, and removing/adjusting fields
            row.update(row.pop('total'))

            # Sum group record
            self._sum_records(row, group_record)

            # Total the project record
            self._total_record(row)
            records.append(row)

        # Total the remaining group record
        if group_record:
            self._total_record(group_record)

        return records

    def before_collect(self):
        # Set start and end dates. Jobs that completed between start & end will be included
        # Files and sessions created before end will be included
        try:
            if self.year or self.month or self.day:
                self.start_date = datetime.datetime(year=self.year, month=self.month, day=self.day)
            else:
                now = datetime.datetime.now()
                self.start_date = datetime.datetime(year=now.year, month=now.month, day=now.day) -  datetime.timedelta(days=1)
        except (TypeError, ValueError) as e:
            raise APIReportParamsException('Invalid date specified: {}'.format(e))

        self.end_date = self.start_date + datetime.timedelta(days=1)

    def collect(self):
        """Collect daily usage data. NOTE: We deliberately include deleted collections/files"""
        # First update the file_job_origin collection, for joins
        yield { 'status': 'Updating file_job_origin collection' }
        file_job_origin.update_file_job_origin()

        # Create empty record for each project
        report_entries = {}
        yield { 'status': 'Initializing collection...' }
        for project in config.db.projects.find({}, {'group': True, 'label': True}):
            project_id = project['_id']
            report_entries[project_id] = self._default_record(project['group'], project_id, project['label'])

        # Count sessions created in timeframe, returns cursor
        yield { 'status': 'Getting session counts...' }
        for entry in self._get_session_counts(self.end_date):
            _id = entry['_id']
            report_entries[_id['project']]['session_count'] = entry['count']

        # Count files created in timeframe
        skipped = 0
        for coll_name in FILE_COLLECTIONS:
            yield { 'status': 'Getting {} storage usage...'.format(coll_name) }
            for entry in self._get_file_size_counts(coll_name, self.end_date):
                _id = entry['_id']
                size = entry['bytes']

                # Safety check
                if 'project' not in _id:
                    skipped +=1
                    continue

                project_rec = report_entries.get(_id['project'])
                if project_rec:
                    # if origin is device, then bill to center
                    if _id.get('origin') == 'device' or self._is_center_gear(_id):
                        key = 'center_storage_bytes'
                    else:
                        key = 'group_storage_bytes'

                    project_rec[key] += size

        if skipped:
            log.warn('Skipped %d records because of invalid keys', skipped)

        # Aggregate jobs counts run with execution time (in milliseconds) in timeframe
        yield { 'status': 'Getting compute usage...' }
        for entry in self._get_job_stats(self.start_date, self.end_date):
            _id = entry['_id']

            project_rec = report_entries.get(_id['project'])
            if project_rec:
                if self._is_center_gear(_id):
                    count_key = 'center_job_count'
                    time_key = 'center_compute_ms'
                else:
                    count_key = 'group_job_count'
                    time_key = 'group_compute_ms'

                project_rec[count_key] += entry['count']
                project_rec[time_key] += entry['total_ms']

        # Bulk updates
        update_count = 0
        record_count = len(report_entries)
        year = self.start_date.year
        month = self.start_date.month
        day = str(self.start_date.day)
        day_entry = 'days.{}'.format(day)
        bulk_updates = []

        for row in report_entries.itervalues():
            # Yield progress every time we empty out bulk_updates
            if not bulk_updates:
                yield {
                    'status': 'Updating records',
                    'progress': '{}/{}'.format(update_count, record_count)
                }

            group = row.pop('group')
            project = row.pop('project')
            project_label = row.pop('project_label')

            query = {
                'group': group,
                'project': bson.ObjectId(project),
                'year': year,
                'month': month,
                day_entry: {'$exists': False}
            }

            # Create the bulk update
            bulk_updates.append(UpdateOne(
                query,
                {
                    '$set': {
                        'project_label': project_label,
                        day_entry: row,
                        'total.session_count': row['session_count']
                    },
                    '$inc': {
                        'total.days': 1,
                        'total.center_job_count': row['center_job_count'],
                        'total.group_job_count': row['group_job_count'],
                        'total.center_storage_bytes': row['center_storage_bytes'],
                        'total.group_storage_bytes': row['group_storage_bytes'],
                        'total.center_compute_ms': row['center_compute_ms'],
                        'total.group_compute_ms': row['group_compute_ms'],
                    },
                    '$setOnInsert': {
                        'group': group,
                        'project':  project,
                        'year': year,
                        'month': month
                    }
                },
                upsert=True
            ))

            if len(bulk_updates) >= BULK_UPDATE_BLOCK_SIZE:
                # Do bulk update block
                self._batch_insert(bulk_updates)
                bulk_updates = []

            update_count += 1

        # Send final bulk update
        self._batch_insert(bulk_updates)

        yield {'status': 'Complete'}

    @staticmethod
    def _batch_insert(updates):
        if not updates:
            return

        conflicts = 0

        try:
            config.db.usage_data.bulk_write(updates, ordered=False)
        except BulkWriteError as e:
            for err in e.details.get('writeErrors', []) + e.details.get('writeConcernErrors', []):
                code = err.get('code', 0)
                if code == 11000:
                    conflicts += 1
                else:
                    config.log.error('usage-report collection insertion error: %d - %s',
                        code, err.get('errmsg', 'UNKNOWN ERROR'))

        if conflicts:
            config.log.warning('usage-report - %d entries not created due to conflicts', conflicts)


    def _is_center_gear(self, key): # pylint: disable=unused-argument
        """Check if the given key is a center gear.

        key is a dict, with 'gear_name' and 'gear_version' properties.
        """
        return key.get('gear_name') in self.center_gears

    @staticmethod
    def _get_session_counts(end_date):
        """
        Get count of sessions created within date_query.
        Grouped by project_id
        """
        # Aggregation query
        pipeline = [
            {'$match': {
                'created': {'$lt': end_date}
            }},
            {'$group': {
                '_id': {'project': '$project'},
                'count': {'$sum': 1}
            }}
        ]

        return config.db.sessions.aggregate(pipeline)

    @staticmethod
    def _get_file_size_counts(coll_name, end_date):
        """
        Get total file size in bytes, for files created before end_date
        Grouped by project_id, origin, gear_name and gear_version
        """
        file_q = {'files.created': {'$lt': end_date}}

        if coll_name == 'projects':
            group_id = {'project': '$_id'}
        else:
            group_id = {'project': '$parents.project'}

        group_id['origin'] = '$files.origin.type'
        group_id['gear_name'] = '$job_origin.value.gear_info.name'
        group_id['gear_version'] = '$job_origin.value.gear_info.version'

        pipeline = [
            {'$unwind': '$files'},
            {'$match': file_q },
            {'$lookup': {
                'from': 'file_job_origin',
                'localField': 'files.origin.id',
                'foreignField': '_id',
                'as': 'job_origin'
            }},
            {'$unwind': {
                'path': '$job_origin',
                'preserveNullAndEmptyArrays': True
            }},
            {'$group': {
                '_id': group_id,
                'bytes': {'$sum': '$files.size'}
            }}
        ]

        return config.db[coll_name].aggregate(pipeline)

    @staticmethod
    def _get_job_stats(start_date, end_date):
        """
        Get count and runtime duration of jobs created within date_query.
        Grouped by project_id, gear_name and gear_version
        """
        # Note: We require the "new" job records in order to aggregate them
        date_query = { '$gte': start_date, '$lt': end_date }

        # Query for jobs that completed in the time window
        match = {
            'parents.project': {'$exists': True},
            'state': {'$in': ['complete', 'failed', 'cancelled']},
            '$or': [
                {'transitions.complete': date_query},
                {'transitions.cancelled': date_query},
                {'transitions.failed': date_query}
            ]
        }

        pipeline = [
            {'$match': match},
            {'$group': {
                '_id': {'project': '$parents.project', 'gear_name': '$gear_info.name', 'gear_version': '$gear_info.version'},
                'count': {'$sum': 1},
                'total_ms': {'$sum': '$profile.total_time_ms'},
            }}
        ]

        return config.db.jobs.aggregate(pipeline)

    @staticmethod
    def _default_record(group, project_id, project_label):
        return {
            'group': group,
            'project': project_id,
            'project_label': project_label,
            'session_count': 0,
            'center_job_count': 0,
            'group_job_count': 0,
            'center_storage_bytes': 0,
            'group_storage_bytes': 0,
            'center_compute_ms': 0,
            'group_compute_ms': 0,
        }

    @staticmethod
    def _sum_records(src, dst):
        dst['center_job_count'] += src['center_job_count']
        dst['group_job_count'] += src['group_job_count']
        dst['center_storage_bytes'] += src['center_storage_bytes']
        dst['group_storage_bytes'] += src['group_storage_bytes']
        dst['center_compute_ms'] += src['center_compute_ms']
        dst['group_compute_ms'] += src['group_compute_ms']
        dst['session_count'] += src['session_count']
        dst['days'] = max(src.get('days', 0), dst.get('days', 0))

    @staticmethod
    def _total_record(record):
        record['center_storage_byte_day'] = record.pop('center_storage_bytes')
        record['group_storage_byte_day'] = record.pop('group_storage_bytes')
        record['total_job_count'] = record['center_job_count'] + record['group_job_count']
        record['total_storage_byte_day'] = record['center_storage_byte_day'] + record['group_storage_byte_day']
        record['total_compute_ms'] = record['center_compute_ms'] + record['group_compute_ms']
