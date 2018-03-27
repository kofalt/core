FROM python:2.7 as python2

RUN set -eux \
	&& pip install -qq --upgrade pip pymongo>=3.6.0 pylint>=1.8.3 \
    && mkdir -p /var/flywheel/code/sdk/tests

WORKDIR /var/scitran/code/sdk

COPY src/python/tests/requirements.txt /var/scitran/code/sdk/tests/requirements.txt
RUN set -eux \
    && pip install -qq --requirement /var/scitran/code/sdk/tests/requirements.txt

FROM python:3.4 as python3

RUN set -eux \
	&& pip install -qq --upgrade pip pymongo>=3.6.0 pylint>=1.8.3 \
    && mkdir -p /var/flywheel/code/sdk/tests

WORKDIR /var/scitran/code/sdk

COPY src/python/tests/requirements.txt /var/scitran/code/sdk/tests/requirements.txt
RUN set -eux \
    && pip install -qq --requirement /var/scitran/code/sdk/tests/requirements.txt

