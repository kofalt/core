import collections

import dateutil

from .report import Report

from .. import config
from ..dao.basecontainerstorage import ContainerStorage
from ..web.errors import APIReportParamsException

log = config.log

BYTES_IN_MEGABYTE = float(1<<20)
MILLISECONDS_IN_HOUR = float(1000 * 60 * 60)

# Tuple of collection name, file size key
FILE_COLLECTIONS = [
    ('projects', 'data_storage_bytes'),
    ('subjects', 'data_storage_bytes'),
    ('sessions', 'data_storage_bytes'),
    ('acquisitions', 'data_storage_bytes'),
    ('analyses', 'analysis_storage_bytes')
]

class ExtendedUsageReport(Report):
    """
    Creates a site usage report, aggregated by group and project.

    Specify a date range to only return stats for that range.

    Report includes:
        - Count of sessions
        - Count of complete jobs, grouped by data/analysis
        - Aggregation of gear execution time in hours, grouped by data/analysis
        - Aggregation of total storage size in megabytes, grouped by data/analysis
    """
    columns = [
        'group', 'project_id', 'project_label', 'session_count',
        'data_job_count', 'analysis_job_count', 'total_job_count',
        'data_compute_hours', 'analysis_compute_hours', 'total_compute_hours',
        'data_storage_mb', 'analysis_storage_mb', 'total_storage_mb'
    ]

    def __init__(self, params):
        """
        Initialize a Usage Report

        Possible keys in :params:
        :start_date:    ISO formatted timestamp
        :end_date:      ISO formatted timestamp
        """
        super(ExtendedUsageReport, self).__init__(params)

        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if start_date:
            start_date = dateutil.parser.parse(start_date)
        if end_date:
            end_date = dateutil.parser.parse(end_date)
        if end_date and start_date and end_date < start_date:
            raise APIReportParamsException('End date {} is before start date {}'.format(end_date, start_date))

        self.start_date = start_date
        self.end_date = end_date

    def user_can_generate(self, uid):
        """
        User generating report must be superuser
        """
        if config.db.users.count({'_id': uid, 'root': True}) > 0:
            return True
        return False

    def build(self):
        # Setup date clause
        date_query = {}
        if self.start_date:
            date_query['$gte'] = self.start_date
        if self.end_date:
            date_query['$lte'] = self.end_date

        return self._build_project_report(date_query)

    def _build_project_report(self, date_query):
        # Report data is keyed by project_id or group
        report_data = collections.OrderedDict()

        # Get a sorted list (by group/project label) from mongo
        project_storage = ContainerStorage.factory('projects')
        projects = project_storage.get_all_el(None, None, {'group': True, 'label': True}, sort=[('group', 1), ('label', 1)])

        # Create empty records for groups & projects
        for project in projects:
            project_id = project['_id']
            group = project['group']

            # Group rollup record
            if group not in report_data:
                report_data[group] = self._default_record(group, '', '')

            # Project record
            report_data[project_id] = self._default_record(group, project_id, project['label'])

        # Count sessions created in timeframe, returns cursor
        for entry in self._get_session_counts(date_query):
            _id = entry['_id']

            report_data[_id['group']]['session_count'] += entry['count']
            report_data[_id['project']]['session_count'] = entry['count']

        # Count files created in timeframe
        skipped = 0

        for coll_name, key in FILE_COLLECTIONS:
            for entry in self._get_file_size_counts(coll_name, date_query):
                _id = entry['_id']
                size = entry['bytes']

                # Safety check
                if 'group' not in _id or 'project' not in _id:
                    skipped += 1
                    continue

                group_rec = report_data.get(_id['group'])
                if group_rec:
                    group_rec[key] += size
                    group_rec['total_storage_bytes'] += size

                project_rec = report_data.get(_id['project'])
                if project_rec:
                    project_rec[key] += size
                    project_rec['total_storage_bytes'] += size

        if skipped:
            log.warn('Skipped %d records because of invalid keys', skipped)

        # Aggregate jobs counts run with execution time (in minutes) in timeframe
        for entry in self._get_job_stats(date_query):
            _id = entry['_id']

            total_count = entry['total_count']
            analysis_count = entry['analysis_count']
            data_count = total_count - analysis_count

            total_ms = entry['total_ms']
            analysis_ms = entry['analysis_ms']
            data_ms = total_ms - analysis_ms

            group_rec = report_data.get(_id['group'])
            if group_rec:
                group_rec['data_job_count'] += data_count
                group_rec['analysis_job_count'] += analysis_count
                group_rec['total_job_count'] += total_count

                group_rec['data_compute_ms'] += data_ms
                group_rec['analysis_compute_ms'] += analysis_ms
                group_rec['total_compute_ms'] += total_ms

            project_rec = report_data.get(_id['project'])
            if project_rec:
                project_rec['data_job_count'] = data_count
                project_rec['analysis_job_count'] = analysis_count
                project_rec['total_job_count'] = total_count

                project_rec['data_compute_ms'] = data_ms
                project_rec['analysis_compute_ms'] = analysis_ms
                project_rec['total_compute_ms'] = total_ms


        # Yield each entry after performing unit conversions
        result = []
        for row in report_data.itervalues():
            # Convert ms to hours
            row['data_compute_hours'] = row.pop('analysis_compute_ms') / MILLISECONDS_IN_HOUR
            row['analysis_compute_hours'] = row.pop('data_compute_ms') / MILLISECONDS_IN_HOUR
            row['total_compute_hours'] = row.pop('total_compute_ms') / MILLISECONDS_IN_HOUR

            # Convert bytes to megabytes
            row['data_storage_mb'] = row.pop('data_storage_bytes') / BYTES_IN_MEGABYTE
            row['analysis_storage_mb'] = row.pop('analysis_storage_bytes') / BYTES_IN_MEGABYTE
            row['total_storage_mb'] = row.pop('total_storage_bytes') / BYTES_IN_MEGABYTE

            result.append(row)

        return result

    def _get_session_counts(self, date_query):
        """
        Get count of sessions created within date_query.
        Grouped by (group, project_id)
        """
        session_query = {'deleted': {'$exists': False}}
        if date_query:
            session_query['created'] = date_query

        # Aggregation query
        pipeline = [
            {'$match': session_query},
            {'$group': {
                '_id': {'group': '$parents.group', 'project': '$parents.project'},
                'count': {'$sum': 1}
            }}
        ]

        return config.db.sessions.aggregate(pipeline)

    def _get_file_size_counts(self, coll_name, date_query):
        """
        Get total non-deleted file size in bytes, for files created in date_query.
        Grouped by (group, project_id)
        """
        file_q = {'files.deleted': {'$exists': False}}
        if date_query:
            file_q['files.created'] = date_query

        if coll_name == 'projects':
            group_id = {'group': '$group', 'project': '$_id'}
        else:
            group_id = {'group': '$parents.group', 'project': '$parents.project'}

        pipeline = [
            {'$match': {'deleted': {'$exists': False}}},
            {'$unwind': '$files'},
            {'$match': file_q },
            {'$group': {
                '_id': group_id,
                'bytes': {'$sum': '$files.size'}
            }}
        ]

        return config.db[coll_name].aggregate(pipeline)


    def _get_job_stats(self, date_query):
        """
        Get count and runtime duration of jobs created within date_query.
        Grouped by (group, project_id) and further separated by analysis
        """
        # Note: We require the "new" job records in order to aggregate them
        match = {
            'group': {'$exists': True},
            'project': {'$exists': True},
            'state': {'$in': ['complete', 'failed', 'cancelled']}
        }

        if date_query:
            # Completion timestamp within our date range
            match['$or'] = [
                {'transitions.complete': date_query},
                {'transitions.cancelled': date_query},
                {'transitions.failed': date_query}
            ]

        pipeline = [
            {'$match': match},
            {'$group': {
                '_id': {'group': '$group', 'project': '$project'},
                'total_count': {'$sum': 1},
                'analysis_count': {'$sum': {'$cond': [{'$eq': ['$destination.type', 'analysis']}, 1, 0]}},
                'total_ms': {'$sum': '$profile.total_time_ms'},
                'analysis_ms': {'$sum': {'$cond': [{'$eq': ['$destination.type', 'analysis']}, '$profile.total_time_ms', 0]}}
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
            'data_job_count': 0,
            'analysis_job_count': 0,
            'total_job_count': 0,
            'data_compute_ms': 0,
            'analysis_compute_ms': 0,
            'total_compute_ms': 0,
            'data_storage_bytes': 0,
            'analysis_storage_bytes': 0,
            'total_storage_bytes': 0
        }