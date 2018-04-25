#!/bin/bash
set -ev

if [ "$#" -ne 0 ]; then
	print "Usage: test-sdk.sh "
	exit 1
fi

# Test SDK (Python 3.4)
sdk/scripts/docker-tests.sh --image core:testing

# Test SDK (Python 2.7)
sdk/scripts/docker-tests.sh --image core:testing --python2
