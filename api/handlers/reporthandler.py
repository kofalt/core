import bson
import copy
import unicodecsv as csv
import datetime
import dateutil
import os
import pymongo
import pytz

from .. import config
from .. import tempdir as tempfile
from .. import util
from ..web import base

from ..web.errors import APIReportException, APIReportParamsException
from ..web.request import AccessTypeList


EIGHTEEN_YEARS_IN_SEC = 18 * 365.25 * 24 * 60 * 60
BYTES_IN_MEGABYTE = float(1<<20)
ACCESS_LOG_FIELDS = [
    "_id",
    "timestamp",
    "access_type",
    "origin.id",
    "origin.method",
    "origin.name",
    "origin.type",
    "origin.via.type",
    "origin.via.id",
    "context.group.id",
    "context.group.label",
    "context.project.id",
    "context.project.label",
    "context.subject.id",
    "context.subject.label",
    "context.session.id",
    "context.session.label",
    "context.acquisition.id",
    "context.acquisition.label",
    "context.analysis.id",
    "context.analysis.label",
    "context.collection.id",
    "context.collection.label",
    "context.ticket_id",
    "request_method",
    "request_path"
]

class ReportHandler(base.RequestHandler):

    def __init__(self, request=None, response=None):
        super(ReportHandler, self).__init__(request, response)

    def get_types(self):
        return AccessTypeList

    def get(self, report_type):

        report = None

        if report_type in ReportTypes:
            report_class = ReportTypes[report_type]
            try:
                report = report_class(self.request.params)
            except APIReportParamsException as e:
                self.abort(400, e.message)
        else:
            raise NotImplementedError('Report type {} is not supported'.format(report_type))

        if self.superuser_request or report.user_can_generate(self.uid):

            if self.is_true('csv'):
                tempdir = tempfile.TemporaryDirectory(prefix='.tmp', dir=config.get_item('persistent', 'data_path'))
                filepath = os.path.join(tempdir.name, report.csv_filename)

                report.build_csv(filepath)

                self.response.app_iter = open(filepath, 'r')
                self.response.headers['Content-Type'] = 'text/csv'
                self.response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(report.csv_filename)
            else:
                return report.build()
        else:
            self.abort(403, 'User {} does not have required permissions to generate report'.format(self.uid))


class Report(object):

    csv_filename = 'report.csv'

    def __init__(self, params):
        """
        Initialize a Report
        """

        super(Report, self).__init__()
        self.params = params

    def user_can_generate(self, uid):
        """
        Check if user has required permissions to generate report
        """
        raise NotImplementedError()

    def build(self):
        """
        Build and return a json report
        """
        raise NotImplementedError()

    def build_csv(self, filepath): # pylint: disable=unused-argument
        """
        Build and return a csv file of the report
        """
        raise APIReportParamsException('This report does not support csv file format.')


    @staticmethod
    def _get_result_list(output):
        """
        Helper function for extracting mongo aggregation results

        Given the output of a mongo aggregation call, checks 'ok' field
        If not 1.0, 'result' field does not exist or 'result' array is empty,
        throws APIReportException
        """

        if output.get('ok') == 1.0:
            result = output.get('result')
            if result is not None and len(result) > 0:
                return result

        raise APIReportException

    @staticmethod
    def _get_result(output):
        """
        Helper function for extracting a singular mongo aggregation result

        If more than one item is in the results array, throws APIReportException
        """

        results = Report._get_result_list(output)
        if len(results) == 1:
            return results[0]

        raise APIReportException



class SiteReport(Report):
    """
    Report of statistics about the site, generated by Site Managers

    Report includes:
      - number of groups
      - number of projects per group
      - number of sessions per group
    """

    def user_can_generate(self, uid):
        """
        User generating report must be superuser
        """
        if config.db.users.count({'_id': uid, 'root': True}) > 0:
            return True
        return False

    def build(self):
        report = {}

        groups = config.db.groups.find({})
        report['group_count'] = groups.count()
        report['groups'] = []

        for g in groups:
            group = {}
            group['label'] = g.get('label')

            project_ids = [p['_id'] for p in config.db.projects.find({'group': g['_id'], 'deleted': {'$exists': False}}, [])]
            group['project_count'] = len(project_ids)

            group['session_count'] = config.db.sessions.count({'project': {'$in': project_ids}, 'deleted': {'$exists': False}})
            report['groups'].append(group)

        return report


