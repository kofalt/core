# coding=utf-8
import pytest

import api.search

from api.search.ast import *
from api.search.query_parser import lexer
from api.search import ParseError, PartialParseResult

def test_flyql_lexer():
    # Helper function returns a list of tuples of
    # (token type, token value) for comparison
    def lex(s):
        my_lexer = lexer()
        my_lexer.input(s)
        return [(tok.type, tok.value) for tok in my_lexer]

    assert lex('') == []

    # Check that literals don't get picked up by any other token regex
    for literal in '[]()':
        assert lex(literal) == [(literal, literal)]

    assert lex('test_foo.bar') == [('ID', 'test_foo.bar')]
    # Test unicode in symbols
    assert lex('∆') == [('ID', '∆')]
    assert lex(r'"escape\"\\\n"') == [('QUOTED', 'escape"\\\n')]
    assert lex(r'"Quoted String\"\"()[],,,,"') == [('QUOTED', r'Quoted String""()[],,,,')]
    assert lex(r'"Unmatched quote [] \n\"\\') == [('UNMATCHED_QUOTE', 'Unmatched quote [] \n"\\')]
    assert lex('and AND') == [('AND', 'and'), ('AND', 'AND')]
    assert lex('or OR') == [('OR', 'or'), ('OR', 'OR')]
    assert lex('not NOT') == [('NOT', 'not'), ('NOT', 'NOT')]
    assert lex('in IN') == [('IN', 'in'), ('IN', 'IN')]
    assert lex('like LIKE') == [('LIKE', 'like'), ('LIKE', 'LIKE')]
    assert lex('contains CONTAINS') == [('CONTAINS', 'contains'), ('CONTAINS', 'CONTAINS')]
    assert lex('exists EXISTS') == [('EXISTS', 'exists'), ('EXISTS', 'EXISTS')]

    assert lex('<') == [('LESSTHAN', '<')]
    assert lex('<=') == [('LESSEQUALS', '<=')]
    assert lex('=') == [('EQUALS', '=')]
    assert lex('==') == [('EQUALS', '==')]
    assert lex('!=') == [('NOTEQUALS', '!=')]
    assert lex('<>') == [('NOTEQUALS', '<>')]
    assert lex('>') == [('GREATERTHAN', '>')]
    assert lex('>=') == [('GREATEREQUALS', '>=')]
    assert lex('=~') == [('MATCHES', '=~')]
    assert lex('!~') == [('NOTMATCHES', '!~')]

    # Special cases
    assert lex('[a]') == [('[', '['), ('ID', 'a'), (']', ']')]
    assert lex('["a"]') == [('[', '['), ('QUOTED', 'a'), (']', ']')]
    assert lex('[a, b]') == [('[', '['), ('ID', 'a'), (',', ','), ('ID', 'b'), (']', ']')]
    assert lex('[a, "b"]') == [('[', '['), ('ID', 'a'), (',', ','), ('QUOTED', 'b'), (']', ']')]


