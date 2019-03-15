import json
import os
import shutil
import tempfile
import unittest
from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel
import mock

class GearContextTestCases(SdkTestCase):
    def setUp(self):
        self._path = tempfile.mkdtemp()
        cfg_path = os.path.join(self._path, 'config.json')
        with open(cfg_path, 'w') as f:
            json.dump(INVOCATION, f)

        self.context = flywheel.GearContext(gear_path=self._path)
        self.group_id = None
        self.project_id = None

    def tearDown(self):
        if self.project_id:
            self.fw.delete_project(self.project_id)
            self.fw.delete_group(self.group_id)
        shutil.rmtree(self._path)

    def createInputs(self):
        inputs_dir = os.path.join(self._path, 'inputs')
        os.makedirs(inputs_dir)

        for inp in self.context._get_invocation()['inputs'].values():
            if inp['base'] == 'file':
                inp_path = os.path.join(inputs_dir, inp['location']['name'])
                with open(inp_path, 'w') as f:
                    f.write('Hello World!')
                inp['location']['path'] = inp_path

    def createDestination(self):
        self.group_id, self.project_id, self.session_id, self.acquisition_id = create_test_acquisition()
        self.context.destination['id'] = self.acquisition_id

    def testGetAttributes(self):
        context = self.context
        self.assertEqual(context.config.get('not_exist', 'default'), 'default')
        self.assertEqual(context.config['speed'], 2)
        self.assertEqual(context.config['coordinates'], [1, 2, 3])

        self.assertEqual(context.destination['id'], 'example_id')
        self.assertEqual(context.destination['type'], 'acquisition')

        self.assertIsNotNone(context.output_dir)
        self.assertEqual(os.path.basename(context.output_dir), 'output')
        self.assertTrue(os.path.isdir(context.output_dir))

        # Stash api key input
        api_key = context._get_invocation()['inputs'].pop('an_api_key')
        self.assertRaises(RuntimeError, lambda: context.client)

        context._get_invocation()['inputs']['an_api_key'] = api_key
        self.assertIsInstance(context.client, flywheel.Client)

    def testInputs(self):
        context = self.context
        self.createInputs()

        self.assertIsNone(context.get_input('not_exist'))
        inp = context.get_input('text')
        self.assertIsNotNone(inp)
        self.assertEqual(inp['base'], 'file')

        with context.open_input('text', 'r') as f:
            text = f.read()

        self.assertEqual(text, 'Hello World!')

    def testExportBids(self):
        context = self.context

        self.createDestination()
        download_bids = mock.MagicMock()

        with mock.patch.object(context, '_load_download_bids') as patched_loader:
            patched_loader.return_value = download_bids

            bids_dir = context.download_session_bids()

            self.assertEqual(bids_dir, os.path.join(self._path, 'work', 'bids'))

            download_bids.assert_called_with(context.client, self.session_id, 'session', bids_dir, src_data=False)


INVOCATION = {
    'config': {
        'speed': 2,
        'coordinates': [1, 2, 3]
    },
    'inputs': {
        'text' : {
            'base' : 'file',
            'hierarchy' : {
                'type' : 'acquisition',
                'id' : '5988d38b3b49ee001bde0853'
            },
            'location' : {
                'name' : 'example.txt'
            },
            'object' : {
                'info' : {},
                'mimetype' : 'text/plain',
                'tags' : [],
                'measurements' : [],
                'type' : 'text',
                'modality' : None,
                'size' : 12
            }
        },

        'matlab_license_code': {
            'base': 'context',
            'found': True,
            'value': 'ABC'
        },

        'an_api_key': {
            'base': 'api-key',
            'key': os.environ.get('SdkTestKey')
        }
    },
    'destination': {
        'type': 'acquisition',
        'id': 'example_id'
    }
}

