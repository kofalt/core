"""Parser module for FlyQL.

See README.md in this module for a description of the language and grammar.

Handles parsing according to the guidelines in the PLY documentation:
https://www.dabeaz.com/ply/ply.html

And produces an abstract syntax tree composed of the classes in the ast submodule.
"""
import threading

import ply.yacc

from . import ast
from .query_lexer import create_lexer, tokens, ID_RESTRICTED_CHARS, UNESCAPE_RULES  # pylint: disable=unused-import


thread_local = threading.local()


def parse_query(query):
    """Parse the given query string, returning a syntax tree.

    Args:
        query (str): The query string

    Returns:
        object: The syntax tree, constructed from classes in the ast submodule.

    Raises:
        ParseError: If any parse errors occurred.
    """
    p = parser()

    result = p.parse(query, lexer=lexer())
    if p.syntax_errors:
        raise ParseError(p.syntax_errors)

    return result


def escape_id(s):
    """Escape the string s if it contains any restricted characters

    Args:
        s (str): The string to escape

    Returns:
        str: The (potentially) escaped string
    """
    for c in ID_RESTRICTED_CHARS:
        if c in s:
            for replace, find in reversed(UNESCAPE_RULES):
                s = s.replace(find, replace)
            return '"' + s + '"'
    return s


def lexer():
    """Get or create a single lexer for the current thread of execution"""
    if getattr(thread_local, 'lexer', None) is None:
        thread_local.lexer = create_lexer()
    return thread_local.lexer


def parser():
    """Get or create a single parser for the current thread of execution"""
    if getattr(thread_local, 'parser', None) is None:
        thread_local.parser = ply.yacc.yacc()

    thread_local.parser.syntax_errors = []
    return thread_local.parser


class ParseErrorMessage(object):
    """Represents a single parser error."""
    def __init__(self, offset, line, pos, message):
        """Construct a parer error message.

        Args:
            offset (int): The absolute offset (0-indexed) in the input where the error occurred.
            line (int): The logical line (1-indexed) where the error occurred.
            pos (int): The logical column (1-indexed) where the error occurred.
            message (str): A description of the error
        """
        self.offset = offset
        """int: The absolute offset (0-indexed) in the input where the error occurred."""

        self.line = line
        """int: The logical line (1-indexed) where the error occurred."""

        self.pos = pos
        """int: The logical column (1-indexed) where the error occurred."""

        self.message = message
        """str: A description of the error"""

    def to_dict(self):
        """Convert the error message to a JSON-convertible dictionary.

        Returns:
            dict: A dictionary representation of the error
        """
        return {
            'line': self.line,
            'pos': self.pos,
            'offset': self.offset,
            'message': self.message
        }

    def __str__(self):
        return '{}:{} - {}'.format(self.line, self.pos, self.message)


class ParseError(Exception):
    """Exception raised when one or more parse errors occur."""
    def __init__(self, errors):
        """Create a new parse error from the given error list.

        Args:
            errors (list(ParseErrorMessage)): The list of parse errors
        """
        super(ParseError, self).__init__()

        self.errors = errors
        """list(ParseErrorMessage): The list of parse errors"""

    def __str__(self):
        return '\n'.join([str(err) for err in self.errors])


def _add_error(message, token=None, idx=1):
    """Add an error to the thread-local parser instance.

    If no token is specified, then the current lexer position will be used.

    Args:
        message (str): The error description
        token (Token): The parse tokens, if available
        idx (int): The index of the token where the error occurred, if available.
    """
    lex = lexer()

    if token is not None:
        line = token.lineno(idx)
        lexpos = token.lexpos(idx)
    else:
        line = lex.lineno
        lexpos = lex.lexpos

    line_start = lex.lexdata.rfind('\n', 0, lexpos) + 1
    pos = (lexpos - line_start) + 1

    parser().syntax_errors.append(ParseErrorMessage(lexpos, line, pos, message))


## The following are grammar productions for the query parser
## See PLY documentation for details on how these are specified

# Indicate operator precedence to the parser
precedence = [
    ('left', 'OR'),
    ('left', 'AND')
]


def p_expression_and(p):
    '''expression : expression AND expression'''
    p[0] = ast.And(p[1], p[3])


def p_expression_or(p):
    '''expression : expression OR expression'''
    p[0] = ast.Or(p[1], p[3])


def p_expression_unary(p):
    '''expression : unary_expression'''
    p[0] = p[1]


def p_expression_group(p):
    '''unary_expression : '(' expression ')' '''
    p[0] = ast.Group(p[2])


def p_expression_not(p):
    '''unary_expression : NOT unary_expression'''
    p[0] = ast.Not(p[2])


def p_expression_term(p):
    '''unary_expression : term'''
    p[0] = p[1]


def p_term_in(p):
    '''term : field IN list'''
    p[0] = ast.Term('in', p[1], p[3])


def p_term_like(p):
    '''term : field LIKE phrase'''
    p[0] = ast.Term('like', p[1], p[3])


def p_term_contains(p):
    '''term : field CONTAINS phrase'''
    p[0] = ast.Term('contains', p[1], p[3])


def p_term_binary(p):
    '''term : field operator phrase'''
    p[0] = ast.Term(p[2], p[1], p[3])


def p_term_exists(p):
    '''term : field EXISTS'''
    p[0] = ast.Term('exists', p[1], True)


def p_term_error_1(p):
    '''term : field error'''
    _add_error("Unknown operator: '{}'".format(p[2].value), p, 2)


def p_operator(p):
    '''operator : EQUALS
                | NOTEQUALS
                | LESSTHAN
                | LESSEQUALS
                | GREATERTHAN
                | GREATEREQUALS
                | MATCHES
                | NOTMATCHES'''
    p[0] = p[1]


def p_list(p):
    '''list : '[' list_items ']' '''
    p[0] = p[2]


def p_list_items(p):
    '''list_items : phrase
                  | list_items ',' phrase'''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1]
        p[0].append(p[3])


def p_field(p):
    '''field : ID
              | QUOTED'''
    p[0] = p[1]


def p_phrase(p):
    '''phrase : ID
              | QUOTED'''
    p[0] = p[1]


def p_field_unmatched(p):  # pylint: disable=unused-argument
    '''field : UNMATCHED_QUOTE'''
    _add_error("Expected '\"'", p)


def p_phrase_unmatched(p):  # pylint: disable=unused-argument
    '''phrase : UNMATCHED_QUOTE'''
    _add_error("Expected '\"'", p)


def p_error(p):
    if p is not None:
        _add_error("Syntax error at '{}'".format(p))
    else:
        _add_error('Unexpected end of input!')
