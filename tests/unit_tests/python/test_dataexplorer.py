import copy
import json

import elasticsearch

import api.handlers.dataexplorerhandler as deh


class TransportError(elasticsearch.TransportError):
    def __str__(self):
        return 'TransportError'

def test_search(as_public, as_drone, es, as_user):
    # try to search w/o login
    r = as_public.post('/dataexplorer/search')
    assert r.status_code == 403

    # try to search w/o body
    r = as_drone.post('/dataexplorer/search')
    assert r.status_code == 400

    # try to search w/o return_type in body
    r = as_drone.post('/dataexplorer/search', json={})
    assert r.status_code == 400

    # try to search w/ invalid return_type
    r = as_drone.post('/dataexplorer/search', json={'return_type': 'test'})
    assert r.status_code == 400

    # try to search w/ invalid filters
    r = as_drone.post('/dataexplorer/search', json={'return_type': 'file', 'filters': 'test'})
    assert r.status_code == 400

    # session search against elastic mock
    cont_type, filter_key, filter_value, filter_range, search_str, results = 'session', 'key', 'value', 'range', 'search', 'results'
    es.search.return_value = {'aggregations': {'by_container': {'buckets': [
        {'by_top_hit': {'hits': {'hits': [results]}}},
    ]}}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'search_string': search_str, 'filters': [
        {'terms': {filter_key: filter_value}},
        {'range': filter_range},
    ]})
    es.search.assert_called_with(
        body={
            'size': 0,
            'query': {'bool': {
                'must': {'match': {'all_fields': 'search'}},
                'filter': {'bool': {'must': [
                    {'terms': {filter_key + '.raw': filter_value}},
                    {'range': filter_range},
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'aggs': {'by_container': {'terms':
                {'field': cont_type + '._id', 'size': 100},
                'aggs': {'by_top_hit': {'top_hits': {
                    '_source': deh.SOURCE[cont_type],
                    'size': 1
                }}}
            }}
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == [results]

    # acquisition search
    cont_type = 'acquisition'
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True})
    es.search.assert_called_with(
        body={
            'size': 0,
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'aggs': {'by_container': {'terms':
                {'field': cont_type + '._id', 'size': 100},
                'aggs': {'by_top_hit': {'top_hits': {
                    '_source': deh.SOURCE[cont_type],
                    'size': 1
                }}}
            }}
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == [results]

    # analysis search
    cont_type = 'analysis'
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True})
    es.search.assert_called_with(
        body={
            'size': 0,
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'aggs': {'by_container': {'terms':
                {'field': cont_type + '._id', 'size': 100},
                'aggs': {'by_top_hit': {'top_hits': {
                    '_source': deh.SOURCE[cont_type],
                    'size': 1
                }}}
            }}
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == [results]

    # file search
    cont_type = 'file'
    raw_file_results = [{'fields': {'info_exists': [True]}, '_source': {'file': {}}}]
    formatted_file_results = [{'_source': {'file': {'info_exists': True}}}]
    es.search.return_value = {'hits': {'hits': copy.deepcopy(raw_file_results)}}

    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True})
    es.search.assert_called_with(
        body={
            '_source': deh.SOURCE[cont_type],
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'container_type': cont_type}},
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'script_fields': {'info_exists': deh.INFO_EXISTS_SCRIPT},
            'size': 100},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == formatted_file_results

    # file search w/ search string and filter
    es.search.return_value = {'hits': {'hits': copy.deepcopy(raw_file_results)}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'search_string': search_str, 'filters': [
        {'terms': {filter_key: filter_value}},
        {'range': filter_range},
    ]})
    es.search.assert_called_with(
        body={
            '_source': deh.SOURCE[cont_type],
            'query': {'bool': {
                'must': {'match': {'all_fields': search_str}},
                'filter': {'bool': {'must': [
                    {'term': {'container_type': cont_type}},
                    {'terms': {filter_key + '.raw': filter_value}},
                    {'range': filter_range},
                    {'term': {'deleted': 0}}
                ]}}
            }},
            'script_fields': {'info_exists': deh.INFO_EXISTS_SCRIPT},
            'size': 100},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == formatted_file_results

    # Drone search without self.uid and all_data set to false
    es.search.return_value = {'hits': {'hits': copy.deepcopy(raw_file_results)}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': False, 'search_string': search_str, 'filters': [
        {'terms': {filter_key: filter_value}},
        {'range': filter_range},
    ]})
    es.search.assert_called_with(
        body={
            'query': {
                'bool': {
                    'filter': {
                        'bool': {
                            'must': [
                                {'term': {'container_type': cont_type}},
                                {'terms': {filter_key + '.raw': filter_value}},
                                {'range': filter_range},
                                {'term': {'permissions._id': None}},
                                {'term': {'deleted': 0}}
                            ]
                        }
                    },
                    'must': {
                        'match': {'all_fields': search_str}
                    }
                }
            },
            '_source': deh.SOURCE[cont_type],
            'script_fields': {
                'info_exists': deh.INFO_EXISTS_SCRIPT
            },
            'size': 100
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == formatted_file_results

    # User search without root and all_data set to true
    r = as_user.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'search_string': search_str, 'filters': [
        {'terms': {filter_key: filter_value}},
        {'range': filter_range},
    ]})
    assert r.status_code == 403

    # file search w/ search null filter
    es.search.return_value = {'hits': {'hits': copy.deepcopy(raw_file_results)}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'filters': [
        {'terms': {filter_key: [filter_value, "null"]}},
    ]})
    es.search.assert_called_with(
        body={
            '_source': deh.SOURCE[cont_type],
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'container_type': cont_type}},
                    {'bool':
                        {'should':
                            [
                                {'bool':
                                    {
                                        'must': [
                                            {
                                                'bool': {
                                                    'must_not': [
                                                        {"exists": {"field":filter_key}}
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                },
                                {'terms': {filter_key + '.raw': [filter_value]}}
                            ]
                        }
                    },
                    {'term': {'deleted': 0}}
                ]}}
            }},
            'script_fields': {'info_exists': deh.INFO_EXISTS_SCRIPT},
            'size': 100},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == formatted_file_results

    # file search size=all and filters
    # file search w/ search string and filter
    es.search.return_value = {
        "hits": {
            "total": 0,
            "max_score": 0,
            "hits": []
        },
        "aggregations": {
            "count": {
                "value": 0
            }
        }
    }
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'filters': [
       {'terms': {filter_key: filter_value}},
    ], 'size':"all"})
    es.search.assert_called_with(
        body={
            '_source': deh.SOURCE[cont_type],
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'container_type': cont_type}},
                    {'terms': {filter_key + '.raw': filter_value}},
                    {'term': {'deleted': 0}}
                ]}}
            }},
            'script_fields': {'info_exists': deh.INFO_EXISTS_SCRIPT},
            'size': 1},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok

    # file search size > 10000
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'filters': [
       {'terms': {filter_key: filter_value}},
    ], 'size':"10000000"})
    assert r.status_code == 400

    # Search for training set given a set of nodes
    r = as_drone.post('/dataexplorer/search/training', json={
        'labels': ['file.classifications'],
        'files': [{'parent_id': '123456789009876543211234', 'name': 'example.txt'}],
        'output': {'type': 'project','id': '000000000000000000000000'}
    })
    print(r.json)
    es.mget.assert_called_with(
        body={
            'docs':[
                {
                    '_source': list(set(deh.SOURCE_FILE + ['file.classifications'])),
                    '_id': '123456789009876543211234_example.txt'
                }
            ]
        },
        index='data_explorer')
    assert r.status_code == 404 # the output container doesn't exist

    # Query search
    r = as_drone.post('/dataexplorer/search/training', json={
        'labels': ['file.classifications'],
        'search_query': {'return_type': cont_type, 'all_data': True},
        'output': {'type': 'project','id': '000000000000000000000000'}
    })

    raw_file_results = [{'fields': {'info_exists': [True]}, '_source': {'file': {}}}]
    es.search.return_value = {'hits': {'hits': copy.deepcopy(raw_file_results)}}

    es.search.assert_called_with(
        body={
            '_source': list(set(deh.SOURCE_FILE + ['file.classifications'])),
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    {'term': {'container_type': cont_type}},
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'script_fields': {'info_exists': deh.INFO_EXISTS_SCRIPT},
            'size': 100},
        doc_type='flywheel',
        index='data_explorer')


