import bson
from datetime import datetime
import pytest

from api import util

@pytest.fixture(scope='function', params=[
    #range header content       expected_output
    ('bytes=1-5',               [(1, 5)]),
    ('bytes=-5',                [(-5, None)]),
    ('bytes=5-',                [(5, None)]),
    ('bytes=1-5, 6-10, 10-15',  [(1, 5), (6, 10), (10, 15)]),
    ('bytes=-5, 6-, 10-15',     [(-5, None), (6, None), (10, 15)]),
    ('bytes=-',                 util.RangeHeaderParseError),
    ('bytes=3',                 util.RangeHeaderParseError),
    ('bytes=a-b',               util.RangeHeaderParseError),
    ('by-',                     util.RangeHeaderParseError),
    ('bytes=5+5',               util.RangeHeaderParseError),
    ('bytes=5=',                util.RangeHeaderParseError),
    ('b=1-5',                   util.RangeHeaderParseError),
    ('bytes=15, 6-10, 10-15',   util.RangeHeaderParseError),
    ('bytes=15, -6--10, 10-15', util.RangeHeaderParseError),
    ('bytes=1-5; 6-10; 10-15',  util.RangeHeaderParseError),
])
def parse_range_header_fixture(request):
    header, expected_output = request.param
    return header, expected_output


def test_parse_range_header(parse_range_header_fixture):
    range_input, expected_output = parse_range_header_fixture

    if expected_output == util.RangeHeaderParseError:
        with pytest.raises(expected_output):
            util.parse_range_header(range_input)
    else:
        assert util.parse_range_header(range_input) == expected_output


def test_hrsize():
    assert util.hrsize(999) == '999B'
    assert util.hrsize(1000) == '1.0KB'
    for i, suffix in enumerate('KMGTPEZY'):
        assert util.hrsize(2**(10*i + 10)) == '1.0{}B'.format(suffix)
        assert util.hrsize(2**(10*i + 10) * 10) == '10{}B'.format(suffix)
    assert util.hrsize(2**80 * 1000) == '1000YB'


def test_mongo_sanitize_fields():
    obj = object()

    input_fields = {
        1: 1,
        2.0: 2.0,
        'foo.bar$baz': 'foo.bar$baz',
        'list': [1, 2.0, 'foo.bar$baz', obj],
        'obj': obj,
    }

    expected_fields = {
        '1': 1,
        '2_0': 2.0,
        'foo_bar-baz': 'foo.bar$baz',
        'list': [1, 2.0, 'foo_bar-baz', obj],
        'obj': obj,
    }

    assert util.mongo_sanitize_fields(input_fields) == expected_fields


def test_deep_update():
    d = {
        'old': 1,
        'both': 1,
        'dict': {
            'old': 1,
            'both': 1,
        },
    }

    u = {
        'both': 2,
        'new': 2,
        'dict': {
            'both': 2,
            'new': 2,
        },
    }

    util.deep_update(d, u)

    assert d == {
        'old': 1,
        'both': 2,
        'new': 2,
        'dict': {
            'old': 1,
            'both': 2,
            'new': 2,
        },
    }


def test_enum():
    # create test enum class
    TestEnum = util.Enum('TestEnum', {
        'foo': 1,
        'bar': 2,
    })

    # test __eq__
    assert TestEnum.foo == TestEnum.foo
    assert TestEnum.foo == 'foo'
    assert TestEnum.foo == u'foo'

    # test __ne__
    assert TestEnum.foo != TestEnum.bar
    assert TestEnum.foo != 'bar'
    assert TestEnum.foo != u'bar'

    # test __str__
    assert str(TestEnum.foo) == 'foo'

def test_parse_pagination_value():
    assert util.parse_pagination_value('"Brainiac"') == 'Brainiac'
    assert util.parse_pagination_value('"Deadshot') == '"Deadshot'
    assert util.parse_pagination_value('Clayface"') == 'Clayface"'
    assert util.parse_pagination_value('12characters') == '12characters'
    oid = bson.ObjectId()
    assert util.parse_pagination_value(str(oid)) == oid
    datestring = '2019-05-22'
    assert util.parse_pagination_value(datestring) == datetime.strptime(datestring, '%Y-%m-%d')
    assert util.parse_pagination_value('null') == None
    assert util.parse_pagination_value('true') == True
    assert util.parse_pagination_value('false') == False
    assert util.parse_pagination_value('9000') == 9000
    assert util.parse_pagination_value('Bizarro') == 'Bizarro'

def test_parse_pagination_filter_param():
    assert util.parse_pagination_filter_param('label=ex1000') == {'label': {'$eq': 'ex1000'}}
    assert util.parse_pagination_filter_param('age>100') == {'age': {'$gt': 100}}
    assert util.parse_pagination_filter_param('label=~1000') == {'label': {'$regex': '1000'}}
    assert util.parse_pagination_filter_param('label=~1000,age>100') == {'label': {'$regex': '1000'}, 'age': {'$gt': 100}}
    assert util.parse_pagination_filter_param('label=') == {'label': {'$eq': ''}}
    with pytest.raises(util.PaginationParseError):
        util.parse_pagination_filter_param('label') == {}
    with pytest.raises(util.PaginationParseError):
        util.parse_pagination_filter_param('') == {}
