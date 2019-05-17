import pytest
from api.data_views import safe_eval


def assert_invalid_expr(expr, variables=None):
    try:
        safe_eval.compile_expr(expr, variables)
        pytest.fail("Expected ValueError")
    except ValueError:
        pass


def test_safe_eval():
    assert safe_eval.compile_expr("z+1/y", {"x", "y", "z"})

    expr = safe_eval.compile_expr("x+1")
    assert expr.eval({"x": 10}) == 11

    expr = safe_eval.compile_expr("(x+1)*(y+3)")
    assert expr.eval({"x": 1, "y": 2}) == 10

    try:
        expr.eval({})
        pytest.fail("Expected ValueError")
    except ValueError:
        pass

    expr = safe_eval.compile_expr("0x10")
    assert expr.eval({}) == 16

    assert_invalid_expr("9**9**9")
    assert_invalid_expr('print "Hello World"')
    assert_invalid_expr('print("Hello World")')
    assert_invalid_expr('"test"')
    assert_invalid_expr("3 if x else 4")
    assert_invalid_expr("import platform;print(platform.version())")
    assert_invalid_expr("None", {"x"})
    assert_invalid_expr("z+1", {"x", "y"})
