#!/usr/bin/env python3
"""NOTE: This script REQUIRES python3"""

import argparse
import csv
import flywheel
import hashlib
import random
import sys

from datetime import datetime
from flywheel.rest import ApiException

FILE_PERCENT = 0.10


class ExceptionHandler(object):
    def __init__(self, logger, container_type, container):
        self.logger = logger
        self.container_type = container_type
        self.container = container

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, traceback):
        if exc_type == ApiException:
            print("Caught ApiException: {}".format(exc_val), file=sys.stderr)
            self.logger.report_exception(self.container_type, self.container, exc_val)
            return True


class ErrorLogger(object):
    def __init__(self, out=sys.stdout, stop_on_error=False):
        self.out = out
        self.writer = csv.writer(out)
        self.count = 0
        self.writer.writerow(["Container", "Id", "Key", "Error"])
        self.model = "UNKNOWN"
        self.stop_on_error = stop_on_error

    def set_model_type(self, model):
        self.model = model

    def assert_is_none(self, model, key):
        if key in model and model[key] is not None:
            self.report_error(model, key, "Expected value to be None, but got {} instead".format(model[key]))

    def assert_not_none(self, model, key):
        if key not in model or model[key] is None:
            self.report_error(model, key, "Expected value, but got None instead")

    def assert_is_instance(self, model, key, types):
        if key not in model:
            self.report_error(model, key, "Expected an instance of ({}), but got None instead".format(", ".join(types)))
        elif model[key] is not None and not isinstance(model[key], types):
            typelist = ", ".join([str(t) for t in types])
            actual = str(type(model[key]))
            self.report_error(model, key, "Expected an instance of ({}), but got {} instead".format(typelist, actual))

    def handle(self, container_type, container):
        return ExceptionHandler(self, container_type, container)

    def report_error(self, model, key, msg, container_type=None):
        if container_type is None:
            container_type = self.model
        self.writer.writerow([container_type, model.get("_id"), key, msg])
        self.out.flush()
        self.count += 1

    def report_exception(self, container_type, model, ex):
        msg = str(ex)
        if isinstance(ex, ApiException):
            msg = "{} {}".format(ex.status, ex.reason)
        self.writer.writerow([container_type, model.get("_id"), "NONE", msg])
        self.out.flush()
        self.count += 1

        if self.stop_on_error:
            sys.exit(1)

    def validate_config(self, config):
        self.set_model_type("config")

        self.assert_not_none(config, "site")
        self.assert_not_none(config, "created")
        self.assert_not_none(config, "modified")

        # TODO: Bug?
        # self.assert_is_instance(config, 'created', (datetime,))
        # self.assert_is_instance(config, 'modified', (datetime,))

    def validate_user(self, user):
        self.set_model_type("user")

        self.assert_not_none(user, "_id")
        self.assert_not_none(user, "email")
        self.assert_is_instance(user, "created", (datetime,))
        self.assert_is_instance(user, "modified", (datetime,))

    def validate_group(self, group):
        self.set_model_type("group")

        self.assert_not_none(group, "_id")
        self.assert_is_instance(group, "created", (datetime,))
        self.assert_is_instance(group, "modified", (datetime,))

    def validate_gear(self, gear):
        self.set_model_type("gear")

        self.assert_not_none(gear, "_id")
        self.assert_not_none(gear, "gear")
        self.assert_not_none(gear.gear, "name")
        self.assert_not_none(gear.gear, "version")

    def validate_project(self, project):
        self.set_model_type("project")

        self.assert_not_none(project, "_id")
        self.assert_not_none(project, "group")
        self.assert_not_none(project, "label")
        self.assert_is_instance(project, "created", (datetime,))
        self.assert_is_instance(project, "modified", (datetime,))

    def validate_session(self, session):
        self.set_model_type("session")

        self.assert_not_none(session, "_id")
        self.assert_not_none(session, "project")
        self.assert_is_instance(session, "created", (datetime,))
        self.assert_is_instance(session, "modified", (datetime,))

    def validate_subject(self, subject):
        self.set_model_type("subject")

        self.assert_not_none(subject, "_id")
        # self.assert_not_none(subject, 'code')

    def validate_acquisition(self, acquisition):
        self.set_model_type("acquisition")

        self.assert_not_none(acquisition, "_id")
        self.assert_not_none(acquisition, "session")
        self.assert_is_instance(acquisition, "created", (datetime,))
        self.assert_is_instance(acquisition, "modified", (datetime,))

    def validate_collection(self, collection):
        self.set_model_type("collection")
        self.assert_not_none(collection, "_id")
        self.assert_not_none(collection, "label")
        self.assert_is_instance(collection, "created", (datetime,))
        self.assert_is_instance(collection, "modified", (datetime,))

    def validate_analysis(self, analysis):
        self.set_model_type("analysis")
        self.assert_not_none(analysis, "_id")
        self.assert_not_none(analysis, "label")
        self.assert_is_instance(analysis, "created", (datetime,))
        self.assert_is_instance(analysis, "modified", (datetime,))

    def validate_file(self, file_entry):
        self.set_model_type("file")

        self.assert_not_none(file_entry, "_id")
        self.assert_not_none(file_entry, "name")
        self.assert_not_none(file_entry, "size")
        self.assert_is_instance(file_entry, "created", (datetime,))
        self.assert_is_instance(file_entry, "modified", (datetime,))

    def validate_device(self, device):
        self.set_model_type("device")

        self.assert_not_none(device, "_id")
        self.assert_not_none(device, "name")
        self.assert_not_none(device, "type")


