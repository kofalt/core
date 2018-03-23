[![Build Status](https://travis-ci.org/flywheel-io/core.svg?branch=master)](https://travis-ci.org/flywheel-io/core)
[![Coverage Status](https://codecov.io/gh/flywheel-io/core/branch/master/graph/badge.svg)](https://codecov.io/gh/flywheel-io/core/branch/master)

# SciTran – Scientific Transparency

### Overview

SciTran Core is a RESTful HTTP API, written in Python and backed by MongoDB. It is the central component of the [SciTran data management system](https://scitran.github.io). Its purpose is to enable scientific transparency through secure data management and reproducible processing.


### [Documentation](https://flywheel-io.github.io/core)

API documentation for branches and tags can be found at `https://flywheel-io.github.io/core/branches/<branchname>` and
`https://flywheel-io.github.io/core/tags/<tagname>`.

### [Contributing](https://github.com/flywheel-io/core/blob/master/CONTRIBUTING.md)

### [Testing](https://github.com/flywheel-io/core/blob/master/TESTING.md)

### [License](https://github.com/flywheel-io/core/blob/master/LICENSE)


### Usage
**Currently Python 2 Only**

#### OSX
```
$ ./bin/run-dev-osx.sh --help
```

For the best experience, please upgrade to a recent version of bash.
```
brew install bash bash-completion
sudo dscl . -create /Users/$(whoami) UserShell /usr/local/bin/bash
```

#### Ubuntu
```
mkvirtualenv scitran-core
./bin/install-ubuntu.sh
uwsgi --http :8080 --master --wsgi-file bin/api.wsgi -H $VIRTUAL_ENV \
    --env SCITRAN_PERSISTENT_DB_URI="mongodb://localhost:27017/scitran-core"
```
