import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition
from test_gear import create_test_gear

import flywheel

class BatchTestCases(SdkTestCase):
    def setUp(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()
        self.gear_id = create_test_gear()

    def tearDown(self):
        self.fw.delete_project(self.project_id)
        self.fw.delete_group(self.group_id)
        self.fw.delete_gear(self.gear_id)

    def test_batch(self):
        fw = self.fw_device

        poem = 'The falcon cannot hear the falconer;'
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec('yeats.txt', poem))

        # Add
        tag = self.rand_string()
        acq = fw.get_acquisition(self.acquisition_id)
        gear = fw.get_gear(self.gear_id)
        
        proposal = gear.propose_batch([acq], tags=[tag])
        self.assertIsNotNone(proposal)

        self.assertNotEmpty(proposal.id)
        self.assertEquals(proposal.gear_id, self.gear_id)
        self.assertIsNotNone(proposal.origin)
        self.assertEqual(proposal.origin.type, 'device')
        self.assertNotEmpty(proposal.origin.id)

        self.assertEqual(len(proposal.matched), 1)
        match = proposal.matched[0]
        self.assertEqual(match.id, self.acquisition_id)
        self.assertEqual(len(match.files), 1)
        self.assertEqual(match.files[0].name, 'yeats.txt')

        self.assertEmpty(proposal.ambiguous)
        self.assertEmpty(proposal.not_matched)
        self.assertEmpty(proposal.improper_permissions)

        self.assertTimestampBeforeNow(proposal.created)
        self.assertGreaterEqual(proposal.modified, proposal.created)

        # Get
        r_batch = fw.get_batch(proposal.id)
        self.assertIsNotNone(r_batch)
        self.assertEqual(r_batch.gear_id, self.gear_id)
        self.assertEqual(r_batch.state, 'pending')

        # Get all
        batches = fw.get_all_batches()
        self.assertIn(r_batch, batches)

        # Start
        jobs = proposal.run()
        self.assertEqual(len(jobs), 1)

        # Get again
        r_batch2 = fw.get_batch(proposal.id)
        self.assertEqual(r_batch2.state, 'running')
        self.assertTimestampAfter(r_batch2.modified, r_batch.modified)

        # Cancel
        cancelled = r_batch2.cancel()
        self.assertEqual(cancelled, 1)

    def test_batch_with_jobs(self):
        fw = self.fw_device

        gear = fw.get_gear(self.gear_id)
        self.assertIsNotNone(gear)

        # Make a couple jobs
        poem = 'Mere anarchy is loosed upon the world,'
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec('yeats.txt', poem))
        inputs = {
            'any-file': flywheel.FileReference(
                id=self.acquisition_id,
                type='acquisition',
                name='yeats.txt'
            )
        }
        destination = flywheel.JobDestination(
            id=self.acquisition_id,
            type='acquisition'
        )
        tag = self.rand_string()

        jobs = [
            flywheel.Job(
                gear_id=self.gear_id,
                destination=destination,
                inputs=inputs,
                tags=[tag]
            ),
            flywheel.Job(
                gear_id=self.gear_id,
                destination=destination,
                inputs=inputs,
                tags=[tag]
            )
        ]

        # Propose batch jobs
        proposal = fw.create_batch_job_from_jobs(flywheel.BatchJobsProposalInput(jobs=jobs))

        self.assertIsNotNone(proposal)

        self.assertNotEmpty(proposal.id)
        # Gear Id should be none, each job already knows its gear
        self.assertIsNone(proposal.gear_id)
        self.assertIsNotNone(proposal.origin)
        self.assertEqual(proposal.origin.type, 'device')
        self.assertNotEmpty(proposal.origin.id)

        self.assertTimestampBeforeNow(proposal.created)
        self.assertGreaterEqual(proposal.modified, proposal.created)

        # Get
        r_batch = fw.get_batch(proposal.id)
        self.assertIsNotNone(r_batch)
        # Gear Id should be none, each job already knows its gear
        self.assertIsNone(proposal.gear_id)
        self.assertEqual(r_batch.state, 'pending')

        # Get all
        batches = fw.get_all_batches()
        self.assertIn(r_batch, batches)

        # Start
        jobs = fw.start_batch(proposal.id)
        self.assertEqual(len(jobs), 2)

        # Get again
        r_batch2 = fw.get_batch(proposal.id)
        self.assertEqual(r_batch2.state, 'running')
        self.assertTimestampAfter(r_batch2.modified, r_batch.modified)

        # Cancel
        cancelled = fw.cancel_batch(proposal.id)
        self.assertEqual(cancelled, 2)
