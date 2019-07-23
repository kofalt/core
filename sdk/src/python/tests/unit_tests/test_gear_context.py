import unittest
from unittest import mock
import flywheel


class GearContextTestCases(unittest.TestCase):
    def test_gear_context_download_project_bids_should_pass_kwargs(self):
        gear_context = flywheel.GearContext()
        gear_context._download_bids = mock.MagicMock()

        gear_context.download_project_bids(dry_run=True)

        gear_context._download_bids.assert_called_with('project', 'work/bids',
                                                       {'dry_run': True})

if __name__ == '__main__':
    unittest.main()
