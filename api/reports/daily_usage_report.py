import bson
import datetime

from .report import Report
from .. import config
from ..web.errors import APIReportParamsException

class DailyUsageReport(Report):
    """
    Creates a site usage report, aggregated by group and project, daily.

    This report uses usage_data collected in UsageReport. See that class for more detail.
    """
    can_collect = True
    columns = [
        'year', 'month', 'day', 'group', 'project',
        'project_label', 'session_count',
        'center_job_count', 'group_job_count',
        'center_compute_ms', 'group_compute_ms',
        'center_storage_bytes', 'group_storage_bytes'
    ]

    def __init__(self, params):
        """
        Initialize a Usage Report

        Possible keys in :params:
        :year:      The 4-digit requested report year
        :month:     The 1-indexed requested report month
        :group:     Limit report to one particular group
        :project:   Limit report to one particular project
        """
        super(DailyUsageReport, self).__init__(params)

        self.group = params.get('group')
        self.project = params.get('project')

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
        except (TypeError, ValueError) as e:
            raise APIReportParamsException('Invalid date specified: {}'.format(e))

    def user_can_generate(self, uid, roles):
        """
        User generating report must be superuser
        """
        if config.db.users.count({'_id': uid, 'root': True}) > 0:
            return True
        return False

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
        if self.group:
            query['group'] = self.group
        if self.project:
            query['project'] = bson.ObjectId(self.project)

        # Remove unwanted fields via projection
        projection = {'year': 0, 'month': 0, 'total': 0}
        sort = [('year', 1), ('month', 1), ('group', 1), ('project_label', 1)]

        # No roll-up of groups in the detail report
        records = []
        for row in config.db.usage_data.find(query, projection, sort=sort):
            # Produce one record per collected day, updating with common keys
            row_keys = {
                'year': self.year,
                'month': self.month,
                'group': row['group'],
                'project': row['project'],
                'project_label': row['project_label']
            }

            for day in range(1, 32):
                day_record = row['days'].get(str(day))
                if day_record:
                    day_record.update(row_keys)
                    day_record['day'] = day
                    records.append(day_record)

        return records
