import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition
from test_gear import create_test_gear

import flywheel

class JobsTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()
        self.gear_id = create_test_gear()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)
        self.fw.delete_gear(self.gear_id)

    def test_job(self):
        fw = self.fw
       
        poem = 'Mere anarchy is loosed upon the world,'
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec('yeats.txt', poem))

        tag = self.rand_string()
        job = flywheel.JobInput(
            gear_id=self.gear_id,
            
            destination=flywheel.JobDestination(
                id=self.acquisition_id, 
                type='acquisition'
            ),

            inputs={
                'any-file': flywheel.FileReference(
                    id=self.acquisition_id,
                    type='acquisition',
                    name='yeats.txt'
                )
            },

            tags=[tag]
        )

        # Add
        job_id = fw.add_job(job)
        self.assertNotEmpty(job_id)

        # Get
        r_job = fw.get_job(job_id)
        self.assertEqual(r_job.gear_id, self.gear_id)
        self.assertEqual(r_job.state, 'pending')
        self.assertEqual(r_job.attempt, 1)
        self.assertIsNotNone(r_job.origin)
        self.assertEqual(r_job.origin.type, 'user')
        self.assertNotEmpty(r_job.origin.id)
        self.assertIn(tag, r_job.tags)
        self.assertTimestampBeforeNow(r_job.created)
        self.assertGreaterEqual(r_job.modified, r_job.created)

        # Modify
        tag2 = self.rand_string()
        job_mod = flywheel.Job(tags=[tag2])
        fw.modify_job(job_id, job_mod)

        # Check
        r_job = fw.get_job(job_id)
        self.assertEqual(r_job.state, 'pending')
        self.assertNotIn(tag, r_job.tags)
        self.assertIn(tag2, r_job.tags)

        # Cancel
        job_mod = flywheel.Job(state='cancelled')
        fw.modify_job(job_id, job_mod)

        # Check
        r_job = fw.get_job(job_id)
        self.assertEqual(r_job.state, 'cancelled')

