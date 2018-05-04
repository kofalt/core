#!/bin/bash
set -ev

if [ "$#" -ne 0 ]; then
	print "Usage: build-sdk.sh"
	exit 1
fi

# Copy artifacts
mkdir -p dist/
docker run --name temp_name core:sdk_build /bin/true
docker cp temp_name:/local/src/python/gen/dist/. dist
docker rm temp_name

docker run --name temp_name core:gradle /bin/true
docker cp temp_name:/local/src/matlab/build/distributions/. dist
docker rm temp_name
