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
    SCITRAN_SITE_API_URL            URI to a running core instance (including /api)
    SCITRAN_CORE_DRONE_SECRET       API shared secret
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

    log "INFO: Running unit tests ..."
    py.test --exitfirst --cov=api --cov-report= tests/unit_tests/python $PYTEST_ARGS

    log "INFO: Running integration tests ..."
    if [ "${0##*/}" = "run-tests-ubuntu.sh" ]; then
        # Temporary fly/fly backwards compatibility workaround
        # TODO (Ambrus) Remove together with sh symlink
        export SCITRAN_SITE_API_URL=http://localhost:9000/api
        uwsgi --ini /var/scitran/config/uwsgi-config.ini --http [::]:9000 \
            --processes 1 --threads 1 --enable-threads \
            --http-keepalive --so-keepalive --add-header "Connection: Keep-Alive" \
            --logformat '[%(ltime)] "%(method) %(uri) %(proto)" %(status) %(size) request_id=%(request_id)' \
        &
    fi

    touch tests/running_integration
    py.test --exitfirst tests/integration_tests/python $PYTEST_ARGS
    rm tests/running_integration

    log "INFO: Running pylint ..."
    # TODO Enable Refactor and Convention reports
    # TODO Move --disable into rc
    pylint --rcfile=tests/.pylintrc --jobs=4 --reports=no --disable=C,R,W0312,W0141,W0110 api

    # log "Running pep8 ..."
    # pep8 --max-line-length=150 --ignore=E402 api
}


log() {
    printf "\n%s\n" "$@" >&2
}


main "$@"
