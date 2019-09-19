import mock

from  api.dao.dbutil import paginate_find

def test_paginate_find_with_filter_in_both_arguments_findwkargs_win():

    # This also confirms that pagination will not override find_kwargs
    find_kwargs = {'filter': {'_id': {'$eq': {'I should win'}}}}
    pagination = {'filter': {'_id': {'$eq': {'I should not be in the filter'}}}}
    # Its a little hacky to permmutate the expected but necessary as its passed as **kwargs
    expected = {'_id': {'$eq': set(['I should win'])}}

    mock_collection = mock.MagicMock()
    paginate_find(mock_collection, find_kwargs, pagination)
    mock_collection.find.assert_called_with(filter=expected)

def test_paginate_find_with_filter_in_both_merges():

    find_kwargs = {'filter': {'_id': {'$eq': {'I should win'}}, 'property': 'remains'}}
    pagination = {'filter': {
        '_id': {'$eq': {'I should not be in the filter'}},
        'another_prop': 'also_remains'}}
    # Its a little hacky to permmutate the expected but until we
    expected_filter = {
        '_id': {'$eq': set(['I should win'])},
        'property': 'remains',
        'another_prop': 'also_remains'}

    mock_collection = mock.MagicMock()
    paginate_find(mock_collection, find_kwargs, pagination)
    mock_collection.find.assert_called_with(filter=expected_filter)