class ProjectReport(Report):
    """
    Report of statistics about a list of projects, generated by
    Project Admins or Group Admins. Will only include a sessions
    created in date range (inclusive) when provided by the client.

    Report includes:
      - Project Name
      - Group Name
      - Project Admin(s)
      - Number of Sessions
      - Unique Subjects
      - Male Subjects
      - Female Subjects
      - Other Subjects
      - Subjects with sex type Other
      - Demographics grid (Race/Ethnicity/Sex)
      - Subjects under 18
      - Subjects over 18
    """

    def __init__(self, params):
        """
        Initialize a Project Report

        Possible keys in :params:
        :projects:      a list of project ObjectIds
        :start_date:    ISO formatted timestamp
        :end_date:      ISO formatted timestamp
        """

        super(ProjectReport, self).__init__(params)

        project_list = params.getall('projects')
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if len(project_list) < 1:
            raise APIReportParamsException('List of projects requried for Project Report')
        if start_date:
            start_date = dateutil.parser.parse(start_date)
        if end_date:
            end_date = dateutil.parser.parse(end_date)
        if end_date and start_date and end_date < start_date:
            raise APIReportParamsException('End date {} is before start date {}'.format(end_date, start_date))

        self.projects = [bson.ObjectId(id_) for id_ in project_list]
        self.start_date = start_date
        self.end_date = end_date

    def user_can_generate(self, uid):
        """
        User generating report must be admin on all
        """

        perm_count = config.db.projects.count({'_id': {'$in': self.projects},
                                               'permissions._id': uid,
                                               'permissions.access': 'admin'})
        if perm_count == len(self.projects):
            return True
        return False

    def _base_query(self, pid):
        base_query = {'project': pid, 'deleted': {'$exists': False}}

        if self.start_date is not None or self.end_date is not None:
            base_query['created'] = {}
        if self.start_date is not None:
            base_query['created']['$gte'] = self.start_date
        if self.end_date is not None:
            base_query['created']['$lte'] = self.end_date

        return base_query

    def _base_demo_grid(self):
        """
        Constructs a base demographics grid for the project report
        """

        races = [
                    'American Indian or Alaska Native',
                    'Asian',
                    'Native Hawaiian or Other Pacific Islander',
                    'Black or African American',
                    'White',
                    'More Than One Race',
                    'Unknown or Not Reported'
        ]
        ethnicities = [
                    'Not Hispanic or Latino',
                    'Hispanic or Latino',
                    'Unknown or Not Reported'
        ]
        sexes = [
                    'Female',
                    'Male',
                    'Unknown or Not Reported'
        ]

        sexes_obj = dict([(s, 0) for s in sexes])
        eth_obj = dict([(e, copy.deepcopy(sexes_obj)) for e in ethnicities])
        eth_obj['Total'] = 0
        race_obj = dict([(r, copy.deepcopy(eth_obj)) for r in races])
        race_obj['Total'] = copy.deepcopy(eth_obj)

        return race_obj

    def _base_project_report(self):
        """
        Constructs a dictionary representation of the project report with neutral values
        """
        return {
                'name':                 '',
                'group_name':           '',
                'admins':               [],
                'session_count':        0,
                'subjects_count':       0,
                'female_count':         0,
                'male_count':           0,
                'other_count':          0,
                'demographics_grid':    self._base_demo_grid(),
                'demographics_total':   0,
                'over_18_count':        0,
                'under_18_count':       0
            }


    def _process_demo_results(self, results, grid):
        """
        Given demographics aggregation results, fill in base demographics grid

        All `null` or unlisted values will be counted as 'Unknown or Not Reported'
        """
        UNR = 'Unknown or Not Reported'
        total = 0

        for r in results:
            try:
                count = int(r['count'])
                cell = r['_id']
                race = cell['race']
                ethnicity = cell['ethnicity']
                sex = cell['sex']
            except Exception as e:
                raise APIReportException('Demographics aggregation was malformed: {}'.format(e))

            # Null or unrecognized values are listed as UNR default
            if race is None or race not in grid:
                race = UNR
            if ethnicity is None or ethnicity not in grid[race]:
                ethnicity = UNR
            if sex is None:
                sex = UNR
            else:
                sex = sex.capitalize() # We store sex as lowercase in the db
            if sex not in grid[race][ethnicity]:
                sex = UNR

            # Tally up
            total += count
            grid[race]['Total'] += count
            grid[race][ethnicity][sex] += count
            grid['Total'][ethnicity][sex] += count

        return grid, total


    def build(self):
        report = {}
        report['projects'] = []

        projects = config.db.projects.find({'_id': {'$in': self.projects}, 'deleted': {'$exists': False}})
        for p in projects:
            project = self._base_project_report()
            project['name'] = p.get('label')
            project['group_name'] = p.get('group')

            # Create list of project admins
            admins = []
            for perm in p.get('permissions', []):
                if perm.get('access') == 'admin':
                    admins.append(perm.get('_id'))
            admin_objs = config.db.users.find({'_id': {'$in': admins}})
            project['admins'] = map(lambda x: x.get('firstname','')+' '+x.get('lastname',''), admin_objs) # pylint: disable=bad-builtin, deprecated-lambda

            base_query = self._base_query(p['_id'])
            project['session_count'] = config.db.sessions.count(base_query)

            # If there are no sessions in this project for the date range,
            # no need to continue grabbing more stats
            if project['session_count'] == 0:
                report['projects'].append(project)
                continue

            # Count subjects
            # Any stats on subjects require an aggregation to group by subject._id
            subject_q = copy.deepcopy(base_query)
            subject_q['subject._id'] = {'$ne': None}

            pipeline = [
                {'$match': subject_q},
                {'$group': {'_id': '$subject._id'}},
                {'$group': {'_id': 1, 'count': { '$sum': 1 }}}
            ]

            result = self._get_result(config.db.command('aggregate', 'sessions', pipeline=pipeline))
            project['subjects_count'] = result.get('count', 0)

            # Count subjects by sex
            # Use last sex reporting for subjects with multiple entries
            sex_q = copy.deepcopy(subject_q)
            sex_q['subject.sex'] = {'$ne': None}

            pipeline = [
                {'$match': sex_q},
                {'$group': {'_id': '$subject._id', 'sex': {'$last': '$subject.sex'}}},
                {'$project': {'_id': 1, 'female':  {'$cond': [{'$eq': ['$sex', 'female']}, 1, 0]},
                                        'male':    {'$cond': [{'$eq': ['$sex', 'male']}, 1, 0]},
                                        'other':   {'$cond': [{'$eq': ['$sex', 'other']}, 1, 0]}}},
                {'$group': {'_id': 1, 'female': {'$sum': '$female'},
                                      'male':   {'$sum': '$male'},
                                      'other':  {'$sum': '$other'}}}
            ]
            try:
                result = self._get_result(config.db.command('aggregate', 'sessions', pipeline=pipeline))
            except APIReportException:
                # Edge case when none of the subjects have a sex field
                result = {}

            project['female_count'] = result.get('female',0)
            project['male_count'] = result.get('male',0)
            project['other_count'] = result.get('other',0)


            # Construct grid of subject sex, race and ethnicity
            # Use last sex/race/ethnicity reporting for subjects with multiple entries
            grid_q = copy.deepcopy(subject_q)

            pipeline = [
                {'$match': grid_q},
                {'$group': {'_id': '$subject._id', 'sex':       {'$last': '$subject.sex'},
                                                   'race':      {'$last': '$subject.race'},
                                                   'ethnicity': {'$last': '$subject.ethnicity'}}},
                {'$group': {'_id': { 'sex': '$sex', 'race': '$race', 'ethnicity': '$ethnicity'}, 'count': {'$sum': 1}}}
            ]
            results = self._get_result_list(config.db.command('aggregate', 'sessions', pipeline=pipeline))

            grid, total = self._process_demo_results(results, project['demographics_grid'])
            project['demographics_grid'] = grid
            project['demographics_total'] = total

            # Count subjects by age group
            # Age is taken as an average over all subject entries
            age_q = copy.deepcopy(subject_q)
            age_q['subject.age'] = {'$gt': 0}

            pipeline = [
                {'$match': age_q},
                {'$group': {'_id': '$subject._id', 'age': { '$avg': '$subject.age'}}},
                {'$project': {'_id': 1, 'over_18':  {'$cond': [{'$gte': ['$age', EIGHTEEN_YEARS_IN_SEC]}, 1, 0]},
                                        'under_18': {'$cond': [{'$lt': ['$age', EIGHTEEN_YEARS_IN_SEC]}, 1, 0]}}},
                {'$group': {'_id': 1, 'over_18': {'$sum': '$over_18'}, 'under_18': {'$sum': '$under_18'}}}
            ]
            try:
                result = self._get_result(config.db.command('aggregate', 'sessions', pipeline=pipeline))
            except APIReportException:
                # Edge case when none of the subjects have an age field
                result = {}

            project['over_18_count'] = result.get('over_18',0)
            project['under_18_count'] = result.get('under_18',0)


            report['projects'].append(project)

        return report


