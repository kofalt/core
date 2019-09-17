import bson
import mock
from api.jobs import job_util


def test_validate_job_against_gear_should_return_true_if_job_no_inputs_and_gear_no_inputs():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {},
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {}
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is True


def test_validate_job_against_gear_should_return_true_if_job_inputs_are_all_required_inputs():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'file': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'file': {
                'base': 'file',
                'required': True
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is True


def test_validate_job_against_gear_should_return_true_if_job_doesnt_input_optional():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'file': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'file': {
                'base': 'file',
                'required': True
            },
            'optional': {
                'base': 'file',
                'optional': True
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is True


def test_validate_job_against_gear_should_return_true_if_job_inputs_optional():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'file': mock.MagicMock(),
            'optional': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'file': {
                'base': 'file',
                'required': True
            },
            'optional': {
                'base': 'file',
                'optional': True
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is True


def test_validate_job_against_gear_should_return_false_if_job_inputs_wrong_input():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'file': mock.MagicMock(),
            'not-input': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'file': {
                'base': 'file',
                'required': True
            },
            'optional': {
                'base': 'file',
                'optional': True
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is False


def test_validate_job_against_gear_should_return_false_if_job_inputs_non_file_or_context_input():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'context-input': mock.MagicMock(),
            'apikey': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'context': {
                'base': 'context'
            },
            'apikey': {
                'base': 'api-key'
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is False


def test_validate_job_against_gear_should_return_false_if_job_doesnt_input_all_required():
    job_map = {
        '_id': bson.ObjectId(),
        'inputs': {
            'file': mock.MagicMock(),
            'optional': mock.MagicMock()
        },
        'gear_id': 'gear-id'
    }
    gear_doc = {
        'inputs': {
            'file': {
                'base': 'file',
                'required': True
            },
            'input_2': {
                'base': 'file',
            },
            'optional': {
                'base': 'file',
                'optional': True
            }
        }
    }

    result = job_util.validate_job_against_gear(job_map, gear_doc)

    assert result is False


def test_removing_phi_from_job_map():
    job_map = {
        '_id': bson.ObjectId(),
        'produced_metadata': {'session': {'label': 'hi'}},
        'config': {
            'inputs': {
                'dicom': {
                    'base': 'file',
                    'object': {
                        'info': {'phi': True}
                    }
                }
            }
        }
    }
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get('produced_metadata') is None
    assert clean_job_map['config']['inputs']['dicom']['object'].get('info') is None


def test_removing_phi_from_job_map_without_produced_metadata():
    job_map = {
        '_id': bson.ObjectId(),
        'config': {
            'inputs': {
                'dicom': {
                    'base': 'file',
                    'object': {
                        'info': {'phi': True}
                    }
                }
            }
        }
    }
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get('produced_metadata') is None
    assert clean_job_map['config']['inputs']['dicom']['object'].get('info') is None


def test_removing_phi_from_job_map_without_config():
    job_map = {
        '_id': bson.ObjectId(),
        'produced_metadata': {}
    }
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get('produced_metadata') is None
    assert clean_job_map.get('config') is None

def test_removing_phi_from_job_map_with_config_set_to_None():
    job_map = {
        '_id': bson.ObjectId(),
        'produced_metadata': {},
        'config': None
    }
    clean_job_map = job_util.remove_potential_phi_from_job(job_map)
    assert clean_job_map.get('produced_metadata') is None
    assert clean_job_map.get('config') is None

