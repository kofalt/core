"""Handles partial parsing of FlyQL for the purpose of making suggestions and substitutions"""
from .query_lexer import create_lexer, ID_TOKENS, OPERATOR_TOKENS


class PartialParseResult(object):
    """Represents an approximation of the state of the parser"""
    def __init__(self, pos=0, token_type=None, value=None, last_field=None):
        """Create a new parse result

        Args:
            pos (int): The absolute offset (from 0) of the last parsed token.
            type (str): The type of the last token parsed (either 'field' or 'phrase')
            value (str): The value of the last token parsed
            last_field (str): If the type is 'phrase', then this will be the name of the last field seen.
        """
        self.pos = pos
        """int: The absolute offset (from 0) of the last parsed token."""

        self.type = token_type
        """str: The type of the last token parsed (either 'field' or 'phrase')"""

        self.value = value
        """str: The value of the last token parsed"""

        self.last_field = last_field
        """str: If the type is 'phrase', then this will be the name of the last field seen."""

    def __bool__(self):
        return bool(self.value)

    def __nonzero__(self):
        return bool(self.value)

    def __eq__(self, other):
        return (self.pos == other.pos
                and self.type == other.type
                and self.value == other.value
                and self.last_field == other.last_field)

    def __repr__(self):
        return 'PartialParseResult(pos={}, type={}, value={}, last_field={})'.format(
            self.pos, self.type, self.value, self.last_field)


def parse_partial(query):
    """Parse the given query string, returning the partial parse result.

    The purpose of this function is to indicate what type (if any) of suggestions could
    be made for the current position of the query string, and how much of the
    string needs to be replaced with any selected suggestion string.

    This works by lexing all of the tokens in query, and looking at the last
    few to determine if the parser is in a field or phrase, and what the last
    field seen was.

    Args:
        query (str): The query string to parse

    Returns:
        PartialParseResult: The partial parse result
    """
    # Nothing for empty queries, or a query ending in space
    if not query:
        return PartialParseResult()

    l = create_lexer()
    l.input(query)
    token_list = list(l)

    # No tokens, so no state
    if not token_list:
        return PartialParseResult()

    # The last token was an operator or a comma, so no suggestions can be made
    cur_token = token_list[-1]
    if cur_token.type not in ID_TOKENS:
        return PartialParseResult()

    # Don't offer any suggestions if we're in ignored whitespace
    if cur_token.type != 'UNMATCHED_QUOTE' and query[-1].isspace():
        return PartialParseResult()

    # Shortcut for single field
    if len(token_list) == 1:
        return PartialParseResult(cur_token.lexpos, 'field', cur_token.value)

    # At this point we know that:
    # 1. We have an ID token (either quoted or not)
    # 2. We have at least 2 tokens
    last_token = token_list[-2]
    if last_token.type in ID_TOKENS:
        return PartialParseResult()

    # Determine whether we're field or phrase by looking at the previous token
    # If it's an operator or literal, then we're probably a phrase
    result = PartialParseResult()
    if last_token.type in OPERATOR_TOKENS:
        result = PartialParseResult(cur_token.lexpos, 'phrase', cur_token.value)
    elif last_token.value in '[,':
        result = PartialParseResult(cur_token.lexpos, 'phrase', cur_token.value)
    else:
        result = PartialParseResult(cur_token.lexpos, 'field', cur_token.value)

    # If phrase, find the last referenced field by backtracking
    if result.type == 'phrase':
        # Find the last operator, then field
        found_op = False
        for token in reversed(token_list[:-1]):
            if found_op:
                if token.type in ID_TOKENS:
                    result.last_field = token.value
                    break
            elif token.type in OPERATOR_TOKENS:
                found_op = True

    return result