def walk_project(fw, validator, project):
    validator.validate_project(project)
    print("Project: {}".format(project.get("label", "UNKNOWN")))

    with validator.handle("project", project):
        # Retrieve and validate
        project = fw.get_project(project.id)
        validator.validate_project(project)

        test_files(fw, validator, "project", project)

        # Test analyses
        test_analyses(fw, validator, "project", project)

        # Walk sessions
        for session in fw.get_project_sessions(project.id):
            walk_session(fw, validator, session)


def walk_session(fw, validator, session):
    print("  Session: {}".format(session.get("label", "UNKNOWN")))
    validator.validate_session(session)

    with validator.handle("session", session):
        # Retrieve and validate
        session = fw.get_session(session.id)
        validator.validate_session(session)

        # Check subject
        subject = session.get("subject")
        if subject is not None:
            validator.validate_subject(subject)

        # Check files
        test_files(fw, validator, "session", session)

        # Test analyses
        test_analyses(fw, validator, "session", session)

        for acquisition in fw.get_session_acquisitions(session.id):
            walk_acquisition(fw, validator, acquisition)


def walk_acquisition(fw, validator, acquisition):
    print("    Acquisition: {}".format(acquisition.get("label", "UNKNOWN")))
    validator.validate_acquisition(acquisition)

    with validator.handle("acquisition", acquisition):
        # Retrieve and validate
        acquisition = fw.get_acquisition(acquisition.id)
        validator.validate_acquisition(acquisition)

        # Check files
        test_files(fw, validator, "acquisition", acquisition)

        # Test analyses
        test_analyses(fw, validator, "acquisition", acquisition)


def walk_collection(fw, validator, collection):
    print("Collection: {}".format(collection.get("label", "UNKNOWN")))
    validator.validate_collection(collection)

    with validator.handle("collection", collection):
        # Retrieve and validate
        collection = fw.get_collection(collection.id)
        validator.validate_collection(collection)

        for session in fw.get_collection_sessions(collection.id):
            walk_session(fw, validator, session)

        for acquisition in fw.get_collection_acquisitions(collection.id):
            walk_acquisition(fw, validator, acquisition)

        # Check files
        test_files(fw, validator, "collection", collection)

        # Test analyses
        test_analyses(fw, validator, "collection", collection, retrieve=False)


def test_analyses(fw, validator, container_type, container, retrieve=True):
    if retrieve:
        fn_name = "get_{}_analyses".format(container_type)
        fn = getattr(fw, fn_name)
        analyses = fn(container["_id"])
    else:
        analyses = container.get("analyses", [])

    for analysis in analyses:
        with validator.handle("analysis", analysis):
            validator.validate_analysis(analysis)

            # Retrieve and validate
            analysis = fw.get_analysis(analysis.id)
            validator.validate_analysis(analysis)

            # Check files
            test_files(fw, validator, "analysis", analysis)


def test_files(fw, validator, container_type, container):
    files = container.get("files", [])

    if files:
        for file_entry in files:
            with validator.handle("file", file_entry):
                validator.validate_file(file_entry)

                if random.random() < FILE_PERCENT:
                    file_entry = random.choice(files)
                    print("File: {}".format(file_entry["name"]))

                    # Attempt to download file
                    if container_type == "analysis":
                        fn_name = "download_output_from_analysis_as_data"
                    else:
                        fn_name = "download_file_from_{}_as_data".format(container_type)
                    fn = getattr(fw, fn_name)

                    try:
                        data = fn(container["_id"], file_entry["name"])

                        # Validate length
                        if len(data) != file_entry["size"]:
                            validator.report_error(container, file_entry["name"], "Invalid file size reported", container_type=container_type)

                        hash_str = file_entry.get("hash")
                        if hash_str:
                            _, alg, checksum = hash_str.split("-")
                            hasher = hashlib.new(alg)
                            hasher.update(data)
                            digest = hasher.hexdigest()
                            if digest != checksum:
                                validator.report_error(container, file_entry["name"], "Checksum mismatch reported", container_type=container_type)

                    except ApiException as e:
                        validator.report_error(container, file_entry["name"], "Error downloading file: {} {}".format(e.status, e.reason), container_type=container_type)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk an entire flywheel site")
    parser.add_argument("--api-key", required=True, help="The api key to use")
    parser.add_argument("--root", action="store_true", help="Use a root Flywheel client")
    parser.add_argument("--seed", type=int, help="Random seed to use")
    parser.add_argument("--file-pct", type=float, default="0.10", help="Percentage of files to visit")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop the script if an exception is encountered")
    parser.add_argument("dest_file", help="The destination file")

    args = parser.parse_args()

    seed = args.seed if args.seed is not None else round(datetime.utcnow().timestamp())
    print("Using seed: {}".format(seed))
    random.seed(seed)

    FILE_PERCENT = args.file_pct

    with open(args.dest_file, "w") as out:
        fw = flywheel.Flywheel(args.api_key, root=args.root)
        validator = ErrorLogger(out, stop_on_error=args.stop_on_error)

        start = datetime.now()

        # User self
        user = fw.get_current_user()
        validator.validate_user(user)

        # Config
        config = fw.get_config()
        validator.validate_config(config)

        # List users
        for user in fw.get_all_users():
            validator.validate_user(user)

        # List gears
        for gear in fw.get_all_gears():
            validator.validate_gear(gear)

        # List groups
        for group in fw.get_all_groups():
            validator.validate_group(group)

        # List devices
        for device in fw.get_all_devices():
            validator.validate_device(device)

        # Walk projects
        for project in fw.get_all_projects():
            walk_project(fw, validator, project)

        # Walk collections
        for collection in fw.get_all_collections():
            walk_collection(fw, validator, collection)

        # Attempt search queries?

    # Print Error Summary
    elapsed = (datetime.now() - start).total_seconds()
    print("Finished. Found {} errors after {} seconds".format(validator.count, elapsed))
