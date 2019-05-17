import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel


class ContainersTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

    def test_get_container(self):
        fw = self.fw

        cgroup = fw.get_container(self.group_id)
        cproject = fw.get_container(self.project_id)
        csession = fw.get_container(self.session_id)
        cacquisition = fw.get_container(self.acquisition_id)

        group = fw.get_group(self.group_id)
        project = fw.get_project(self.project_id)
        session = fw.get_session(self.session_id)
        acquisition = fw.get_acquisition(self.acquisition_id)

        self.assertEqual(dict(cgroup), dict(group))
        self.assertEqual(dict(cproject), dict(project))
        self.assertEqual(dict(csession), dict(session))
        self.assertEqual(dict(cacquisition), dict(acquisition))

    def test_modify_container(self):
        fw = self.fw

        fw.modify_container(self.acquisition_id, {"label": "NewName"})

        cacquisition = fw.get_container(self.acquisition_id)
        acquisition = fw.get_acquisition(self.acquisition_id)

        self.assertEqual(cacquisition.label, "NewName")
        self.assertEqual(dict(cacquisition), dict(acquisition))

    def test_notes_and_tags(self):
        # Notes, Tags
        fw = self.fw

        acquisition = flywheel.Acquisition(label=self.rand_string(), session=self.session_id)
        acquisition_id = fw.add_acquisition(acquisition)

        message = "This is a note"
        fw.add_container_note(acquisition_id, message)

        tag = "example-tag"
        fw.add_container_tag(acquisition_id, tag)

        # Replace Info
        fw.replace_container_info(acquisition_id, {"foo": 3, "bar": "qaz"})

        # Set Info
        fw.set_container_info(acquisition_id, {"foo": 42, "hello": "world"})

        # Check
        c_acquisition = fw.get_container(acquisition_id)

        self.assertEqual(len(c_acquisition.notes), 1)
        self.assertEqual(c_acquisition.notes[0].text, message)

        self.assertEqual(len(c_acquisition.tags), 1)
        self.assertEqual(c_acquisition.tags[0], tag)

        self.assertEqual(c_acquisition.info["foo"], 42)
        self.assertEqual(c_acquisition.info["bar"], "qaz")
        self.assertEqual(c_acquisition.info["hello"], "world")

        # Delete info fields
        fw.delete_container_info_fields(acquisition_id, ["foo", "bar"])

        c_acquisition = fw.get_container(acquisition_id)
        self.assertNotIn("foo", c_acquisition.info)
        self.assertNotIn("bar", c_acquisition.info)
        self.assertEqual(c_acquisition.info["hello"], "world")

        # Delete
        fw.delete_container(acquisition_id)

        acquisitions = fw.get_all_acquisitions()
        self.assertNotIn(c_acquisition, acquisitions)

    def test_container_files(self):
        fw = self.fw

        acquisition = flywheel.Acquisition(label=self.rand_string(), session=self.session_id)
        acquisition_id = fw.add_acquisition(acquisition)

        # Upload a file
        poem = "Turning and turning in the widening gyre"
        fw.upload_file_to_container(acquisition_id, flywheel.FileSpec("yeats.txt", poem))

        # Check that the file was added to the acquisition
        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(len(c_acquisition.files), 1)
        self.assertEqual(c_acquisition.files[0].name, "yeats.txt")
        self.assertEqual(c_acquisition.files[0].size, 40)
        self.assertEqual(c_acquisition.files[0].mimetype, "text/plain")

        # Download the file and check content
        self.assertDownloadFileTextEquals(fw.download_file_from_container_as_data, acquisition_id, "yeats.txt", poem)

        # Test unauthorized download with ticket for the file
        self.assertDownloadFileTextEqualsWithTicket(fw.get_container_download_url, acquisition_id, "yeats.txt", poem)

        # Test file attributes
        self.assertEqual(c_acquisition.files[0].modality, None)
        self.assertEmpty(c_acquisition.files[0].classification)
        self.assertEqual(c_acquisition.files[0].type, "text")

        resp = fw.modify_container_file(acquisition_id, "yeats.txt", flywheel.FileEntry(modality="modality", type="type"))

        # Check that no jobs were triggered, and attrs were modified
        self.assertEqual(resp.jobs_spawned, 0)

        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(c_acquisition.files[0].modality, "modality")
        self.assertEmpty(c_acquisition.files[0].classification)
        self.assertEqual(c_acquisition.files[0].type, "type")

        # Test classifications
        resp = fw.modify_container_file_classification(acquisition_id, "yeats.txt", {"modality": "modality2", "replace": {"Custom": ["measurement1", "measurement2"]}})
        self.assertEqual(resp.modified, 1)
        self.assertEqual(resp.jobs_spawned, 0)

        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(c_acquisition.files[0].modality, "modality2")
        self.assertEqual(c_acquisition.files[0].classification, {"Custom": ["measurement1", "measurement2"]})

        resp = fw.set_container_file_classification(acquisition_id, "yeats.txt", {"Custom": ["HelloWorld"]})
        self.assertEqual(resp.modified, 1)
        self.assertEqual(resp.jobs_spawned, 0)

        resp = fw.delete_container_file_classification_fields(acquisition_id, "yeats.txt", {"Custom": ["measurement2"]})
        self.assertEqual(resp.modified, 1)
        self.assertEqual(resp.jobs_spawned, 0)

        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(c_acquisition.files[0].classification, {"Custom": ["measurement1", "HelloWorld"]})

        # Test file info
        self.assertEmpty(c_acquisition.files[0].info)
        fw.replace_container_file_info(acquisition_id, "yeats.txt", {"a": 1, "b": 2, "c": 3, "d": 4})

        fw.set_container_file_info(acquisition_id, "yeats.txt", {"c": 5})

        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(c_acquisition.files[0].info["a"], 1)
        self.assertEqual(c_acquisition.files[0].info["b"], 2)
        self.assertEqual(c_acquisition.files[0].info["c"], 5)
        self.assertEqual(c_acquisition.files[0].info["d"], 4)

        fw.delete_container_file_info_fields(acquisition_id, "yeats.txt", ["c", "d"])
        c_acquisition = fw.get_container(acquisition_id)
        self.assertEqual(c_acquisition.files[0].info["a"], 1)
        self.assertEqual(c_acquisition.files[0].info["b"], 2)
        self.assertNotIn("c", c_acquisition.files[0].info)
        self.assertNotIn("d", c_acquisition.files[0].info)

        fw.replace_container_file_info(acquisition_id, "yeats.txt", {})
        c_acquisition = fw.get_container(acquisition_id)
        self.assertEmpty(c_acquisition.files[0].info)

        # Delete file
        fw.delete_container_file(acquisition_id, "yeats.txt")
        c_acquisition = fw.get_container(acquisition_id)
        self.assertEmpty(c_acquisition.files)

        # Delete acquisition
        fw.delete_container(acquisition_id)

    def test_container_analysis(self):
        fw = self.fw

        acquisition = flywheel.Acquisition(session=self.session_id, label=self.rand_string())

        # Add
        acquisition_id = fw.add_acquisition(acquisition)
        self.assertNotEmpty(acquisition_id)

        poem = "Troubles my sight: a waste of desert sand;"
        fw.upload_file_to_container(acquisition_id, flywheel.FileSpec("yeats.txt", poem))

        file_ref = flywheel.FileReference(id=acquisition_id, type="acquisition", name="yeats.txt")

        analysis = flywheel.AnalysisInput(label=self.rand_string(), description=self.rand_string(), inputs=[file_ref])

        # Add
        analysis_id = fw.add_container_analysis(acquisition_id, analysis)
        self.assertNotEmpty(analysis_id)

        # Get the list of analyses in the acquisition
        analyses = fw.get_container_analyses(acquisition_id)
        self.assertEqual(len(analyses), 1)

        r_analysis = analyses[0]

        self.assertEqual(r_analysis.id, analysis_id)
        self.assertEmpty(r_analysis.job)

        self.assertTimestampBeforeNow(r_analysis.created)
        self.assertGreaterEqual(r_analysis.modified, r_analysis.created)

        self.assertEqual(len(r_analysis.inputs), 1)
        self.assertEqual(r_analysis.inputs[0].name, "yeats.txt")

    def test_delete_container(self):
        fw = self.fw

        fw.delete_container(self.session_id)

        sessions = fw.get_project_sessions(self.project_id)
        self.assertTrue(len(sessions) == 0)