def test_flyql_parser():
    parse = api.search.parse_query

    # Simple operator term
    assert parse(r'field == "Quoted String"') == Term('==', 'field', 'Quoted String')

    assert parse(r'subject.age == 32') == Term('==', 'subject.age', '32')

    # like operator
    assert parse(r'subject.code LIKE %1001') == Term('like', 'subject.code', '%1001')
    assert parse(r'subject.code LIKE "%1001"') == Term('like', 'subject.code', '%1001')

    # Quoted field, with IN
    assert parse(r'"field name" IN [a]') == Term('in', 'field name', ['a'])
    assert parse(r'"field \"name\"" IN [a, b]') == Term('in', 'field "name"', ['a', 'b'])
    assert parse(r'"field \"name\"" IN [a, b, c]') == Term('in', 'field "name"', ['a', 'b', 'c'])

    assert parse(r'"field name" IN ["a"]') == Term('in', 'field name', ['a'])
    assert parse(r'"field \"name\"" in [a, b, "another value"]') == Term('in', 'field "name"', ['a', 'b', 'another value'])

    assert parse(r'subject.sex == male and subject.age < 37') == And(
        Term('==', 'subject.sex', 'male'), Term('<', 'subject.age', '37'))

    assert parse(r'not (subject.sex == male and subject.age < 37)') == Not(Group(And(
        Term('==', 'subject.sex', 'male'), Term('<', 'subject.age', '37'))))

    assert parse(r'not subject.label contains 666') == Not(Term('contains', 'subject.label', '666'))

    assert parse(r'not subject.race exists AND subject.sex exists') == And(
        Not(Term('exists', 'subject.race', True)), Term('exists', 'subject.sex', True))

    # Operator precedence
    assert parse(r'not a == b or c == "d"') == Or(Not(Term('==', 'a', 'b')), Term('==', 'c', 'd'))

    assert parse(r'a == b or c < d and e =~ f') == Or(
        Term('==', 'a', 'b'), And(Term('<', 'c', 'd'), Term('=~', 'e', 'f')))

    assert parse(r'a < b and c < d or e < f') == Or(
        And(Term('<', 'a', 'b'), Term('<', 'c', 'd')), Term('<', 'e', 'f'))

    # Unmatched quotes
    with pytest.raises(ParseError):
        parse(r'"a == some text')

    with pytest.raises(ParseError):
        parse(r'a == "some text')

    try:
        parse('a\n >> some_text')
        pytest.fail('Expected ParseError')
    except ParseError as e:
        assert len(e.errors) == 1
        err = e.errors[0]
        assert err.line == 2
        assert err.pos == 2
        assert err.offset == 3
        assert err.message == "Unknown operator: '>>'"

    # Test AST repr
    tree = And(Group(Or(Term('=', 'a', 'b'), Term('<', 'c', 'd'))), Not(Term('>', 'e', 'f')))
    assert repr(tree) == ("And(lhs=Group(Or(lhs=Term(op='=' field='a' phrase='b') "
        "rhs=Term(op='<' field='c' phrase='d'))) rhs=Not(Term(op='>' field='e' phrase='f')))")

def test_flyql_partial_parsing():
    # Single expression
    partial = api.search.parse_partial

    assert partial('') == PartialParseResult()
    assert partial(' ') == PartialParseResult()
    assert partial(r'file.inf') == PartialParseResult(0, 'field', 'file.inf')
    assert partial(r'file.info ') == PartialParseResult()
    assert partial(r'field == "foo bar') == PartialParseResult(9, 'phrase', 'foo bar', 'field')
    assert partial(r'field == "foo bar space  ') == PartialParseResult(9, 'phrase', 'foo bar space  ', 'field')
    assert partial(r'field == "foo \"bar\" qaz') == PartialParseResult(9, 'phrase', 'foo "bar" qaz', 'field')
    assert partial(r'field =') == PartialParseResult()
    assert partial(r'(foo') == PartialParseResult(1, 'field', 'foo')
    assert partial(r'foo == bar an') == PartialParseResult()
    assert partial(r'foo == bar and qa') == PartialParseResult(15, 'field', 'qa')
    assert partial(r'foo LIKE %XYZ') == PartialParseResult(9, 'phrase', '%XYZ', 'foo')
    assert partial(r'"') == PartialParseResult(0, 'field', '')
    assert partial(r'foo >= "') == PartialParseResult(7, 'phrase', '', 'foo')
    assert partial(r'foo in [x') == PartialParseResult(8, 'phrase', 'x', 'foo')
    assert partial(r'foo in ["x') == PartialParseResult(8, 'phrase', 'x', 'foo')
    assert partial(r'foo in ["x", "y') == PartialParseResult(13, 'phrase', 'y', 'foo')

    # Test repr
    assert repr(partial(r'foo in ["x", "y')) == "PartialParseResult(pos=13, type=phrase, value=y, last_field=foo)"

def test_flyql_escape_id():
    esc = api.search.escape_id

    assert esc('foo') == 'foo'
    assert esc('foo[]') == '"foo[]"'
    assert esc('"foo\n\\"') == '"\\"foo\\n\\\\\\""'

