import os
import six
import tarfile
import tempfile
import unittest

from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel


class DownloadTicketTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()
        self.tmpfile = None

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)

        if self.tmpfile:
            try:
                os.remove(self.tmpfile)
            except:
                pass

    def test_acquisition_files(self):
        fw = self.fw

        project = fw.get_project(self.project_id)
        session = fw.get_session(self.session_id)
        acquisition = fw.get_acquisition(self.acquisition_id)

        # Upload a file to session and acquisition
        poem1 = "When a vast image out of Spiritus Mundi"
        fw.upload_file_to_session(self.session_id, flywheel.FileSpec("yeats1.txt", poem1))

        poem2 = "Troubles my sight: a waste of desert sand;"
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec("yeats2.txt", poem2))

        # Create the download ticket for the container
        node = flywheel.DownloadNode(level="session", id=self.session_id)
        downloadSpec = flywheel.DownloadInput(nodes=[node], optional=True)

        ticket = fw.create_download_ticket(downloadSpec, prefix="flywheel")
        self.assertIsNotNone(ticket)
        self.assertIsNotNone(ticket.ticket)
        self.assertEqual(2, ticket.file_cnt)
        self.assertGreater(ticket.size, 1)

        fd, self.tmpfile = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)

        # Attempt to complete the download
        fw.download_ticket(ticket.ticket, self.tmpfile)

        self.assertTrue(os.path.isfile(self.tmpfile))
        self.assertGreater(os.path.getsize(self.tmpfile), 0)

        sess_path = "flywheel/{}/{}/{}/{}".format(self.group_id, project["label"], session.get("subject", {}).get("code", "unknown_subject"), session["label"])
        sess_file = "{}/{}".format(sess_path, "yeats1.txt")

        acq_path = "{}/{}".format(sess_path, acquisition["label"])
        acq_file = "{}/{}".format(acq_path, "yeats2.txt")

        # Verify the download structure
        with tarfile.open(self.tmpfile, mode="r") as tar:
            tar_names = tar.getnames()

            self.assertEqual(2, len(tar_names))
            self.assertIn(sess_file, tar_names)
            self.assertIn(acq_file, tar_names)

            # Read member data
            mem_f = tar.extractfile(sess_file)
            data = mem_f.read()
            self.assertEqual(six.u(poem1), data.decode("utf-8"))
            mem_f.close()

            mem_f = tar.extractfile(acq_file)
            data = mem_f.read()
            self.assertEqual(six.u(poem2), data.decode("utf-8"))
            mem_f.close()
