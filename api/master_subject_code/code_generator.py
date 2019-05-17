import string
from random import SystemRandom


def generate_code(length=6, allowed_chars=string.ascii_uppercase + string.digits, prefix=None):
    """Generate a random code.

    Keyword Arguments:
        length (int) -- Length of the random part (default: {6})
        allowed_chars (string) -- Allowed characters (default: {string.ascii_uppercase+string.digits})
        prefix (string) -- Prefix of the code (default: {None})

    Returns:
        string -- The generated code
    """

    random = SystemRandom()
    code = "".join(random.choice(allowed_chars) for _ in range(length))
    if prefix:
        return "{}-{}".format(prefix, code)
    else:
        return code
