#!/usr/bin/env sh

set -eu
unset CDPATH
cd "$( dirname "$0" )/../.."


USAGE="
Usage:
    $0 [OPTION...] [[--] PYTEST_ARGS...]

Runs all tests (unit, integ and linting) if no options are provided.

Assumes running in a flywheel/core:testing container or that core and all
of its dependencies are installed the same way as in the Dockerfile.

Options:
    -h, --help           Print this help and exit

    -s, --shell          Enter shell instead of running tests
    -l, --lint-only      Run linting only
    --py3lint            Run py3k lint profile
    -L, --skip-lint      Skip linting

    PYTEST_ARGS          Arguments passed to py.test

Envvars (required for integration tests):
    SCITRAN_PERSISTENT_DB_URI       Mongo URI to the scitran DB
    SCITRAN_PERSISTENT_DB_LOG_URI   Mongo URI to the scitran log DB
"


main() {
    export PYTHONDONTWRITEBYTECODE=1
    local RUN_SHELL=false
    local LINT_TOGGLE=
    local LINT_PY3K=false

    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                log "$USAGE"
                exit 0
                ;;
            -s|--shell)
                RUN_SHELL=true
                ;;
            -l|--lint-only)
                LINT_TOGGLE=true
                ;;
            -L|--skip-lint)
                LINT_TOGGLE=false
                ;;
            --py3lint)
                LINT_TOGGLE=true
                LINT_PY3K=true
                ;;
            --)
                shift
                break
                ;;
            *)
                break
                ;;
        esac
        shift
    done

    log "INFO: Cleaning pyc and previous coverage results ..."
    for code_dir in api bin tests
    do
        find $code_dir -type d -name __pycache__ -exec rm -rf {} \; || true
        find $code_dir -type f -name '*.pyc' -delete || true
    done
    rm -rf .coverage htmlcov tests/artifacts

    if [ "$LINT_TOGGLE" != true ]; then
        log "INFO: Staring core ..."
        export SCITRAN_CORE_DRONE_SECRET=${SCITRAN_CORE_DRONE_SECRET:-change-me}
        export SCITRAN_PERSISTENT_DATA_PATH=$(mktemp -d)

        ### Temp fix for 3-way split storages, see api.config.local_fs2 for details (section not required for anything else)
        # Pre-creating data_path/v1 folder to enable testing the fix
        mkdir -p $SCITRAN_PERSISTENT_DATA_PATH/v1
        # Setting and pre-creating fs_url
        if [ -z "${SCITRAN_PERSISTENT_FS_URL:-}" ]; then
            export SCITRAN_PERSISTENT_FS_URL=$SCITRAN_PERSISTENT_DATA_PATH/v2
            mkdir -p $SCITRAN_PERSISTENT_FS_URL
        fi

        ###

        export SCITRAN_COLLECT_ENDPOINTS=true
        export SCITRAN_CORE_ACCESS_LOG_ENABLED=true
        export SCITRAN_CORE_LOG_LEVEL=debug
        export SCITRAN_RUNTIME_COVERAGE=true

        gunicorn --reload --workers=1 --log-file=/tmp/core.log -c /src/core/gunicorn_config.py api.app &
        export CORE_PID=$!
        export SCITRAN_SITE_API_URL=http://localhost:8080/api

        if [ $RUN_SHELL = true ]; then
            log "INFO: Entering test shell ..."
            sh
            exit
        fi

        log "INFO: Running unit tests ..."
        python -m pytest --exitfirst --cov=api --cov-report= tests/unit_tests/python "$@" || allow_skip_all

        log "INFO: Running integration tests ..."
        python -m pytest --exitfirst tests/integration_tests/python "$@" || allow_skip_all || tail_logs_and_exit

        log "INFO: Stopping core ..."
        kill $CORE_PID || true
        wait 2>/dev/null

        log "INFO: Collecting coverage ..."
        coverage combine
        coverage html
        coverage xml
        coverage report --skip-covered --show-missing

        touch tests/artifacts
        [ $(id -u) = 0 ] && chown -R $(stat -c %u:%g .) .
    fi

    if [ "$LINT_TOGGLE" != false ]; then
        if [ "$LINT_PY3K" == true ]; then
            log "INFO: Running pylint py3k ..."
            pylint --rcfile=tests/.py3lintrc --jobs=4 --reports=no api
        else
            log "INFO: Running pylint ..."
            # TODO Enable Refactor and Convention reports
            # TODO Move --disable into rc
            pylint --rcfile=tests/.pylintrc --jobs=4 --reports=no --disable=C,R,W0312,W0141,W0110 api

        fi
        # log "INFO: Running pep8 ..."
        # pep8 --max-line-length=150 --ignore=E402 api
    fi
}


allow_skip_all() {
    # Allow pytest exit code 5 when no tests were selected
    local PYTEST_EXIT_CODE=$?
    [ $PYTEST_EXIT_CODE = 5 ] && return 0 \
                              || return $PYTEST_EXIT_CODE
}


tail_logs_and_exit() {
    local PYTEST_EXIT_CODE=$?
    log "INFO: Tailing core logs ..."
    tail -n 100 /tmp/core.log
    exit $PYTEST_EXIT_CODE
}


log() {
    printf "\n%s\n" "$@" >&2
}


main "$@"
