#!/bin/bash
/bin/bash "${BASH_SOURCE%/*}/run-in-docker.sh" gradle --no-daemon build