def test_get_facets(as_public, as_drone, es):
    # try to get facets w/o login
    r = as_public.post('/dataexplorer/facets')
    assert r.status_code == 403

    # get facets w/o sending body
    session_age = 'test'
    es.search.return_value = {'aggregations': {
        'session_age': {'session.age': session_age},
        'by_session': {}}}
    r = as_drone.post('/dataexplorer/facets')
    body = copy.deepcopy(deh.FACET_QUERY)
    body.update({'query': {'match_all': {}}})
    es.search.assert_called_with(body=body, doc_type='flywheel', index='data_explorer')
    assert r.ok
    assert r.json == {'facets': {'by_session': {'session.age': session_age}}}


def test_search_fields(as_public, as_drone, es):
    # try to search fields w/o login
    r = as_public.post('/dataexplorer/search/fields')
    assert r.status_code == 403

    # search fields
    query_field, result_source = 'field', 'source'
    es.search.return_value = {'hits': {'hits': [{'_source': result_source}]}}
    r = as_drone.post('/dataexplorer/search/fields', json={'field': query_field})
    es.search.assert_called_with(
        body={'size': 15, 'query': {'match': {'name': query_field}}},
        doc_type='flywheel_field',
        index='data_explorer_fields')
    assert r.ok
    assert r.json == [result_source]


