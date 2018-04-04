#!/bin/bash
set -exo pipefail

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}/" )/.." && pwd )"
PYTHON_CONTAINER="python:3.4"

docker run --rm -it \
	-w /local/docs \
	-v "${PROJECT_DIR}:/local" \
	${PYTHON_CONTAINER} python build-docs.py "$@"

