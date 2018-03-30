#!/bin/bash
set -ev

if [ "$#" -ne 2 ]; then
	print "Usage: build-sdk.sh <sdk version> <doc version>"
	exit 1
fi

SDK_VERSION=$1
DOC_VERSION=$2

# Build Swagger
swagger/make.sh $DOC_VERSION

# Copy swagger.json into place
cp swagger/build/swagger-codegen.json sdk/swagger.json

# Build SDK
sdk/make.sh $SDK_VERSION

# Test SDK (Python 3.4)
sdk/scripts/docker-tests.sh --image core:testing 

# Test SDK (Python 2.7)
sdk/scripts/docker-tests.sh --image core:testing --python2

# Copy artifacts
mkdir -p dist/
cp sdk/dist/* dist/

