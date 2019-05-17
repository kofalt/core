import bson
import copy
import dateutil

from .report import Report

from .. import config

from ..web.errors import APIReportParamsException


EIGHTEEN_YEARS_IN_SEC = 18 * 365.25 * 24 * 60 * 60


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

        project_list = params.getall("projects")
        start_date = params.get("start_date")
        end_date = params.get("end_date")

        if len(project_list) < 1:
            raise APIReportParamsException("List of projects requried for Project Report")
        if start_date:
            start_date = dateutil.parser.parse(start_date)
        if end_date:
            end_date = dateutil.parser.parse(end_date)
        if end_date and start_date and end_date < start_date:
            raise APIReportParamsException("End date {} is before start date {}".format(end_date, start_date))

        self.projects = [bson.ObjectId(id_) for id_ in project_list]
        self.start_date = start_date
        self.end_date = end_date

    def user_can_generate(self, uid):
        """
        User generating report must be admin on all
        """

        perm_count = config.db.projects.count({"_id": {"$in": self.projects}, "permissions._id": uid, "permissions.access": "admin"})
        if perm_count == len(self.projects):
            return True
        return False

    def _base_query(self, pid):
        base_query = {"project": pid, "deleted": {"$exists": False}}

        if self.start_date is not None or self.end_date is not None:
            base_query["created"] = {}
        if self.start_date is not None:
            base_query["created"]["$gte"] = self.start_date
        if self.end_date is not None:
            base_query["created"]["$lte"] = self.end_date

        return base_query

    def _base_demo_grid(self):
        """
        Constructs a base demographics grid for the project report
        """

        races = ["American Indian or Alaska Native", "Asian", "Native Hawaiian or Other Pacific Islander", "Black or African American", "White", "More Than One Race", "Unknown or Not Reported"]
        ethnicities = ["Not Hispanic or Latino", "Hispanic or Latino", "Unknown or Not Reported"]
        sexes = ["Female", "Male", "Unknown or Not Reported"]

        sexes_obj = dict([(s, 0) for s in sexes])
        eth_obj = dict([(e, copy.deepcopy(sexes_obj)) for e in ethnicities])
        eth_obj["Total"] = 0
        race_obj = dict([(r, copy.deepcopy(eth_obj)) for r in races])
        race_obj["Total"] = copy.deepcopy(eth_obj)

        return race_obj

    def _base_project_report(self):
        """
        Constructs a dictionary representation of the project report with neutral values
        """
        return {"name": "", "group_name": "", "admins": [], "session_count": 0, "subjects_count": 0, "female_count": 0, "male_count": 0, "other_count": 0, "demographics_grid": self._base_demo_grid(), "demographics_total": 0, "over_18_count": 0, "under_18_count": 0}

    def _process_demo_results(self, results, grid):
        """
        Given demographics aggregation results, fill in base demographics grid

        All `null` or unlisted values will be counted as 'Unknown or Not Reported'
        """
        UNR = "Unknown or Not Reported"
        total = 0

        for r in results:
            count = int(r["count"])
            cell = r["_id"]
            race = cell.get("race")
            ethnicity = cell.get("ethnicity")
            sex = cell.get("sex")

            # Null or unrecognized values are listed as UNR default
            if race is None or race not in grid:
                race = UNR
            if ethnicity is None or ethnicity not in grid[race]:
                ethnicity = UNR
            if sex is None:
                sex = UNR
            else:
                sex = sex.capitalize()  # We store sex as lowercase in the db
            if sex not in grid[race][ethnicity]:
                sex = UNR

            # Tally up
            total += count
            grid[race]["Total"] += count
            grid[race][ethnicity][sex] += count
            grid["Total"][ethnicity][sex] += count

        return grid, total

    def build(self):
        report = {}
        report["projects"] = []

        projects = config.db.projects.find({"_id": {"$in": self.projects}, "deleted": {"$exists": False}})
        for p in projects:
            project = self._base_project_report()
            project["name"] = p.get("label")
            project["group_name"] = p.get("group")

            # Create list of project admins
            admins = []
            for perm in p.get("permissions", []):
                if perm.get("access") == "admin":
                    admins.append(perm.get("_id"))
            admin_objs = config.db.users.find({"_id": {"$in": admins}})
            project["admins"] = [a.get("firstname", "") + " " + a.get("lastname", "") for a in admin_objs]

            base_query = self._base_query(p["_id"])
            sessions = list(config.db.sessions.find(base_query, {"_id": 1, "subject": 1}))
            project["session_count"] = len(sessions)

            # If there are no sessions in this project for the date range,
            # no need to continue grabbing more stats
            if project["session_count"] == 0:
                report["projects"].append(project)
                continue

            # Count subjects (only include those referenced by sessions)
            subject_q = {"_id": {"$in": list(set(session["subject"] for session in sessions))}}
            project["subjects_count"] = config.db.subjects.count(subject_q)

            # Count subjects by sex
            pipeline = [{"$match": subject_q}, {"$group": {"_id": "$sex", "count": {"$sum": 1}}}]
            results = self._get_result_list("subjects", pipeline)
            result = {group["_id"]: group["count"] for group in results}
            project["female_count"] = result.get("female", 0)
            project["male_count"] = result.get("male", 0)
            project["other_count"] = result.get("other", 0)

            # Construct grid of subject sex, race and ethnicity
            grid_q = copy.deepcopy(subject_q)

            pipeline = [{"$match": grid_q}, {"$group": {"_id": {"sex": "$sex", "race": "$race", "ethnicity": "$ethnicity"}, "count": {"$sum": 1}}}]
            results = self._get_result_list("subjects", pipeline)

            grid, total = self._process_demo_results(results, project["demographics_grid"])
            project["demographics_grid"] = grid
            project["demographics_total"] = total

            # Count subjects by age group
            # Age is taken as an average over all subject entries
            pipeline = [
                {"$match": base_query},
                {"$group": {"_id": "$subject", "age": {"$avg": "$age"}}},
                {"$project": {"_id": 1, "over_18": {"$cond": [{"$gte": ["$age", EIGHTEEN_YEARS_IN_SEC]}, 1, 0]}, "under_18": {"$cond": [{"$and": [{"$lt": ["$age", EIGHTEEN_YEARS_IN_SEC]}, {"$gte": ["$age", 0]}]}, 1, 0]}}},
                {"$group": {"_id": 1, "over_18": {"$sum": "$over_18"}, "under_18": {"$sum": "$under_18"}}},
            ]
            result = self._get_result("sessions", pipeline)

            project["over_18_count"] = result.get("over_18", 0)
            project["under_18_count"] = result.get("under_18", 0)

            report["projects"].append(project)

        return report
