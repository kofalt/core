#/usr/bin/env python3
import argparse
import datetime
import time

import flywheel

from pprint import pprint


GROUP_ID = 'flyql'
PROJECT_LABEL = 'FlyQL Test'
SUBJECT_CODE = '1001'
SESSION_LABEL = 'session-1'
ACQUISITION_LABEL = 'acquisition-1'

FILENAME_FORMAT = 'file-{}.txt'
FILECOUNT = 5


ERRORS = 0

def filenames():
    for i in range(FILECOUNT):
        yield FILENAME_FORMAT.format(i+1)

def format_set(items):
    if not items:
        return 'Ø'
    return '({})'.format(', '.join(sorted(items)))

def get_acquisition_id(fw):
    try:
        return fw.lookup('/'.join([GROUP_ID, PROJECT_LABEL, SUBJECT_CODE, SESSION_LABEL, ACQUISITION_LABEL]))
    except:
        return None

def create_hierarchy(fw):
    # Create group, project, session, subject, acquisitions
    fw.add_group({'_id': GROUP_ID})
    project_id = fw.add_project({'group': GROUP_ID, 'label': PROJECT_LABEL})
    subject_id = fw.add_subject({'project': project_id, 'code': SUBJECT_CODE})
    session_id = fw.add_session({'project': project_id, 'subject': {'_id': subject_id}, 'label': SESSION_LABEL})
    acquisition_id = fw.add_acquisition({'session': session_id, 'label': ACQUISITION_LABEL})

    for filename in filenames():
        fw.upload_file_to_acquisition(acquisition_id, flywheel.FileSpec(filename, 'Hello World'))

    return fw.get(acquisition_id)

def setup_conditions(fw, acq):
    for i, filename in enumerate(filenames()):
        i = i + 1

        info = {}
        info['text'] = 'file {} text field'.format(i)
        info['integer'] = i
        info['double'] = i * 1.1
        info['boolean'] = bool(i % 2)

        print('Setting info for {}:'.format(filename))
        pprint(info)

        acq.replace_file_info(filename, info)


def suggest(fw, qs, expected_offset, expected_values):
    global ERRORS

    print('SUGGESTIONS: {} : '.format(qs), end='', flush=True)

    try:
        result = fw.get_search_query_suggestions({'structured_query': qs})
    except Exception as e:
        ERRORS += 1
        print('ERROR')
        print('  API Error: {}'.format(e))
        return

    if result._from != expected_offset:
        ERRORS += 1
        print('ERROR')
        print('  Expected offset to be: {}, got: {}'.format(expected_offset, result._from))
        return

    suggested_values = set([s['value'] for s in result['suggestions']])
    if suggested_values == set(expected_values):
        print('OK')
    else:
        ERRORS += 1
        print('ERROR')
        print('  Expected: {}, Got: {}'.format(format_set(expected_values), format_set(suggested_values)))


def search(fw, qs, expected_files):
    global ERRORS

    print('QUERY: {} : '.format(qs), end='', flush=True)
    try:
        results = fw.search({
            'structured_query': qs,
            'return_type': 'file'
        })
    except Exception as e:
        ERRORS += 1
        print('ERROR')
        print('  API Error: {}'.format(e))
        return
    matched_files = set()
    for r in results:
        matched_files.add(r['file']['name'])

    if matched_files == set(expected_files):
        print('OK')
    else:
        ERRORS += 1
        print('ERROR')
        print('  Expected: {}, Got: {}'.format(format_set(expected_files), format_set(matched_files)))

def run_queries(fw, acq):
    all_files = list(filenames())  # Shorthand list of all filenames
    created_time = acq.created.strftime('%Y-%m-%dT%H:%M:%S')

    # Test suggestions
    suggest(fw, 'file.info.bo', 0, ['file.info.boolean'])
    suggest(fw, 'file.info.text == "f', 18, ['"file {} text field"'.format(i+1) for i in range(FILECOUNT)])
    suggest(fw, 'file.name == file', 13, all_files)
    suggest(fw, 'file.name == file-1', 13, ['file-1.txt'])

    # Test search results
    search(fw, 'file.name LIKE file-?.txt', all_files)
    search(fw, 'file.info.text == "file 1 text field"', ['file-1.txt'])
    search(fw, 'file.info.text EXISTS AND file.info.text != "file 1 text field"', ['file-2.txt', 'file-3.txt', 'file-4.txt', 'file-5.txt'])
    search(fw, 'file.info.boolean == true', ['file-1.txt', 'file-3.txt', 'file-5.txt'])
    search(fw, 'file.info.boolean == false', ['file-2.txt', 'file-4.txt'])
    search(fw, 'file.info.text CONTAINS text', all_files)
    search(fw, 'file.name LIKE file-?.txt AND NOT file.info.text CONTAINS text', [])
    search(fw, 'file.name IN [file-1.txt]', ['file-1.txt'])
    search(fw, 'file.name LIKE file-?.txt AND (NOT (file.name IN [file-5.txt, file-3.txt]))', ['file-1.txt', 'file-2.txt', 'file-4.txt'])
    search(fw, 'file.info.integer < 3', ['file-1.txt', 'file-2.txt'])
    search(fw, 'file.info.integer = 3', ['file-3.txt'])
    search(fw, 'file.info.integer > 3', ['file-4.txt', 'file-5.txt'])
    search(fw, 'file.info.integer >= 3', ['file-3.txt', 'file-4.txt', 'file-5.txt'])
    search(fw, 'file.name LIKE file-?.txt and file.created >= {}'.format(created_time), all_files)
    search(fw, 'file.name LIKE file-?.txt and file.created < {}'.format(created_time), [])
    search(fw, 'file.info.double < 3.0', ['file-1.txt', 'file-2.txt'])
    search(fw, 'file.info.double EXISTS', all_files)
    search(fw, r'file.info.text =~ "file [1-5]+ text.*"', all_files)
    search(fw, r'file.name LIKE file-?.txt and file.info.text !~ "file [2-9]+ text.*"', ['file-1.txt'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test FlyQL queries and assumptions')
    parser.add_argument('--skip-setup', action='store_true')

    args = parser.parse_args()

    fw = flywheel.Client()
    fw.api_client.set_version_check_fn(lambda: None)

    acq = get_acquisition_id(fw)

    if not args.skip_setup:
        if acq is None:
            print('Creating hierarchy')
            acq = create_hierarchy(fw)

        print('Setting up conditions...')
        setup_conditions(fw, acq)
        time.sleep(1.0)
    elif acq is None:
        print('Acquisition does NOT exist, run without `--skip-setup`')
        exit(1)

    print('Running queries...')
    run_queries(fw, acq)

    exit(ERRORS)
