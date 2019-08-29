"""Provides one-time scripts that fix found issues in the database.

When adding a fix, create a new list for the current
DB version (if it doesn't exist) and add your entry to the back.
That fix will be applied before upgrading from that version to the next.
"""
import datetime

from api import config

from process_cursor import process_cursor

AVAILABLE_FIXES = {
    62: [ 'fix_subject_age_62' ],
    66: [ 'fix_move_flair_from_measurement_to_feature_66' ]
}

def get_available_fixes(db_version, applied_fixes):
    """Get a list of fixes that should be applied for the given db version.

    Args:
        db_version (int): The current db version
        applied_fixes (dict): The set of fixes that have already been applied

    Returns:
        list(str): The list of fix_ids to be applied
    """
    available_fixes = AVAILABLE_FIXES.get(db_version, [])

    result = []
    for fix_id in available_fixes:
        if fix_id not in applied_fixes:
            result.append(fix_id)

    return result

def has_unappliable_fixes(db_version, applied_fixes):
    """Given the current db version, check if there are fixes that cannot be applied.

    Any fix from an earlier schema that has not been applied is considered incompatible.

    Args:
        db_version (int): The current db version
        applied_fixes (dict): The set of fixes that have already been applied

    Returns:
        bool: True if there are incompatible fixes that have not been applied
    """
    found = False
    for i in range(1, db_version):
        available_fixes = AVAILABLE_FIXES.get(i, [])
        for fix_id in available_fixes:
            if fix_id not in applied_fixes:
                config.log.error('The fix %s has never been applied and is ' + \
                        'incompatible with the current schema version: %s',
                        fix_id, str(db_version))
                found = True
    return found

def apply_available_fixes(db_version, applied_fixes, update_doc):
    """
    Applies fixes that need to be run for this database version.

    Adds an entry for each fix that was run to update_doc

    Args:
        db_version (int): The current database version
        applied_fixes (dict): The map of fixes that have already been applied
        update_doc (dict): The document to update with applied fixes.
    """
    available_fixes = get_available_fixes(db_version, applied_fixes)

    for fix_id in available_fixes:
        fix_fn = get_fix_function(fix_id)
        config.log.info('Applying fix: {} ...'.format(fix_id))
        fix_fn()
        config.log.info('Fix {} complete'.format(fix_id))
        update_doc['applied_fixes.{}'.format(fix_id)] = datetime.datetime.now()

def get_fix_function(fix_id):
    """Get a fix function by id.

    Args:
        fix_id (str): The id of the fix function

    Returns:
        function: The fix function

    Raises:
        ValueError: If an invalid fix_id is supplied
    """
    result = globals().get(fix_id, None)
    if not result:
        raise ValueError('Unknown fix method: {}'.format(fix_id))
    return result

def parse_patient_age(age, session_id=None, info_name=None):
    """
    From https://github.com/scitran-apps/dicom-mr-classifier/blob/master/dicom-mr-classifier.py#L45
    Parse patient age from string.
    convert from 70d, 10w, 2m, 1y to datetime.timedelta object.
    Returns age as duration in seconds.
    """
    if age == 'None' or not age:
        return None

    conversion = {  # conversion to days
        'Y': 365,
        'M': 30,
        'W': 7,
        'D': 1,
    }
    scale = age[-1:]
    value = age[:-1]
    if scale not in conversion.keys():
        # Assume years
        scale = 'Y'
        value = age

    try:
        age_in_seconds = datetime.timedelta(int(value) * conversion.get(scale)).total_seconds()
    except ValueError:
        config.log.warning('Parsed age was not an integer for session {} info container {}'.format(session_id, info_name))
        age_in_seconds = None

    # Make sure that the age is reasonable
    if not age_in_seconds or age_in_seconds <= 0:
        age_in_seconds = None

    return age_in_seconds

def set_session_age_from_file_info(session, subject_age):
    session_age = None
    acquisition = config.db.acquisitions.find_one({'session': session['_id'], 'metadata.PatientAge': {'$exists': True}})
    if acquisition:
        session_age = parse_patient_age(acquisition['metadata']['PatientAge'], session_id=session['_id'], info_name=acquisition.get('label'))
    else:
        # Get all the files in each acquisition
        config.log.info('Session {} has no acquisition with PatientAge in its metadata, checking individual files'.format(session['_id']))
        list_of_file_lists = list(map((lambda a: a.get('files', [])), list(config.db.acquisitions.find({'session': session['_id']},{'files': {'$elemMatch': {'info.PatientAge': {'$exists': True}}}}))))
        if list_of_file_lists:
            # Reduce require a nonempty list
            # Reduce the list of lists to a single list and filter out non-dicoms
            files = list(reduce((lambda x, y: x + y), list_of_file_lists))
        else:
            files = []

        if files:
            session_age = parse_patient_age(files[0]['info']['PatientAge'], session_id=session['_id'], info_name=files[0].get('name'))
        else:
            config.log.info('Session {} has no files to derive age from'.format(session['_id']))

    if session_age is not None:
        config.db.sessions.update({'_id': session['_id']}, {'$set': {'age': session_age}})
    return True

def move_subject_age_to_session(subject):
    if config.db.sessions.find({'subject': subject['_id']}).count() == 1:
        # If the subject only has one session use the subject age
        config.db.sessions.update({'subject': subject['_id']}, {'$set': {'age': subject['age']}})
    else:
        # Otherwise we need to find a classifier job for each session
        sessions_without_age = config.db.sessions.find({'subject': subject['_id'], 'age': {'$exists': False}})
        process_cursor(sessions_without_age, set_session_age_from_file_info, subject['age'])

    # Unset the subject age
    config.db.subjects.update({'_id': subject['_id']}, {'$unset': {'age': ''}})
    return True

def fix_subject_age_62():
    """
    Subject age needs to be stored on the session
    Check each subject, if it has a subject age, pop it.
        if there is only one session for that subject, set the age to the popped subject age
        if there are more, set the session age to the session's most recent classifier job's produced metadata subject age
    Not sure what the best way to handle session's that were moved away from their subject
    """
    subjects_with_age = config.db.subjects.find({"age": {"$exists": True}})
    process_cursor(subjects_with_age, move_subject_age_to_session)


def move_flair_for_files_in_doc(container, container_name):
    files = container.get('files', [])
    for file_ in container.get('files', []):
        classification = file_.get('classification') or {}
        measurement = classification.get('Measurement')
        if measurement:
            if 'FLAIR' in measurement:
                measurement.remove('FLAIR')
                if not isinstance(classification.get('Features'), list):
                    classification['Features'] = []
                classification['Features'].append('FLAIR')
    config.db[container_name].update({'_id': container['_id']}, {'$set': {'files': files}})
    return True


def fix_move_flair_from_measurement_to_feature_66():
    """
    Move FLAIR from classification.Measurement to classification.Features
        for MR modality
    """
    collection_names = ['projects', 'subjects', 'sessions', 'acquisitions', 'analyses']
    for collection_name in collection_names:
        cursor = config.db[collection_name].find({'files.classification.Measurement': 'FLAIR'})
        process_cursor(cursor, move_flair_for_files_in_doc, collection_name)

    config.db.modalities.update({'_id': 'MR'}, {'$pull': {'classification.Measurement': 'FLAIR'}})
