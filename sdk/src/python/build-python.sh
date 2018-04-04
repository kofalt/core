#!/bin/bash
set -eu

pip install -qq --upgrade pip
pip install -qq -r gen/requirements.txt

# Build sphinx docs
(
	cd sphinx/
	pip install -qq -r requirements-docs.txt
	./build-docs.sh
)


# Build wheel
(
	cd gen/
	python setup.py -q bdist_wheel
)

