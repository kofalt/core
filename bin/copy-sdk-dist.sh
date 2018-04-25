#!/bin/bash
set -ev

if [ "$#" -ne 0 ]; then
	print "Usage: copy-sdk-dist.sh"
	exit 1
fi

# Copy artifacts
mkdir -p dist/
docker run --name sdk_container core:sdk_build /bin/true
docker cp sdk_container:/local/src/python/gen/dist/. dist
docker rm sdk_container

docker run --name gradle_container core:gradle /bin/true
docker cp gradle_container:/local/src/matlab/build/distributions/. dist
docker rm gradle_container
