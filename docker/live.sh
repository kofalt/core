#!/usr/bin/env sh

set -eu
unset CDPATH
cd "$( dirname "$0" )/.."

USAGE="
Usage:
    $0 [OPTION...] [[--] TEST_ARGS...]

Build flywheel/core image and run tests in a Docker container.
Also displays coverage report and saves HTML under htmlcov/

Options:
    -h, --help          Print this help and exit

    -B, --no-build      Skip rebuilding default Docker image
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
                DOCKER_IMAGE="flywheel/core:live"
                ;;
            *)
                break
                ;;
        esac
        shift
    done

    if [ -z "${DOCKER_IMAGE}" ]; then
        log "Building flywheel/core:live ..."
        docker build --target live --tag flywheel/core:live .
    fi

    mkdir -p keys/log_clients
    echo Config >> keys/log_clients/remote_config
    echo Config >> keys/log_clients/ca.pem

    docker run --rm \
        --volume $(pwd):/pwd \
        flywheel/core:live \
        cp -r /src/core/core.egg-info /pwd/

    docker run --rm -it \
        --name core-live \
        -p 8080:8080 \
        --volume $(pwd):/src/core \
        --volume $(pwd)/keys:/var/scitran/keys \
        --env SCITRAN_PERSISTENT_DB_URI=mongodb://localhost:27017/scitran \
        --env SCITRAN_PERSISTENT_DB_LOG_URI=mongodb://localhost:27017/logs \
        --env SYSLOG_HOST=localhost \
        flywheel/core:live
}

log() {
    printf "\n%s\n" "$@" >&2
}


main "$@"
