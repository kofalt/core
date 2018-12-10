import datetime

from pymongo.operations import UpdateOne

from .report import Report
from .. import config
from ..auth import has_privilege, Privilege

from ..web.errors import APIReportParamsException
from ..jobs import file_job_origin

log = config.log

BULK_UPDATE_BLOCK_SIZE = 100
BYTES_IN_MEGABYTE = float(1<<20)
MILLISECONDS_IN_HOUR = float(1000 * 60 * 60)

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
            center_storage_bytes: The size of storage usage allocated to the center, in bytes
            group_storage_bytes: The size of storage usage allocated to the group, in bytes
            center_compute_ms: The amount of compute used attributed to the center, in seconds
            group_compute_ms: The amount of compute used attributed to the group, in seconds
        total: A usage total (to-date), same format as the day record, with additional:
            days: The number of days collated for this month

    NOTE: Storage is reported in byte days (i.e. how many bytes were in use for that day)
    """
    required_role = Privilege.is_admin
    can_collect = True
    columns = [
        'group', 'project_id', 'project_label', 'session_count',
        'center_job_count', 'group_job_count', 'total_job_count',
        'center_compute_hours', 'group_compute_hours', 'total_compute_hours',
        'center_storage_mb', 'group_storage_mb', 'total_storage_mb'
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

        now = datetime.datetime.now()

        # TODO: Use configured gear names
        self.center_gears = [ 'dicom-mr-classifier', 'dcm2niix', 'mriqc' ]

        try:
            year = int(params.get('year', str(now.year)))
            month = int(params.get('month', str(now.month)))
            day = int(params.get('day', str(now.day)))

            # Does validation
            self.date = datetime.datetime(year=year, month=month, day=day)
        except ValueError as e:
            raise APIReportParamsException('Invalid date specified: {}'.format(e))

    def user_can_generate(self, uid, roles):
        """
        User generating report must be site admin
        """
        has_privilege(roles, self.required_role)
        return True

    def build(self):
        # TODO: Implement
        return None

    def collect(self):
        """Collect daily usage data. NOTE: We deliberately include deleted collections/files"""
        # Set start and end dates. Jobs that completed between start & end will be included
        # Files and sessions created before end will be included
        start_date = self.date
        end_date = self.date + datetime.timedelta(days=1)

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
        for entry in self._get_session_counts(end_date):
            _id = entry['_id']
            report_entries[_id['project']]['session_count'] = entry['count']

        # Count files created in timeframe
        skipped = 0
        for coll_name in FILE_COLLECTIONS:
            yield { 'status': 'Getting {} storage usage...'.format(coll_name) }
            for entry in self._get_file_size_counts(coll_name, end_date):
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
        for entry in self._get_job_stats(start_date, end_date):
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
        year = self.date.year
        month = self.date.month
        day = self.date.day
        day_entry = 'day.{}'.format(day)
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
                'project': project,
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
                        day: row,
                        'total.sessions': row['session_count']
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
                config.db.bulk_write(bulk_updates, ordered=False)
                bulk_updates = []

            update_count += 1

        yield {'status': 'Complete'}

        # TODO: Set metric for last successful usage collection date
        # TODO: Set metric counter for usage collection failure

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
                '_id': {'project': 'project'},
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
        group_id['gear_name'] = '$job_origin.0.value.gear_info.name'
        group_id['gear_version'] = '$job_origin.0.value.gear_info.version'

        pipeline = [
            {'$unwind': '$files'},
            {'$match': file_q },
            {'$lookup': {
                'from': 'file_job_origin',
                'localField': 'origin.id',
                'foreignField': '_id',
                'as': 'job_origin'
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
            'parents': {'$exists': True},
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
                '_id': {'project': '$project', 'gear_name': '$gear_info.name', 'gear_version': '$gear_info.version'},
                'count': {'$sum': 1},
                'total_ms': {'$sum': '$profile.total_time_ms'},
            }}
        ]

        return config.db.jobs.aggregate(pipeline)

    @staticmethod
    def _default_record(group, project_id, project_label):
        return {
            'group': group,
            'project_id': project_id,
            'project_label': project_label,
            'session_count': 0,
            'center_job_count': 0,
            'group_job_count': 0,
            'center_storage_bytes': 0,
            'group_storage_bytes': 0,
            'center_compute_ms': 0,
            'group_compute_ms': 0,
        }
