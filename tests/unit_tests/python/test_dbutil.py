import datetime

from mock import patch

import bson
import pytest

from api.dao.dbutil import _append_parents


def test_filter_no_parents_returns_same():

    filter_ = {'test': 'value', 'test2': 'not container key'}

    res = _append_parents(filter_)

    assert res == filter_
    #assert not parents

def test_filter_with_container_key_is_removed():
    project = 'a_valid_id'
    filter_ = {
        'test': 'value',
        'test2': 'not container key',
        'project': project
    }

    res = _append_parents(filter_)

    assert res != filter_
    assert res.get('project') is None
    assert res['parents.project'] == project


def test_filter_with_all_container_keys_are_removed():

    group = 1234
    project = 'a_valid_id'
    subject = 'another_id'
    session = 'goodtimes'
    acquisition = 'free'
    filter_ = {
        'test': 'value',
        'test2': 'not container key',
        'group': group,
        'project': project,
        'subject': subject,
        'session': session,
        'acquisition': acquisition,
        'value': 'not a container'
    }

    res = _append_parents(filter_)

    assert res != filter_

    assert res.get('group') is None
    assert res.get('project') is None
    assert res.get('subject') is None
    assert res.get('session') is None
    assert res.get('acquisition') is None

    assert res['parents.group'] == group
    assert res['parents.project'] == project
    assert res['parents.subject'] == subject
    assert res['parents.session'] == session
    assert res['parents.acquisition'] == acquisition
