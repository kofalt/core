import re

import pytest
from pymongo import errors


def test_master_subject_code(as_public, as_admin, api_db):
    # protected endpoint
    resp = as_public.post('/subjects/master-code', json={'use_patient_id': 'XYZ'})
    assert resp.status_code == 403

    # invalid input payload, no patient id
    resp = as_admin.post('/subjects/master-code', json={'use_patient_id': True})
    assert resp.status_code == 400

    # invalid input payload, no date of birth
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'X',
        'last_name': 'Y'
    })
    assert resp.status_code == 400

    # invalid input payload, invalid date format
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'X',
        'last_name': 'Y',
        'date_of_birth': '1970.01.01'
    })
    assert resp.status_code == 400

    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': ' \n',
        'last_name': '\t\t',
        'date_of_birth': '1980-02-02'
    })
    assert resp.status_code == 400

    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': '   JOHN   ',
        'last_name': '  SMith   ',
        'date_of_birth': '1980-02-02'
    })
    assert resp.status_code == 200
    msc = api_db.master_subject_codes.find_one(
        {'_id': resp.json()['code']}
    )
    assert msc['first_name'] == 'john'
    assert msc['last_name'] == 'smith'
    subj_code_1 = msc['_id']

    # use patient id
    resp = as_admin.post('/subjects/master-code', json={'use_patient_id': True, 'patient_id': 'XYZ'})
    assert resp.status_code == 200
    assert resp.json()['code']
    subj_code_2 = resp.json()['code']
    pattern = re.compile('^fw-[0-9A-Z]{6}$')
    assert bool(pattern.match(subj_code_2))

    # use patient id, but provide additional info, first name, last name, date of birth
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': 'XYZ',
        'first_name': 'First',
        'last_name': 'Last',
        'date_of_birth': '1999-02-02'
    })
    assert resp.status_code == 200
    assert subj_code_2 == resp.json()['code']

    # now we can get the previous subject code via first name, last name, date of birth
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'First',
        'last_name': 'Last',
        'date_of_birth': '1999-02-02'
    })
    assert resp.status_code == 200
    assert subj_code_2 == resp.json()['code']

    # use first name, last name, date of birth
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'X',
        'last_name': 'Y',
        'date_of_birth': '1990-01-01'
    })
    assert resp.status_code == 200
    subj_code_3 = resp.json()['code']

    # we will get the same code, with the same data
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'X',
        'last_name': 'Y',
        'date_of_birth': '1990-01-01'
    })
    assert resp.status_code == 200
    assert subj_code_3 == resp.json()['code']

    # different person with same name and date of birth, but different patient id
    # in this case we need to use the patient id to receive a new master subject code
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': '123456',
        'first_name': 'X',
        'last_name': 'Y',
        'date_of_birth': '1990-01-01'
    })
    assert resp.status_code == 200
    assert subj_code_3 != resp.json()['code']
    subj_code_4 = resp.json()['code']

    # At this point we can't get master subject code for the previous two patient via
    # first name, last name and date of birth because there will be multiple matches
    # in this case we have to use the patient id
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': False,
        'first_name': 'X',
        'last_name': 'Y',
        'date_of_birth': '1990-01-01'
    })
    assert resp.status_code == 400

    # with patient id we still get the correct master subject code
    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': '123456'
    })
    assert resp.status_code == 200
    assert subj_code_4 == resp.json()['code']

    # clean up
    api_db.master_subject_codes.delete_one({'_id': subj_code_1})
    api_db.master_subject_codes.delete_one({'_id': subj_code_2})
    api_db.master_subject_codes.delete_one({'_id': subj_code_3})
    api_db.master_subject_codes.delete_one({'_id': subj_code_4})


def test_master_subject_code_indexes(api_db):
    # master subject codes collection has a unique compound index on first_name, last_name, date_of_birth, patient_id
    api_db.master_subject_codes.insert_one(
        {'_id': 'CCC555', 'first_name': 'A', 'last_name': 'B', 'date_of_birth': '1970-01-01'}
    )
    # can't insert the new patient with the same first/last/dob data without patient id
    with pytest.raises(errors.DuplicateKeyError):
        api_db.master_subject_codes.insert_one(
            {'_id': 'FFF555', 'first_name': 'A', 'last_name': 'B', 'date_of_birth': '1970-01-01'}
        )

    # but can insert the a patient with different first/last/dob data without patient id
    # testing that partial filter expression is set on patient_id
    api_db.master_subject_codes.insert_one(
        {'_id': 'DDD555', 'first_name': 'C', 'last_name': 'D', 'date_of_birth': '1970-01-01'}
    )

    # insert the first patient with patient_id
    api_db.master_subject_codes.insert_one(
        {'_id': 'FFF555', 'first_name': 'A', 'last_name': 'B', 'date_of_birth': '1970-01-01', 'patient_id': 'MRN-11111'}
    )

    # patient id is unique
    with pytest.raises(errors.DuplicateKeyError):
        api_db.master_subject_codes.insert_one(
            {'_id': 'GGG555', 'first_name': 'A', 'last_name': 'B', 'date_of_birth': '1970-01-01',
             'patient_id': 'MRN-11111'}
        )

    # patient id is part of the compound index but it also has a partial unique index
    with pytest.raises(errors.DuplicateKeyError):
        api_db.master_subject_codes.insert_one(
            {'_id': 'GGG555', 'first_name': 'E', 'last_name': 'F', 'date_of_birth': '1970-01-01',
             'patient_id': 'MRN-11111'}
        )

    # same first/last/DOB different patient id
    # at this point we will have three document with the same first/last/DOB, the first one doesn't have patient id
    # the other two have different patient ids
    api_db.master_subject_codes.insert_one(
        {'_id': 'GGG555', 'first_name': 'A', 'last_name': 'B', 'date_of_birth': '1970-01-01', 'patient_id': 'MRN-22222'}
    )

    # clean up
    api_db.master_subject_codes.delete_one({'_id': 'CCC555'})
    api_db.master_subject_codes.delete_one({'_id': 'DDD555'})
    api_db.master_subject_codes.delete_one({'_id': 'FFF555'})
    api_db.master_subject_codes.delete_one({'_id': 'GGG555'})


def test_master_subject_code_verify_endpoint(as_public, as_user, as_admin):
    # login required on this endpoint
    resp = as_public.get('/subjects/master-code/CODE')
    assert resp.status_code == 403

    # code doesn't exist
    resp = as_user.get('/subjects/master-code/CODE')
    assert resp.status_code == 404

    resp = as_admin.post('/subjects/master-code', json={
        'use_patient_id': True,
        'patient_id': 'MRN-12345'
    })
    subj_code = resp.json()['code']

    # code verify sucessfully
    resp = as_user.get('/subjects/master-code/' + subj_code)
    assert resp.ok
