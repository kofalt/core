#!/usr/bin/env bash

set -e

# change to parent dir
unset CDPATH
cd "$( dirname "${BASH_SOURCE[0]}" )/.."

# Transform those rst files into html docs
sphinx-build -a -b html -c sphinx build/gen/sphinx/source build/gen/sphinx/build