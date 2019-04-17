"""Provides classes for the Structured Search Syntax Tree"""
class Term(object):
    """Represents a single search term (e.g. comparison operation)"""
    def __init__(self, op, field, phrase):
        """Create a new term.

        Args:
            op (str): The literal operation value
            field (TokenStr): The name of the field being searched
            phrase (TokenStr): The basis for comparison, if provided.
        """

        self.op = op
        """str: The literal operation string"""

        self.field = field
        """TokenStr: The name of the field being searched"""

        self.phrase = phrase
        """TokenStr: The basis for comparsion, if provided."""

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.op == other.op and
                self.field == other.field and
                self.phrase == other.phrase)

    def __repr__(self):
        return "Term(op='{}' field='{}' phrase='{}')".format(
            self.op, self.field, self.phrase)


class UnaryOp(object):
    """Represents a Unary operation or expression (e.g. NOT or Grouping)"""
    def __init__(self, expr):
        """Create a new unary expression.

        Args:
            expr (object): The expression object (term or another op)
        """

        self.expr = expr
        """object: The expression"""

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.expr == other.expr)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, repr(self.expr))


class BinaryOp(object):
    """Represents a Binary expression (e.g. AND or OR)"""
    def __init__(self, lhs, rhs):
        """Create a new binary expression.

        Args:
            lhs (object): The left hand side of the expression
            rhs (object): The right hand side of the expression
        """

        self.lhs = lhs
        """object: The left hand side of the expression"""

        self.rhs = rhs
        """object: The right hand side of the expression"""

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.lhs == other.lhs and
                self.rhs == other.rhs)

    def __repr__(self):
        return '{}(lhs={} rhs={})'.format(type(self).__name__, self.lhs, self.rhs)


class Group(UnaryOp):
    """Unary operation that represents a grouped expression"""


class Not(UnaryOp):
    """Unary operation that represents a negated expression"""


class And(BinaryOp):
    """Binary operation that represents two ANDed expressions"""


class Or(BinaryOp):
    """Binary operation that represents two ORed expressions"""