def test_flyql_to_elastic():
    def to_elastic(q):
        tree = api.search.parse_query(q)
        return api.search.to_es_query(tree)

    # Test term conversion:
    assert to_elastic(r'subject.age = 32') == {'bool': {'must': [{'term': {'subject.age': 32}}]}}
    assert to_elastic(r'subject.age == 32') == {'bool': {'must': [{'term': {'subject.age': 32}}]}}
    assert to_elastic(r'subject.age != 32.5') == {'bool': {'must_not': [{'term': {'subject.age': 32.5}}]}}
    assert to_elastic(r'subject.age <> 32') == {'bool': {'must_not': [{'term': {'subject.age': 32}}]}}

    assert to_elastic(r'subject.age < 32') == {'bool': {'must': [{'range': {'subject.age': {'lt': 32}}}]}}
    assert to_elastic(r'subject.age <= 32') == {'bool': {'must': [{'range': {'subject.age': {'lte': 32}}}]}}
    assert to_elastic(r'subject.age > 32') == {'bool': {'must': [{'range': {'subject.age': {'gt': 32}}}]}}
    assert to_elastic(r'subject.age >= 32') == {'bool': {'must': [{'range': {'subject.age': {'gte': 32}}}]}}

    assert to_elastic(r'subject.species in [mouse, rat]') == {'bool': {'must': [{'terms': {'subject.species.raw': ['mouse', 'rat']}}]}}

    assert to_elastic(r'project.label like Neuro%') == {'bool': {'must': [{'wildcard': {'project.label.raw': 'Neuro*'}}]}}
    assert to_elastic(r'project.label contains science') == {'bool': {'must': [{'match': {'project.label': 'science'}}]}}

    assert to_elastic(r'subject.age exists') == {'bool': {'must': [{'exists': {'field': 'subject.age'}}]}}
    assert to_elastic(r'subject.code =~ ex\d+') == {'bool': {'must': [{'regexp': {'subject.code.raw': r'ex\d+'}}]}}
    assert to_elastic(r'subject.code !~ ex\d+') == {'bool': {'must_not': [{'regexp': {'subject.code.raw': r'ex\d+'}}]}}

    assert to_elastic(r'subject.code == "ex"') == {'bool': {'must': [{'term': {'subject.code.raw': r'ex'}}]}}

    # Bool conversion
    assert to_elastic(r'subject.code != true') == {'bool': {'must_not': [{'term': {'subject.code': True}}]}}
    assert to_elastic(r'subject.code != false') == {'bool': {'must_not': [{'term': {'subject.code': False}}]}}

    # Date conversion
    assert to_elastic(r'subject.created > 2018-01-15') == {'bool': {'must': [{'range': {'subject.created': {'gt': '2018-01-15'}}}]}}
    assert to_elastic(r'subject.created < 2018-01-15T12:03:15') == {'bool': {'must': [{'range': {'subject.created': {'lt': '2018-01-15T12:03:15'}}}]}}
    assert to_elastic(r'subject.created < 2018-01-15T12:03:15.001') == {'bool': {'must': [{'range': {'subject.created': {'lt': '2018-01-15T12:03:15.001'}}}]}}
    assert to_elastic(r'subject.created < 2018-01-15T12:03:15Z') == {'bool': {'must': [{'range': {'subject.created': {'lt': '2018-01-15T12:03:15Z'}}}]}}
    assert to_elastic(r'subject.created < 2018-01-15T12:03:15.001+06:00') == {'bool': {'must': [{'range': {'subject.created': {'lt': '2018-01-15T12:03:15.001+06:00'}}}]}}

    # Not operator
    assert to_elastic(r'not subject.age = 32') == {'bool': {'must_not': [{'term': {'subject.age': 32}}]}}

    # And operator
    assert to_elastic(r'subject.age exists AND subject.code like ex%') == {'bool': {'must': [
        {'exists': {'field': 'subject.age'}},
        {'wildcard': {'subject.code.raw': 'ex*'}}
    ]}}

    # Or operator
    assert to_elastic(r'subject.age exists OR subject.code like ex%') == {'bool': {'should': [
        {'exists': {'field': 'subject.age'}},
        {'wildcard': {'subject.code.raw': 'ex*'}}
    ]}}

    # Group operator
    assert to_elastic(r'(subject.age = 32)') == {'bool': {'must': [{'term': {'subject.age': 32}}]}}

    # Nested logic
    assert to_elastic(r'a = b and c = d or e = f') == {'bool': {'should': [
        {'bool': {'must': [
            {'term': {'a.raw': 'b'}},
            {'term': {'c.raw': 'd'}},
        ]}},
        {'term': {'e.raw': 'f'}}
    ]}}

    assert to_elastic(r'a = b and (c = d or not e = f)') == {'bool': {'must': [
        {'term': {'a.raw': 'b'}},
        {'bool': {'should': [
            {'term': {'c.raw': 'd'}},
            {'bool': {'must_not': [
                {'term': {'e.raw': 'f'}}
            ]}}
        ]}},
    ]}}

    # Invalid node
    with pytest.raises(RuntimeError):
        api.search.to_es_query(object())

    # Invalid operator
    with pytest.raises(RuntimeError):
        term = Term('>>', 'a', 'b')
        api.search.to_es_query(term)
