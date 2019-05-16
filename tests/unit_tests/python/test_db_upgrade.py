import datetime
import os.path
import sys

from mock import Mock, patch
import pytest

bin_path = os.path.join(os.getcwd(), "bin")
sys.path.insert(0, bin_path)
import database
import fixes
import checks

from api import config

CDV = database.CURRENT_DATABASE_VERSION

def test_all_upgrade_scripts_exist():
    for i in range(1, CDV):
        script_name = 'upgrade_to_{}'.format(i)
        assert hasattr(database, script_name)

def test_CDV_was_bumped():
    script_name = 'upgrade_to_{}'.format(CDV+1)
    assert hasattr(database, script_name) is False


@patch('api.config.get_version', Mock(return_value=None))
def test_get_empty_db_version_from_config():
    assert database.get_db_version() == (0, {}, {})

@patch('api.config.get_version', Mock(return_value={'database': 5}))
def test_get_db_version_from_config():
    assert database.get_db_version() == (5, {}, {})


@pytest.fixture(scope='function')
def database_mock_setup():
    setattr(config.db.singletons, 'update_one', Mock())
    for i in range(1, CDV):
        script_name = 'upgrade_to_{}'.format(i)
        setattr(database, script_name, Mock())

    for available_fixes in fixes.AVAILABLE_FIXES.values():
        for fix_id in available_fixes:
            setattr(fixes, fix_id, Mock())

    for check_id in checks.AVAILABLE_CHECKS:
        setattr(checks, check_id, Mock())

@patch('database.get_db_version', Mock(return_value=(0, {}, {})))
def test_all_upgrade_scripts_ran(database_mock_setup, api_db):
    with pytest.raises(SystemExit):
        database.upgrade_schema()
    for i in range(1, CDV):
        script_name = 'upgrade_to_{}'.format(i)
        assert getattr(database, script_name).called

    for available_fixes in fixes.AVAILABLE_FIXES.values():
        for fix_id in available_fixes:
            assert getattr(fixes, fix_id).called

    for check_id in checks.AVAILABLE_CHECKS:
        assert getattr(checks, check_id).called

    # Upgrade Cleanup 
    # After the upgrade scripts run we will have extra providers since those
    # Are needed for all the previous tests. We should either make this test run first
    # For undo any changes that adjust our seed data state
    api_db.providers.delete_one({'label':'Local Storage'})
    api_db.providers.delete_one({'label':'Static Compute'})

@patch('database.get_db_version', Mock(return_value=(CDV-4, {}, {})))
def test_necessary_upgrade_scripts_ran(database_mock_setup):
    with pytest.raises(SystemExit):
        database.upgrade_schema()
    # Assert the necessary scripts were called
    for i in range(CDV-3, CDV):
        script_name = 'upgrade_to_{}'.format(i)
        assert getattr(database, script_name).called

    # Fixes are inclusive of the "current" database version
    for i in range(CDV-4, CDV):
        available_fixes = fixes.AVAILABLE_FIXES.get(i, [])
        for fix_id in available_fixes:
            assert getattr(fixes, fix_id).called

    # But not the scripts before it
    for i in range(1, CDV-4):
        script_name = 'upgrade_to_{}'.format(i)
        assert getattr(database, script_name).called is False

    # Fixes included in the previous version, could have run
    for i in range(1, CDV-5):
        available_fixes = fixes.AVAILABLE_FIXES.get(i, [])
        for fix_id in available_fixes:
            assert getattr(fixes, fix_id).called is False

    for check_id in checks.AVAILABLE_CHECKS:
        assert getattr(checks, check_id).called

def test_has_unappliable_fixes():
    # Single test case - we know that 62 has fixes
    applied_fixes = {}
    assert not fixes.has_unappliable_fixes(62, applied_fixes)
    assert fixes.has_unappliable_fixes(63, applied_fixes)

    applied_fixes = {
        'fix_subject_age_62': datetime.datetime.now()
    }
    assert not fixes.has_unappliable_fixes(63, applied_fixes)
