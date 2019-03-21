#!/usr/bin/env sh

set -eu
unset CDPATH
cd "$( dirname "$0" )/../.."


USAGE="
Usage:
    $0 [OPTION...] [[--] TEST_ARGS...]

Build flywheel/core image and run tests in a Docker container.
Also displays coverage report and saves HTML under htmlcov/

Options:
    -h, --help          Print this help and exit

    -B, --no-build      Skip rebuilding default Docker image
        --image IMAGE   Use custom Docker image

    TEST_ARGS           Arguments passed to tests.sh

"


main() {
    local DOCKER_IMAGE=
    local RUN_SHELL=

    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                log "$USAGE"
                exit 0
                ;;
            -B|--no-build)
                DOCKER_IMAGE="flywheel/core:testing"
                ;;
            --image)
                DOCKER_IMAGE="$2"
                shift
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

    if [ -z "${DOCKER_IMAGE}" ]; then
        log "Building flywheel/core:testing ..."
        docker build --target testing --tag flywheel/core:testing .
    else
        docker tag "$DOCKER_IMAGE" "flywheel/core:testing"
    fi

    log "INFO: Spinning up dependencies ..."
    trap clean_up EXIT

    docker network create core-test

    docker run -d \
        --name core-test-mongo \
        --network core-test \
        flywheel/core:testing \
        mongod --bind_ip_all

    mkdir -p keys/log_clients
    echo Config >> keys/log_clients/remote_config
    echo Config >> keys/log_clients/ca.pem

    docker run --rm \
        --volume $(pwd):/pwd \
        flywheel/core:testing \
        cp -r /src/core/core.egg-info /pwd/

    docker run -it \
        --name core-test-core \
        --network core-test \
        --volume $(pwd):/src/core \
        --volume $(pwd)/keys:/var/scitran/keys \
        --env SCITRAN_PERSISTENT_DB_URI=mongodb://core-test-mongo:27017/scitran \
        --env SCITRAN_PERSISTENT_DB_LOG_URI=mongodb://core-test-mongo:27017/logs \
        --env FLYWHEEL_FEATURE_MULTIPROJECT=true \
        --env SYSLOG_HOST=localhost \
        --env SCITRAN_PERSISTENT_MULTIPROJECT=true \
        --env SYSLOG_HOST=localhost \
        --workdir /src/core \
        flywheel/core:testing \
        tests/bin/tests.sh "$@"
}


clean_up() {
    local TEST_RESULT_CODE=$?
    set +e

    if [ $TEST_RESULT_CODE = 0 ] && [ -f tests/artifacts ]; then
        log "INFO: Saving test artifacts ..."
        docker cp core-test-core:/src/core/htmlcov .
        docker cp core-test-core:/src/core/coverage.xml .
        docker cp core-test-core:/src/core/endpoints.json .
    fi

    log "INFO: Spinning down dependencies ..."
    docker rm --force --volumes core-test-core
    docker rm --force --volumes core-test-mongo
    docker network rm core-test

    [ "$TEST_RESULT_CODE" = "0" ] && log "INFO: Test return code = $TEST_RESULT_CODE" \
                                  || log "ERROR: Test return code = $TEST_RESULT_CODE"

    rm -rf keys
    exit $TEST_RESULT_CODE
}


log() {
    printf "\n%s\n" "$@" >&2
}


main "$@"
