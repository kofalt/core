#!/usr/bin/env bash

set -e

unset CDPATH
cd "$( dirname "${BASH_SOURCE[0]}" )/.."

SCITRAN_RUNTIME_PATH=${SCITRAN_RUNTIME_PATH:-"./runtime"}

if hash brew 2>/dev/null; then
    echo "Homebrew is installed"
else
    echo "Installing Homebrew"
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    echo "Installed Homebrew"
fi

if brew list | grep -q openssl; then
    echo "OpenSSL is installed"
else
    echo "Installing OpenSSL"
    brew install openssl
    echo "Installed OpenSSL"
fi

if brew list | grep -q "^python$"; then
    echo "Python is installed"
else
    echo "Installing Python"
    brew install python
    echo "Installed Python"
fi

if hash virtualenv 2>/dev/null; then
    echo "Virtualenv is installed"
else
    echo "Installing Virtualenv"
    pip install virtualenv
    echo "Installed Virtualenv"
fi

if [ -d "$SCITRAN_RUNTIME_PATH" ]; then
    echo "Virtualenv exists at $SCITRAN_RUNTIME_PATH"
else
    echo "Creating 'scitran' Virtualenv at $SCITRAN_RUNTIME_PATH"
    virtualenv -p `brew --prefix`/bin/python --prompt="(scitran) " $SCITRAN_RUNTIME_PATH
    echo "Created 'scitran' Virtualenv at $SCITRAN_RUNTIME_PATH"
fi


echo "Activating Virtualenv"
. $SCITRAN_RUNTIME_PATH/bin/activate # will fail with `set -u`


echo "Installing Python requirements"
pip install "pip>=8"
pip install -r requirements.txt


# Install MongoDB
MONGODB_URL="http://downloads.mongodb.org/osx/mongodb-osx-x86_64-v3.2-latest.tgz"
if [ -x "$VIRTUAL_ENV/bin/mongod" ]; then
    MONGODB_VERSION=$($VIRTUAL_ENV/bin/mongod --version | grep "db version" | cut -d "v" -f 3)
    echo "MongoDB version $MONGODB_VERSION is installed"
    echo "Remove $VIRTUAL_ENV/bin/mongod to install latest version"
else
    echo "Installing MongoDB"
    curl $MONGODB_URL | tar xz -C $VIRTUAL_ENV/bin --strip-components 2
    MONGODB_VERSION=$($VIRTUAL_ENV/bin/mongod --version | grep "db version" | cut -d "v" -f 3)
    echo "MongoDB version $MONGODB_VERSION installed"
fi


# Install Node.js
if [ ! -f "$SCITRAN_RUNTIME_PATH/bin/node" ]; then
  echo "Installing Node.js"
  NODE_URL="https://nodejs.org/dist/v6.4.0/node-v6.4.0-darwin-x64.tar.gz"
  curl $NODE_URL | tar xz -C $VIRTUAL_ENV --strip-components 1
fi


# Install testing dependencies
pip install -r "test/integration_tests/requirements.txt"
if [ ! -f "$VIRTUAL_ENV/bin/abao" ]; then
  npm install -g git+https://github.com/flywheel-io/abao.git#better-jsonschema-ref
fi
if [ ! -f "$VIRTUAL_ENV/bin/newman" ]; then
  npm install -g newman@3.0.1
fi
