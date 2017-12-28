#!/bin/bash
set -exo pipefail

maven_cache_repo="${HOME}/.m2/repository"
mkdir -p "${maven_cache_repo}"

docker run --rm -it \
	-w /local \
	-e MAVEN_CONFIG=/var/maven/.m2 \
	-u "$(id -u):$(id -g)" \
	-v "${PWD}:/local" \
	-v "${maven_cache_repo}:/var/maven/.m2/repository" \
	--entrypoint /local/docker/entrypoint.sh \
	maven:3-jdk-8 "$@"


