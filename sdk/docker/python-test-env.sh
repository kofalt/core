#!/bin/bash
set -exo pipefail

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

docker run --rm -it \
	-w /local \
	-v "${PWD}:/local" \
	--net=host \
	-e PYTHONPATH=/local/src/python/gen \
	-e SdkTestKey=${SdkTestKey} \
	python:2.7 /bin/bash -c "cd src/python/tests; pip install -r requirements.txt; /bin/bash"