class AccessLogReport(Report):
    """
    Report of the last <limit> logs in the access log.

    Specify a uid to only return logs for a specific user.
    Specify a date range to only return logs in that range.

    Report includes:
      - action completed
      - user that took action
      - information about the session/project/group in which the action took place
    """

    # What to name csvs generated from this report
    csv_filename = 'accesslog.csv'

    def __init__(self, params):
        """
        Initialize an Access Log Report

        Possible keys in :params:
        :start_date:    ISO formatted timestamp
        :end_date:      ISO formatted timestamp
        :uid:           user id of the target user
        :limit:         number of records to return
        :subject:       subject code of session accessed
        :access_type:  list of access_types to filter logs
        :csv:           Boolean if user wants csv file
        """

        super(AccessLogReport, self).__init__(params)

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        uid = params.get('user')
        limit= params.get('limit', 100)
        subject = params.get('subject', None)
        project = params.get('project', None)
        access_types = params.getall('access_type')

        if start_date:
            start_date = dateutil.parser.parse(start_date)
        if end_date:
            end_date = dateutil.parser.parse(end_date)
        if end_date and start_date and end_date < start_date:
            raise APIReportParamsException('End date {} is before start date {}'.format(end_date, start_date))
        if uid and not util.is_user_id(uid):
            raise APIReportParamsException('Invalid user.')
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise APIReportParamsException('Limit must be an integer greater than 0.')
        if limit < 1:
            raise APIReportParamsException('Limit must be an integer greater than 0.')
        elif limit > 10000:
            raise APIReportParamsException('Limit exceeds 10,000 entries, please contact admin to run script.')
        for access_type in access_types:
            if access_type not in AccessTypeList:
                raise APIReportParamsException('Not a valid access type')

        self.start_date     = start_date
        self.end_date       = end_date
        self.uid            = uid
        self.limit          = limit
        self.subject        = subject
        self.project        = project
        self.access_types   = access_types

    def user_can_generate(self, uid):
        """
        User generating report must be superuser
        """
        if config.db.users.count({'_id': uid, 'root': True}) > 0:
            return True
        return False

    def build(self):
        query = {}

        if self.uid:
            query['origin.id'] = self.uid
        if self.start_date or self.end_date:
            query['timestamp'] = {}
        if self.start_date:
            query['timestamp']['$gte'] = self.start_date
        if self.end_date:
            query['timestamp']['$lte'] = self.end_date
        if self.subject:
            query['context.subject.label'] = self.subject
        if self.project:
            query['context.project.id'] = self.project
        if self.access_types:
            query['access_type'] = {'$in': self.access_types}

        return config.log_db.access_log.find(query).limit(self.limit).sort('timestamp', pymongo.DESCENDING).batch_size(1000)

    def build_csv(self, filepath):
        csv_file = open(filepath, 'w+')
        writer = csv.DictWriter(csv_file, ACCESS_LOG_FIELDS)
        writer.writeheader()

        for doc in self.build():

            # Format timestamp as ISO UTC
            doc['timestamp'] = pytz.timezone('UTC').localize(doc['timestamp']).isoformat()

            # mongo_dict flattens dictionaries using a dot notation
            writer.writerow(util.mongo_dict(doc))

        # Need to close and reopen file to flush buffer into file
        csv_file.close()



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
            results = self._get_result_list(config.db.command('aggregate', 'jobs', pipeline=pipeline))
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
            results = self._get_result_list(config.db.command('aggregate', 'sessions', pipeline=pipeline))
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

        file_q = {}
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
                results = self._get_result_list(config.db.command('aggregate', cont_name, pipeline=pipeline))
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
                results = self._get_result_list(config.db.command('aggregate', cont_name, pipeline=pipeline))
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
            file_q = {}
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
                    result = self._get_result(config.db.command('aggregate', cont_name, pipeline=pipeline))
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


ReportTypes = {
    'site'         : SiteReport,
    'project'      : ProjectReport,
    'accesslog'    : AccessLogReport,
    'usage'        : UsageReport
}
