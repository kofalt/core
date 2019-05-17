import unittest
import json, zipfile
import six
from sdk_test_case import SdkTestCase
from test_session import create_test_session

import flywheel


class PackfileTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id = create_test_session()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_packfile(self):
        fw = self.fw

        session = fw.get_session(self.session_id)
        self.assertNotEmpty(session.label)

        acquisitions = fw.get_session_acquisitions(self.session_id)
        self.assertEmpty(acquisitions)

        poem1 = "Surely some revelation is at hand;"
        poem2 = "Surely the Second Coming is at hand."

        token = fw.start_project_packfile_upload(self.project_id)
        self.assertNotEmpty(token)

        files = [flywheel.FileSpec("yeats1.txt", poem1), flywheel.FileSpec("yeats2.txt", poem2)]

        fw.project_packfile_upload(self.project_id, token, files)

        acquisition_label = self.rand_string()

        metadata = {"project": {"_id": self.project_id}, "session": {"label": session.label}, "acquisition": {"label": acquisition_label}, "packfile": {"type": "text"}}
        metastr = json.dumps(metadata)

        resp = fw.end_project_packfile_upload(self.project_id, token, metastr, _preload_content=False)
        self.assertEqual(resp.status_code, 200)

        for line in resp.iter_lines():
            if six.PY3:
                line = line.decode("utf-8")
            print("response line: " + line)

        acquisitions = fw.get_session_acquisitions(self.session_id)
        self.assertEqual(len(acquisitions), 1)

        self.assertEqual(acquisitions[0].label, acquisition_label)
        self.assertEqual(len(acquisitions[0].files), 1)

        self.assertEqual(acquisitions[0].files[0].name, acquisition_label + ".zip")

        zip_data = fw.download_file_from_acquisition_as_data(acquisitions[0].id, acquisition_label + ".zip")
        zip_file = zipfile.ZipFile(six.BytesIO(zip_data))

        names = zip_file.namelist()
        self.assertIn(acquisition_label + "/yeats1.txt", names)
        self.assertIn(acquisition_label + "/yeats2.txt", names)

        with zip_file.open(acquisition_label + "/yeats1.txt") as f:
            data = f.read()
            if six.PY3:
                data = data.decode("utf-8")
            self.assertEqual(data, poem1)
        with zip_file.open(acquisition_label + "/yeats2.txt") as f:
            data = f.read()
            if six.PY3:
                data = data.decode("utf-8")
            self.assertEqual(data, poem2)
