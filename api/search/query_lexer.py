"""Lexer module for FlyQL.

See README.md in this module for a description of the language and grammar.

Handles tokenization according to the guidelines in the PLY documentation:
https://www.dabeaz.com/ply/ply.html
"""
import ply.lex


def create_lexer():
    """Create a new lexer using the tokens described in this module.

    Returns:
        lex: The lexer instance
    """
    return ply.lex.lex()


class TokenStr(str):
    """Helper class that tracks whether a generated string token was quoted.

    Attributes:
        token_type (str): The type of token this string was extracted from, either 'id' or 'quoted'
    """

    def __new__(cls, value, token_type):
        obj = str.__new__(cls, value)
        obj.token_type = token_type
        return obj


def _unescape_str(s):
    """Convert escaped characters in a string using UNESCAPE_RULES"""
    for find, replace in UNESCAPE_RULES:
        s = s.replace(find, replace)
    return s


# The list of reserved IDs
# This pattern allows our ID expression to be much cleaner
# Maps lowercase operators to UPPERCASE
reserved = {
    "AND": "AND",
    "and": "AND",
    "OR": "OR",
    "or": "OR",
    "NOT": "NOT",
    "not": "NOT",
    "IN": "IN",
    "in": "IN",
    "LIKE": "LIKE",
    "like": "LIKE",
    "CONTAINS": "CONTAINS",
    "contains": "CONTAINS",
    "exists": "EXISTS",
    "EXISTS": "EXISTS",
    "=": "EQUALS",
    "==": "EQUALS",
    "!=": "NOTEQUALS",
    "<>": "NOTEQUALS",
    "<": "LESSTHAN",
    "<=": "LESSEQUALS",
    ">": "GREATERTHAN",
    ">=": "GREATEREQUALS",
    "=~": "MATCHES",
    "!~": "NOTMATCHES",
}

# The set of token types that make up identifiers in the parser
ID_TOKENS = ("ID", "QUOTED", "UNMATCHED_QUOTE")

# The set of token types that are operators in the parser
OPERATOR_TOKENS = ("EQUALS", "NOTEQUALS", "LESSTHAN", "LESSEQUALS", "GREATERTHAN", "GREATEREQUALS", "MATCHES", "NOTMATCHES", "IN", "LIKE", "CONTAINS")

# The set of characters that cannot be in an unquoted ID field
ID_RESTRICTED_CHARS = ',[]() \t\n\\"'

# Global list of tokens for ply.lex
tokens = ["ID", "QUOTED", "UNMATCHED_QUOTE"] + list(set(reserved.values()))

# Global list of literal characters used by the parser (for ply.lex)
literals = ",[]()"

# The regex matching escaped characters in a quoted string
_STR_ESCAPE = r'(\\[n\\"])'

# Regular expression for quoted string with escaped characters
QUOTED_STR = r'"([^"\\\n]|' + _STR_ESCAPE + ')*"'

# Regular expression for an unterminated quoted string
UNMATCHED_QUOTE_STR = r'("([^"\\\n]|' + _STR_ESCAPE + r')*$|"([^"\\\n]|' + _STR_ESCAPE + r")*\n)"

# The set of replacement rules for escaped characters in a string
# i.e. arguments to str.replace()
UNESCAPE_RULES = (('\\"', '"'), ("\\n", "\n"), ("\\\\", "\\"))

## The rules below are the token specifications ##

# Global list of ignored characters for ply.lex
t_ignore = " \t"

# ID is any string of non-whitespace, non-literal characters
def t_ID(t):
    r'[^\'"\[\]\(\),\s]+'
    t.type = reserved.get(t.value, "ID")
    # Capture token type in value for parser
    t.value = TokenStr(t.value, "id")
    return t


@ply.lex.TOKEN(QUOTED_STR)
def t_QUOTED(t):
    t.value = TokenStr(_unescape_str(t.value[1:-1]), "quoted")
    return t


@ply.lex.TOKEN(UNMATCHED_QUOTE_STR)
def t_UNMATCHED_QUOTE(t):
    t.value = _unescape_str(t.value[1:])
    return t


# Error handler, simply skip offending characters
def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


# Track newlines, as described in the PLY docs
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
