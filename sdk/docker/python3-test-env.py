#!/bin/bash
set -exo pipefail

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

docker run --rm -it \
	-w /local \
	-v "${PWD}:/local" \
	--net=host \
	-e PYTHONPATH=/local/src/python/flywheel/gen \
	-e SdkTestKey=${SdkTestKey} \
	python:3.6 /bin/bash -c "cd src/python/flywheel/tests; pip install -r requirements.txt; /bin/bash"

