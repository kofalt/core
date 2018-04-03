#!/usr/bin/env sh

set -eu
unset CDPATH
cd "$( dirname "$0" )/../.."


USAGE="
Usage:
    $0 [-- PYTEST_ARGS...]

Runs all tests (unit, integ and linting) if no options are provided.

Assumes running in a flywheel/core:testing container or that core and all
of its dependencies are installed the same way as in the Dockerfile.

Options:
    -h, --help           Print this help and exit
    -- PYTEST_ARGS       Arguments passed to py.test

Envvars (required for integration tests):
    SCITRAN_PERSISTENT_DB_URI       Mongo URI to the scitran DB
    SCITRAN_PERSISTENT_DB_LOG_URI   Mongo URI to the scitran log DB
"


main() {
    export PYTHONDONTWRITEBYTECODE=1
    local PYTEST_ARGS=

    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                log "$USAGE"
                exit 0
                ;;
            --)
                shift
                PYTEST_ARGS="$@"
                break
                ;;
            *)
                log "Invalid argument: $1"
                log "$USAGE"
                exit 1
                ;;
        esac
        shift
    done

    log "INFO: Cleaning pyc and previous coverage results ..."
    find . -type d -name __pycache__ -exec rm -rf {} \;
    find . -type f -name '*.pyc' -delete
    rm -rf .coverage htmlcov

    log "INFO: Staring core ..."
    export SCITRAN_CORE_DRONE_SECRET=${SCITRAN_CORE_DRONE_SECRET:-change-me}
    uwsgi --ini /var/scitran/config/uwsgi-config.ini --http [::]:9000 \
        --env SCITRAN_COLLECT_ENDPOINTS=true \
        --env SCITRAN_CORE_ACCESS_LOG_ENABLED=true \
        --env SCITRAN_CORE_LOG_LEVEL=debug \
        --env SCITRAN_RUNTIME_COVERAGE=true \
        --processes 1 --threads 1 --enable-threads \
        --http-keepalive --so-keepalive --add-header "Connection: Keep-Alive" \
        --logformat '[%(ltime)] "%(method) %(uri) %(proto)" %(status) %(size) request_id=%(request_id)' \
        >/tmp/core.log 2>&1 &
    export CORE_PID=$!
    export SCITRAN_SITE_API_URL=http://localhost:9000/api

    log "INFO: Running unit tests ..."
    # pytest exits with 5 when no tests were selected at all: do not exit prematurely when
    # selecting integration tests via `pytest -k` (and thereby deselecting all unit tests)
    py.test --exitfirst --cov=api --cov-report= tests/unit_tests/python $PYTEST_ARGS || [ $? = 5 ]

    log "INFO: Running integration tests ..."
    py.test --exitfirst tests/integration_tests/python $PYTEST_ARGS || tail_logs_and_exit $?

    log "INFO: Running pylint ..."
    # TODO Enable Refactor and Convention reports
    # TODO Move --disable into rc
    pylint --rcfile=tests/.pylintrc --jobs=4 --reports=no --disable=C,R,W0312,W0141,W0110 api

    # log "INFO: Running pep8 ..."
    # pep8 --max-line-length=150 --ignore=E402 api

    log "INFO: Stopping core ..."
    kill $CORE_PID || true
    wait 2>/dev/null

    log "INFO: Collecting coverage ..."
    coverage combine
    coverage html
    coverage xml
    coverage report --skip-covered --show-missing
}


tail_logs_and_exit() {
    log "INFO: Tailing core logs ..."
    tail --lines=10 /tmp/core.log
    rm -f tests/running_integration

    exit $1
}


log() {
    printf "\n%s\n" "$@" >&2
}


main "$@"
