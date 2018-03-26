#!/bin/bash
set -ev

# Parse tag/branch
if [ -n "$TRAVIS_TAG" ]; then
	DOC_VERSION="$TRAVIS_TAG"
	SDK_VERSION="$TRAVIS_TAG"
else 
	# Use short commit ref, instead of $TRAVIS_COMMIT
	COMMIT_REF="$(git rev-parse --short HEAD)"
	DOC_VERSION="$TRAVIS_BRANCH/$COMMIT_REF"
	SDK_VERSION="2.0.0.dev${TRAVIS_BUILD_NUMBER}"
fi

# Build Core
test -f "$DOCKER_DIR/image.tar" && docker load -i "$DOCKER_DIR/image.tar" || true
docker build -t core:base --target base .
docker build -t core:dist --target dist --build-arg VCS_BRANCH="$TRAVIS_BRANCH" --build-arg VCS_COMMIT="$TRAVIS_COMMIT" .
docker build -t core:testing --target testing .
docker save -o "$DOCKER_DIR/image.tar" \
	$(docker history -q core:base | grep -v '<missing>') \
	$(docker history -q core:dist | grep -v '<missing>') \
	$(docker history -q core:testing | grep -v '<missing>')

if [ "$BUILD_SDK" = "false" ]; then
	./tests/bin/docker-tests.sh --image core:testing
fi

# Build Swagger
swagger/make.sh $DOC_VERSION

# Optionally build SDK
if [ "$BUILD_SDK" = "true" ]; then
	# Copy swagger.json into place
	cp swagger/build/swagger-codegen.json sdk/swagger.json
	# Build SDK
	sdk/make.sh $SDK_VERSION
fi

