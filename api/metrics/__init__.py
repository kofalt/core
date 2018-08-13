from .values import SYSTEM_TIMEOUT_ERROR_COUNT, SYSTEM_CONNECTION_RESET_COUNT

# See: https://uwsgi-docs.readthedocs.io/en/latest/PythonModule.html#uwsgi.register_signal
# And: https://uwsgi-docs.readthedocs.io/en/latest/AlarmSubsystem.html

TIMEOUT_ERROR_SIGNAL = 64
CONNECTION_RESET_SIGNAL = 65

def register_signal_handlers():
    """ Register signal handlers for timeout and connection reset errors """
    try:
        import uwsgi
        uwsgi.register_signal(TIMEOUT_ERROR_SIGNAL, 'worker', handle_error_signal)
        uwsgi.register_signal(CONNECTION_RESET_SIGNAL, 'worker', handle_error_signal)
    except ImportError:
        pass

def handle_error_signal(num):
    if num == TIMEOUT_ERROR_SIGNAL:
        SYSTEM_TIMEOUT_ERROR_COUNT.inc()
    elif num == CONNECTION_RESET_SIGNAL:
        SYSTEM_CONNECTION_RESET_COUNT.inc()