def test_index_fields(as_public, as_drone, es):
    # try to index fields w/o login
    r = as_public.post('/dataexplorer/index/fields')
    assert r.status_code == 403

    # setup functions for later use in es.indices.exists mock
    indices = set()
    def es_indices_exists(index): return index in indices
    def es_indices_create(index=None, body=None): indices.add(index)
    def es_indices_delete(index): indices.remove(index)

    # try to index fields w/ es unavailable (exc @ exists)
    es.indices.exists.side_effect = TransportError
    r = as_drone.post('/dataexplorer/index/fields')
    assert r.status_code == 404
    es.indices.exists.side_effect = es_indices_exists

    # try to index fields before data_explorer index is available
    r = as_drone.post('/dataexplorer/index/fields')
    es.indices.exists.assert_called_with('data_explorer')
    assert r.status_code == 404
    indices.add('data_explorer')

    # try to (re)index data_explorer_fields w/ hard-reset=true (exc @ delete)
    indices.add('data_explorer_fields')
    es.indices.delete.side_effect = elasticsearch.ElasticsearchException
    r = as_drone.post('/dataexplorer/index/fields?hard-reset=true')
    es.indices.delete.assert_called_with(index='data_explorer_fields')
    assert r.status_code == 500
    es.indices.delete.side_effect = es_indices_delete

    # try to (re)index data_explorer_fields w/ hard-reset=true (exc @ create)
    es.indices.create.side_effect = elasticsearch.ElasticsearchException
    r = as_drone.post('/dataexplorer/index/fields?hard-reset=true')
    es.indices.exists.assert_called_with('data_explorer_fields')
    assert es.indices.create.called
    assert r.status_code == 500
    es.indices.create.side_effect = es_indices_create

    # try to (re)index data_explorer_fields w/ hard-reset=true (exc @ get_mapping)
    es.indices.get_mapping.side_effect = KeyError
    r = as_drone.post('/dataexplorer/index/fields?hard-reset=true')
    assert r.status_code == 404
    es.indices.get_mapping.side_effect = None

    # (re)index data_explorer_fields w/ hard-reset=true
    r = as_drone.post('/dataexplorer/index/fields?hard-reset=true')
    es.indices.create.assert_called_with(index='data_explorer_fields', body={
        'settings': {'number_of_shards': 1, 'number_of_replicas': 0, 'analysis': deh.ANALYSIS},
        'mappings': {'flywheel_field': {'properties': {'all_fields' : {"type": "text"}}, 'dynamic_templates': deh.DYNAMIC_TEMPLATES}}})
    assert r.ok

    # index data_explorer_fields - test ignored fields
    ignored_fields = ['all_fields', 'dynamic_templates', 'analysis_reference', 'file_reference', 'parent', 'container_type', 'origin', 'permissions', '_id']
    fields = {field: None for field in ignored_fields}
    es.indices.get_mapping.return_value = {'data_explorer': {'mappings': {'flywheel': {'properties': fields}}}}
    es.index.reset_mock()
    r = as_drone.post('/dataexplorer/index/fields')
    assert not es.indices.index.called
    assert r.ok

    # index data_explorer_fields - test type "flattening"
    type_map = {
        'string':  ['text', 'keyword'],
        'integer': ['long', 'integer', 'short', 'byte'],
        'float':   ['double', 'float'],
        'date':    ['date'],
        'boolean': ['boolean'],
        'object':  ['object'],
        None:      ['unrecognized'],
        # NOTE _get_field_type returns None for unrecognized field_types
    }
    type_map_r = {vi: k for k, v in type_map.iteritems() for vi in v}
    fields = {k + 'field': {'type': k} for k in type_map_r}
    es.indices.get_mapping.return_value = {'data_explorer': {'mappings': {'flywheel': {'properties': fields}}}}
    es.search.return_value = {'aggregations': {'results': {
        'sum_other_doc_count': 0,
        'buckets': [{'doc_count': 0}]}}}
    es.index.reset_mock()
    r = as_drone.post('/dataexplorer/index/fields')
    for field_name in fields:
        field_type = type_map_r[field_name.replace('field', '')]
        if field_type == 'object':
            continue
        if field_type == 'string':
            es.search.assert_any_call(
                body={'aggs': {'results': {'terms': {'field': field_name + '.raw', 'size': 15}}}, 'size': 0},
                doc_type='flywheel',
                index='data_explorer')
        es.index.assert_any_call(
            body=json.dumps({'name': field_name, 'type': field_type, 'facet': False}),
            doc_type='flywheel_field',
            id=field_name,
            index='data_explorer_fields')
    assert r.ok

    # TODO index data_explorer_fields - test recursion
    # TODO index data_explorer_fields - test facet=True


