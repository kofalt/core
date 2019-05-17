"""Provide safe evaluation of simple math formulas"""
import ast
import operator

# Decided against something like asteval to 1. Reduce dependencies, 2. Not introduce risk
# Loosely based on solution here:
# https://stackoverflow.com/questions/26505420/evaluate-math-equations-from-unsafe-user-input-in-python
# Restricted even further to only allow arithmetic operations

SAFE_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.div}


class CompiledExpression(object):
    """Represents a prepared safe expression, ready for evaluation"""

    def __init__(self, node):
        """Create a compiled expression instance.

        Arguments:
            node (ast.AST): The root node of the expression
        """
        self.node = node

    def eval(self, variables):
        """Evaluate the expression, substituting variables for name nodes

        Arguments:
            variables (dict): The map of variable id to value
        """
        try:
            return _safe_eval_expr(self.node, variables)
        except KeyError:
            raise ValueError("Unknown variable")


def compile_expr(expr, variables=None):
    """Compile string expr into a CompiledExpression
    
    Also validates that every name node is present in variables, if provided.
        
    Arguments:
        variables (set): The set of variables available to the expression
    """
    # Parse
    try:
        node = ast.parse(expr, "<string>", "eval").body
    except SyntaxError as ex:
        raise ValueError("Invalid syntax: {}".format(ex))

    # Quick validation of operations
    _validate_expr(node, variables)

    return CompiledExpression(node)


def _validate_expr(node, variables=None):
    """Validate that the AST uses only supported operations and variables.

    Arguments:
        node (ast.AST): The root expression
        variables (set): The set of variables available to the expression
    """
    if isinstance(node, ast.Num):
        return

    if isinstance(node, ast.Name):
        if variables and node.id not in variables:
            raise ValueError("Unexpected variable: {}".format(node.id))
        return

    if isinstance(node, ast.BinOp):
        if node.op.__class__ not in SAFE_OPS:
            raise ValueError("Unsafe operator")
        _validate_expr(node.left, variables)
        _validate_expr(node.right, variables)
        return

    raise ValueError("Unsafe operation")


def _safe_eval_expr(node, variables):
    """Evaluate an expression, returning a result.

    Arguments:
        node (ast.AST): The root expression
        variables (dict): The map of variables available to the expression

    Returns:
        number: The result of the expression
    """
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Name):
        return variables[node.id]
    elif isinstance(node, ast.BinOp):
        op = SAFE_OPS[node.op.__class__]
        lhs = _safe_eval_expr(node.left, variables)
        rhs = _safe_eval_expr(node.right, variables)
        return op(lhs, rhs)
    return None
