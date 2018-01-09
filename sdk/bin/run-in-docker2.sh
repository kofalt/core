#!/bin/bash
set -exo pipefail

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PERSISTENT_DIR="${PROJECT_DIR}/persistent"
gradle_user_home="${PERSISTENT_DIR}/gradle"

mkdir -p "${PERSISTENT_DIR}/gradle"

docker run --rm -it \
	-w /local \
	-u "$(id -u):$(id -g)" \
	-e GRADLE_USER_HOME=/gradle \
	-v "${PWD}:/local" \
	-v "${gradle_user_home}:/gradle" \
	--entrypoint /local/docker/entrypoint2.sh \
	gradle:4.4-jdk8 "$@"


