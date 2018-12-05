import copy
import datetime
import dateutil

from .report import Report

from .. import config

from ..web.errors import APIReportException, APIReportParamsException


BYTES_IN_MEGABYTE = float(1<<20)


class UsageReport(Report):
    """
    Creates a usage report, aggregated by month or project.

    Specify a date range to only return stats for that range.

    Report includes:
      - count of gears executed (jobs completed successfully)
      - count of sessions
      - aggregation of file size in megabytes
    """

    def __init__(self, params):
        """
        Initialize a Usage Report

        Possible keys in :params:
        :start_date:    ISO formatted timestamp
        :end_date:      ISO formatted timestamp
        :type:          <'project'|'month'>, type of aggregation for results
        """

        super(UsageReport, self).__init__(params)

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        report_type = params.get('type')

        if not report_type or report_type not in ['month', 'project']:
            raise APIReportParamsException('Report type must be "month" or "project".')

        if start_date:
            start_date = dateutil.parser.parse(start_date)
        if end_date:
            end_date = dateutil.parser.parse(end_date)
        if end_date and start_date and end_date < start_date:
            raise APIReportParamsException('End date {} is before start date {}'.format(end_date, start_date))

        self.start_date  = start_date
        self.end_date    = end_date
        self.report_type = report_type

        # Used for month calculation:
        self.first_month = start_date
        self.last_month = end_date


    def user_can_generate(self, uid):
        """
        User generating report must be superuser
        """
        if config.db.users.count({'_id': uid, 'root': True}) > 0:
            return True
        return False


    def build(self):
        query = {}

        if self.start_date or self.end_date:
            query['created'] = {}
        if self.start_date:
            query['created']['$gte'] = self.start_date
        if self.end_date:
            query['created']['$lte'] = self.end_date

        if self.report_type == 'project':
            return self._build_project_report(query)
        else:
            return self._build_month_report(query)

    def _create_default(self, month=None, year=None, project=None, ignore_minmax=False):
        """
        Returns a zerod out usage report for month/project type usage reports

        If proveded with a month and year, adds info to the report as well as updates first and last seen months
        If provided with a project, adds id and label to the report
        """
        obj = {
            'gear_execution_count': 0,
            'file_mbs': 0,
            'session_count': 0
        }
        if month:
            obj['month'] = month
        if year:
            obj['year'] = year
        if project:
            obj['project'] = {'_id': project['_id'], 'label': project['label']}

        if month and year and not ignore_minmax:
            # update the first or last month if this is outside the known bounds
            date = dateutil.parser.parse(year+'-'+month+'-01T00:00.000Z')
            if self.first_month is None or date < self.first_month:
                self.first_month = date
            if self.last_month is None or date > self.last_month:
                self.last_month = date

        return obj

    def _build_month_report(self, base_query):
        """
        Builds a usage report for file size, session count and gear execution count
        Aggregates this information by month.

        Will return all months between the first_month and last_month, zero'd out if no
        data was created or jobs run in that time.
          - `first_month` is determined by the start_date of the query, if available, otherwise
            the earliest month with data/jobs
          - `last_month` is the end_date of the query or the last month with data/jobs

        Returns an ordered list of each month in the range `first_month` -> `last_month` with stats:
        {
            'month':                    <month_int>,
            'year':                     <year_int>,
            'gear_execution_count':     0,
            'session_count':            0,
            'file_mbs':                 0
        }
        """

        report = {}

        # Count jobs that completed successfully, by month
        job_q = copy.deepcopy(base_query)
        job_q['state'] = 'complete'

        pipeline = [
            {'$match': job_q},
            {'$project': {'month': {'$month': '$created'}, 'year': {'$year': '$created'}}},
            {'$group': {'_id': {'month': '$month', 'year': '$year'}, 'jobs_completed': {'$sum':1}}}
        ]

        try:
            results = self._get_result_list('jobs', pipeline)
        except APIReportException:
            results = []

        for r in results:
            month = str(r['_id']['month'])
            year = str(r['_id']['year'])
            key = year+month

            # Check to see if we already have a record for this month/year combo, create and update first/last if not
            if key not in report:
                report[key] = self._create_default(month=month, year=year)

            report[key]['gear_execution_count'] = r['jobs_completed']

        # Count sessions by month
        pipeline = [
            {'$match': base_query},
            {'$project': {'month': {'$month': '$created'}, 'year': {'$year': '$created'}}},
            {'$group': {'_id': {'month': '$month', 'year': '$year'}, 'session_count': {'$sum':1}}}
        ]

        try:
            results = self._get_result_list('sessions', pipeline)
        except APIReportException:
            results = []

        for r in results:
            month = str(r['_id']['month'])
            year = str(r['_id']['year'])
            key = year+month

            # Check to see if we already have a record for this month/year combo, create and update first/last if not
            if key not in report:
                report[key] = self._create_default(month=month, year=year)

            report[key]['session_count'] = r['session_count']

        file_q = {'deleted': {'$exists': False}}
        analysis_q = {'analyses.files.output': True}

        if 'created' in base_query:
            file_q['files.created'] = base_query['created']
            analysis_q['analyses.created'] = base_query['created']

        for cont_name in ['groups', 'projects', 'sessions', 'acquisitions']:
            # For each type of container that would contain files or analyses:

            # Count file mbs by month
            pipeline = [
                {'$unwind': '$files'},
                {'$match': file_q},
                {'$project': {'month': {'$month': '$files.created'}, 'year': {'$year': '$files.created'}, 'mbs': {'$divide': ['$files.size', BYTES_IN_MEGABYTE]}}},
                {'$group': {'_id': {'month': '$month', 'year': '$year'}, 'mb_total': {'$sum':'$mbs'}}}
            ]

            try:
                results = self._get_result_list(cont_name, pipeline)
            except APIReportException:
                results = []

            for r in results:
                month = str(r['_id']['month'])
                year = str(r['_id']['year'])
                key = year+month

                # Check to see if we already have a record for this month/year combo, create and update first/last if not
                if key not in report:
                    report[key] = self._create_default(month=month, year=year)

                report[key]['file_mbs'] += r['mb_total']

            # Count file mbs by month in analyses
            pipeline = [
                {'$unwind': '$analyses'},
                {'$unwind': '$analyses.files'},
                {'$match': analysis_q},
                {'$project': {'month': {'$month': '$analyses.created'}, 'year': {'$year': '$analyses.created'}, 'mbs': {'$divide': ['$analyses.files.size', BYTES_IN_MEGABYTE]}}},
                {'$group': {'_id': {'month': '$month', 'year': '$year'}, 'mb_total': {'$sum':'$mbs'}}}
            ]

            try:
                results = self._get_result_list(cont_name, pipeline)
            except APIReportException:
                results = []

            for r in results:
                month = str(r['_id']['month'])
                year = str(r['_id']['year'])
                key = year+month

                # Check to see if we already have a record for this month/year combo, create and update first/last if not
                if key not in report:
                    report[key] = self._create_default(month=month, year=year)

                report[key]['file_mbs'] += r['mb_total']


        # For each month between `first_month` and `last_month`:
        #  - add the month from the dictionary of report objects if it exists
        #  - OR create a zero'd out report object for the month

        # Set `first_month` and `last_month` to current month in case they weren't specified
        # AND there was no data in mongo to get defaults
        self.first_month = self.first_month or datetime.datetime.utcnow()
        self.last_month = self.last_month or self.first_month

        curr_month = self.first_month.month
        curr_year = self.first_month.year

        last_month = self.last_month.month
        last_year = self.last_month.year

        final_report_list = []

        # While we're not in the year of the last month we want to record OR we are and we haven't hit the last month yet:
        while curr_year < last_year or (curr_month <= last_month and curr_year == last_year):
            key = str(curr_year)+str(curr_month)
            if key in report:
                # We have a record for this month/year combo, add it to the report
                final_report_list.append(report[key])
            else:
                # We don't have a record for this month/year combo, create a zero'd out version
                final_report_list.append(self._create_default(month=str(curr_month), year=str(curr_year), ignore_minmax=True))
            curr_month += 1
            if curr_month > 12:
                curr_year += 1
                curr_month = 1

        # Return ordered list of report objects for each month in range
        return final_report_list


    def _build_project_report(self, base_query):
        """
        Builds a usage report for file size, session count and gear execution count
        Aggregates this information by project.

        Returns an unordered list of each project with stats:
        {
            'project': {
                '_id':      <project_id>,
                'label':    <project_label>
            },
            'gear_execution_count':     0,
            'session_count':            0,
            'file_mbs':                 0
        }
        """
        projects = config.db.projects.find({'deleted': {'$exists': False}})
        final_report_list = []

        for p in projects:
            report_obj = self._create_default(project=p)

            # Grab sessions and their ids
            sessions = config.db.sessions.find({'project': p['_id'], 'deleted': {'$exists': False}}, {'_id': 1})
            session_ids = [s['_id'] for s in sessions]

            # Grab acquisitions and their ids
            acquisitions = config.db.acquisitions.find({'session': {'$in': session_ids}, 'deleted': {'$exists': False}}, {'_id': 1})
            acquisition_ids = [a['_id'] for a in acquisitions]

            # For the project and each session and acquisition, create a list of analysis ids
            parent_ids = session_ids + acquisition_ids + [p['_id']]
            analysis_ids = [an['_id'] for an in config.db.analyses.find({'parent.id': {'$in': parent_ids}, 'deleted': {'$exists': False}})]

            report_obj['session_count'] = len(session_ids)

            # for each type of container below it will have a slightly modified match query
            cont_query = {
                'projects': {'_id': {'project': p['_id']}},
                'sessions': {'project': p['_id']},
                'acquisitions': {'session': {'$in': session_ids}},
                'analyses': {'parent.id' : {'$in':parent_ids}}
            }

            # Create queries for files and analyses based on created date if a range was provided
            file_q = {'deleted': {'$exists': False}}
            analysis_q = {'analyses.files.output': True}

            if 'created' in base_query:
                file_q['files.created'] = base_query['created']
                analysis_q['analyses.created'] = base_query['created']

            for cont_name in ['projects', 'sessions', 'acquisitions', 'analyses']:

                # Aggregate file size in megabytes
                pipeline = [
                    {'$match': cont_query[cont_name]},
                    {'$unwind': '$files'},
                    {'$match': file_q},
                    {'$project': {'mbs': {'$divide': [{'$cond': ['$files.input', 0, '$files.size']}, BYTES_IN_MEGABYTE]}}},
                    {'$group': {'_id': 1, 'mb_total': {'$sum':'$mbs'}}}
                ]

                try:
                    result = self._get_result(cont_name, pipeline)
                except APIReportException:
                    result = None

                if result:
                    report_obj['file_mbs'] += result['mb_total']

            # Create a list of all possible ids in this project hierarchy
            id_list = analysis_ids+acquisition_ids+session_ids
            id_list.append(p['_id'])

            # Look for all completed jobs that have a destination in the id
            job_query = copy.deepcopy(base_query)
            job_query['state'] = 'complete'
            job_query['destination.id'] = {'$in': [str(id_) for id_ in id_list]}

            report_obj['gear_execution_count'] = config.db.jobs.count(job_query)

            final_report_list.append(report_obj)

        return final_report_list
