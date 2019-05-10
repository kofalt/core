"""Provides one-time scripts that perform consistency checks on the database.

Checks will be applied after all upgrades, regardless of version.
"""

from api import config

from process_cursor import process_cursor

AVAILABLE_CHECKS = [ 'check_for_cas_files' ]

def get_available_checks(applied_checks):
    """Get a list of checks that should be run

    Args:
        applied_checks (dict): The set of checks that have already been applied

    Returns:
        list(str): The list of check_ids to be applied
    """
    result = []
    for check_id in AVAILABLE_CHECKS:
        if check_id not in applied_checks:
            result.append(check_id)

    return result

def apply_available_checks(applied_checks, update_doc):
    """
    Applies checks that need to be run for this database version.

    Adds an entry for each check that was run to update_doc

    Args:
        applied_checks (dict): The map of checks that have already been applied
        update_doc (dict): The document to update with applied checks.
    """
    available_checks = get_available_checks(applied_checks)

    for check_id in available_checks:
        check_fn = get_check_function(check_id)
        config.log.info('Applying check: {} ...'.format(check_id))
        check_fn()
        config.log.info('Check {} complete'.format(check_id))
        update_doc['applied_checks.{}'.format(check_id)] = datetime.datetime.now()

def get_check_function(check_id):
    """Get a check function by id.

    Args:
        check_id (str): The id of the check function

    Returns:
        function: The check function

    Raises:
        ValueError: If an invalid check_id is supplied
    """
    result = globals().get(check_id, None)
    if not result:
        raise ValueError('Unknown check method: {}'.format(check_id))
    return result

def check_for_cas_files():
    """
    Check that all CAS files have been migrated in a system.
    """
    for collection_name in [ 'acquisitions', 'sessions', 'subjects', 'projects', 'analyses', 'collections' ]:
        cursor = config.db[collection_name].find({'files._id': {'$exists': 0}})
        if cursor.count():
            print('\n')
            print('='*80)
            print('\nERROR! CAS Files still exist on this system!')
            print('Please migrate before proceeding with the upgrade.\n')
            print('='*80)
            print('\n')

            raise RuntimeError('Found CAS files in {}'.format(collection_name))
