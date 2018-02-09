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
        fw = self.fw
       
        poem = 'The falcon cannot hear the falconer;'
        fw.upload_file_to_acquisition(self.acquisition_id, flywheel.FileSpec('yeats.txt', poem))

        # Add
        tag = self.rand_string()
        targets = [flywheel.ContainerReference(
            type='acquisition',
            id=self.acquisition_id
        )]
        proposal = fw.propose_batch(flywheel.BatchProposalInput(
            gear_id=self.gear_id, 
            config={},
            tags=[tag],
            targets=targets
        ))
        self.assertIsNotNone(proposal)

        self.assertNotEmpty(proposal.id)
        self.assertEquals(proposal.gear_id, self.gear_id)
        self.assertIsNotNone(proposal.origin)
        self.assertEqual(proposal.origin.type, 'user')
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
        jobs = fw.start_batch(proposal.id)
        self.assertEqual(len(jobs), 1)

        # Get again
        r_batch2 = fw.get_batch(proposal.id)
        self.assertEqual(r_batch2.state, 'running')
        self.assertTimestampAfter(r_batch2.modified, r_batch.modified)
        
        # Cancel
        cancelled = fw.cancel_batch(proposal.id)
        self.assertEqual(cancelled, 1)
