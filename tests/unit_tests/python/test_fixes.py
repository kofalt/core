import fixes
import mock


def test_move_flair_moves_flair():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Measurement': ['FLAIR'],
                'Features': []
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Measurement': [], 'Features': ['FLAIR']}}]}})


def test_move_flair_should_set_features_if_unset():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Measurement': ['FLAIR']
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Measurement': [], 'Features': ['FLAIR']}}]}})


def test_move_flair_should_set_features_if_set_to_none():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Measurement': ['FLAIR'],
                'Features': None
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Measurement': [], 'Features': ['FLAIR']}}]}})


def test_move_flair_should_update_superficially_if_no_flair_in_measurements():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Measurement': [],
                'Features': ['FLAIR']
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Measurement': [], 'Features': ['FLAIR']}}]}})


def test_move_flair_should_update_superficially_if_measurement_not_set():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Features': ['FLAIR']
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Features': ['FLAIR']}}]}})

def test_move_flair_should_update_superficially_if_measurement_set_to_none():
    container = {
        '_id': '123',
        'files': [{
            'classification': {
                'Measurement': None,
                'Features': ['FLAIR']
            }
        }]
    }

    with mock.patch('fixes.config.db') as m:
        fixes.move_flair_for_files_in_doc(container, 'acquisitions')

        m['acquisitions'].update.assert_called_with(
            {'_id': '123'},
            {'$set': {'files': [{'classification': {'Measurement': None, 'Features': ['FLAIR']}}]}})

