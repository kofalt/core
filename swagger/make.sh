#!/bin/bash
set -exo pipefail

if [ "$#" -ge 1 ]; then
	DOC_VERSION="-- --docs-version=$1"
fi

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PERSISTENT_DIR="${PROJECT_DIR}/swagger/persistent"
if [ "$NPM_CACHE" = "" ]; then
	NPM_CACHE="${PERSISTENT_DIR}/.npm"
	mkdir -p $NPM_CACHE
fi

NODE_CONTAINER="node:9-alpine"

# Containerized swagger gen
docker run --rm -it \
	-w /local/swagger \
	-v "${PROJECT_DIR}:/local" \
	-v "${NPM_CACHE}:/npm" \
	-e "npm_config_cache=/npm" \
	${NODE_CONTAINER} /bin/sh -c "npm install && npm run build $DOC_VERSION"