def test_aggregate_field_values(as_public, as_drone, es):
    # try to get typeadhed w/o login
    r = as_public.post('/dataexplorer/search/fields/aggregate')
    assert r.status_code == 403

    # try to get typeadhed w/o body
    r = as_drone.post('/dataexplorer/search/fields/aggregate')
    assert r.status_code == 400

    # try to get typeadhed for non-existent field
    field_name, search_str, result = 'field', 'search', 'result'
    es.get.side_effect = TransportError
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name})
    assert r.status_code == 404
    es.get.side_effect = None

    # try to get typeadhed for a field type that's not allowed
    es.get.return_value = {'_source': {'type': 'test'}}
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name})
    assert r.status_code == 400

    # get typeahead w/o search string for string|boolean field type
    es.get.return_value = {'_source': {'type': 'string'}}
    es.search.return_value = {'aggregations': {'results': result}}
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name})
    es.search.assert_called_with(
        body={'aggs': {'results': {'terms': {'field': field_name + '.raw', 'size': 15, 'missing': 'null'}}},
              'query': {'bool': {
                'filter': [{'term': {'deleted': 0}}],
                'must': {'match_all': {}}}},
              'size': 0},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json == result

    # get typeahead w/ search string for string|boolean field type
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name, 'search_string': search_str})
    es.search.assert_called_with(
        body={'aggs': {'results': {'terms': {'field': field_name + '.raw', 'size': 15, 'missing': 'null'}}},
              'query': {'bool': {
              'filter': [{'term': {'deleted': 0}}],
              'must': {'match': {'field': search_str}}}},
              'size': 0},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json == result

    # get typeahead w/o search string for integer|float|date field type
    es.get.return_value = {'_source': {'type': 'integer'}}
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name})
    es.search.assert_called_with(
        body={'aggs': {'results': {'stats': {'field': field_name}}},
              'query': {'bool': {
              'filter': [{'term': {'deleted': 0}}],
              'must': {'match_all': {}}}},
              'size': 0},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json == result

    # get typeahead w/ search string for integer|float|date field type
    r = as_drone.post('/dataexplorer/search/fields/aggregate', json={'field_name': field_name, 'search_string': search_str})
    es.search.assert_called_with(
        body={'aggs': {'results': {'stats': {'field': field_name}}},
              'query': {'bool': {
              'filter': [{'term': {'deleted': 0}}],
              'must': {'match': {'field': search_str}}}},
              'size': 0},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json == result

def test_structured_search(as_public, as_drone, es, as_user):
    # try to search w/ invalid syntax
    r = as_drone.post('/dataexplorer/search', json={'return_type': 'file', 'structured_query': 'foo ^^ bar'})
    assert r.status_code == 422

    # session search against elastic mock
    cont_type, results = 'session', 'results'

    query = 'subject.code == amyg_s4'
    query_es = {'bool': {'must': [{'term': {'subject.code.raw': 'amyg_s4'}}]}}

    es.search.return_value = {'aggregations': {'by_container': {'buckets': [
        {'by_top_hit': {'hits': {'hits': [results]}}},
    ]}}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True, 'structured_query': query})
    es.search.assert_called_with(
        body={
            'size': 0,
            'query': {'bool': {
                'filter': {'bool': {'must': [
                    query_es,
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'aggs': {'by_container': {'terms':
                {'field': cont_type + '._id', 'size': 100},
                'aggs': {'by_top_hit': {'top_hits': {
                    '_source': deh.SOURCE[cont_type],
                    'size': 1
                }}}
            }}
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == [results]


    search_str = 'search'
    es.search.return_value = {'aggregations': {'by_container': {'buckets': [
        {'by_top_hit': {'hits': {'hits': [results]}}},
    ]}}}
    r = as_drone.post('/dataexplorer/search', json={'return_type': cont_type, 'all_data': True,
        'search_string': search_str, 'structured_query': query})
    es.search.assert_called_with(
        body={
            'size': 0,
            'query': {'bool': {
                'must': {'match': {'all_fields': search_str}},
                'filter': {'bool': {'must': [
                    query_es,
                    {'term': {'deleted': 0}}
                ]}},
            }},
            'aggs': {'by_container': {'terms':
                {'field': cont_type + '._id', 'size': 100},
                'aggs': {'by_top_hit': {'top_hits': {
                    '_source': deh.SOURCE[cont_type],
                    'size': 1
                }}}
            }}
        },
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json['results'] == [results]

def test_search_suggest(as_public, as_drone, es, as_user):
    query = 'subject.'
    result_source = 'source'
    es.search.return_value = {'hits': {'hits': [{'_source': {'name': result_source}}]}}
    r = as_drone.post('/dataexplorer/search/suggest', json={'structured_query': query})
    es.search.assert_called_with(
        body={'size': 15, 'query': {'match': {'name': 'subject.'}}},
        doc_type='flywheel_field',
        index='data_explorer_fields')
    assert r.ok
    assert r.json == {
        'from': 0,
        'suggestions': [{'display': result_source, 'value': result_source}]
    }

    es.search.reset_mock()
    query = 'subject.code ='
    r = as_drone.post('/dataexplorer/search/suggest', json={'structured_query': query})
    assert not es.search.called
    assert r.ok
    assert r.json == {'from': 0, 'suggestions': []}

    query = 'subject.code == ex'
    results = {'buckets': [ {'key': 'null'}, {'key': 'value_result'}, {'key': 'value "result"'} ]}
    expected_results = [
        {'display': 'value_result', 'value': 'value_result'},
        {'display': 'value "result"', 'value': '"value \\"result\\""'},
    ]
    es.get.return_value = {'_source': {'type': 'string'}}
    es.search.return_value = {'aggregations': {'results': results}}
    r = as_drone.post('/dataexplorer/search/suggest', json={'structured_query': query})
    es.search.assert_called_with(
        body={'aggs': {'results': {'terms': {'field': 'subject.code.raw', 'size': 15, 'missing': 'null'}}},
              'query': {'bool': {
                'filter': [{'term': {'deleted': 0}}],
                'must': {'match': {'subject.code': 'ex'}}}},
              'size': 0},
        doc_type='flywheel',
        index='data_explorer')
    assert r.ok
    assert r.json == {
        'from': 16,
        'suggestions': expected_results
    }
