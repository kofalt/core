FROM node:9-alpine as swagger
WORKDIR /local
ARG DOC_VERSION=0.0.1
COPY swagger ./swagger/
COPY sdk ./sdk/
WORKDIR /local/swagger
ENV npm_config_cache=/npm
RUN npm install && npm run build -- --docs-version=$DOC_VERSION


FROM gradle:4.5-jdk8-alpine as gradle
WORKDIR /local
ENV GRADLE_USER_HOME=/gradle
ARG SDK_VERSION=0.0.1
USER root
COPY sdk .
COPY --from=swagger /local/sdk/swagger.json /local/swagger.json
RUN apk update && apk add git
RUN git clone https://github.com/flywheel-io/JSONio src/matlab/JSONio && cd src/matlab/JSONio && git pull
RUN gradle --no-daemon -PsdkVersion=$SDK_VERSION clean build


FROM python:3.4 as sdk_build
COPY sdk/src /local/src
WORKDIR /local/src
COPY --from=gradle /local/src/python/gen /local/src/python/gen
COPY --from=gradle /local/src/python/sphinx /local/src/python/sphinx
COPY --from=gradle /local/src/matlab/build/gen /local/src/matlab/build/gen
RUN ./build-wheel-and-docs.sh


FROM python:3.4 as docs
COPY sdk /local/sdk
COPY docs /local/docs
WORKDIR /local/docs
COPY --from=swagger /local/sdk/swagger.json /local/gh-pages/docs/swagger/swagger.json
RUN mkdir -p /local/gh-pages/branches && mkdir -p /local/gh-pages/tags
RUN python build-docs.py docs


FROM ubuntu:14.04 as base
ENV TERM=xterm
RUN set -eux \
    && apt-get -yqq update \
    && apt-get -yqq install \
        build-essential \
        ca-certificates \
        curl \
        git \
        libatlas3-base \
        libffi-dev \
        libpcre3 \
        libpcre3-dev \
        libssl-dev \
        numactl \
        python-dev \
        python-pip \
        realpath \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -qq --upgrade pip setuptools wheel \
    && export GNUPGHOME="$(mktemp -d)" \
    && KEYSERVERS="\
        ha.pool.sks-keyservers.net \
        hkp://keyserver.ubuntu.com:80 \
        hkp://p80.pool.sks-keyservers.net:80 \
        keyserver.ubuntu.com \
        pgp.mit.edu" \
    && for server in $(shuf -e $KEYSERVERS); do \
           gpg --keyserver "$server" --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && break || true; \
       done \
    && curl -LSso /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/1.6/gosu-$(dpkg --print-architecture)" \
    && curl -LSso /tmp/gosu.asc "https://github.com/tianon/gosu/releases/download/1.6/gosu-$(dpkg --print-architecture).asc" \
    && gpg --batch --verify /tmp/gosu.asc /usr/local/bin/gosu \
    && chmod +x /usr/local/bin/gosu \
    && rm -rf "$GNUPGHOME" /tmp/gosu.asc \
    && mkdir -p \
        /var/scitran/code/api \
        /var/scitran/config \
        /var/scitran/data \
        /var/scitran/keys \
        /var/scitran/logs \
        /var/scitran/docs

VOLUME /var/scitran/data
VOLUME /var/scitran/keys
VOLUME /var/scitran/logs

WORKDIR /var/scitran

COPY docker/uwsgi-entrypoint.sh /var/scitran/
COPY docker/uwsgi-config.ini    /var/scitran/config/
ENTRYPOINT ["/var/scitran/uwsgi-entrypoint.sh"]
CMD ["uwsgi", "--ini=/var/scitran/config/uwsgi-config.ini", "--http=[::]:9000", \
              "--http-keepalive", "--so-keepalive", "--add-header", "Connection: Keep-Alive"]


FROM base as dist
COPY requirements.txt /var/scitran/code/api/requirements.txt
RUN set -eux \
    && pip install -qq --ignore-installed --requirement /var/scitran/code/api/requirements.txt

COPY . /var/scitran/code/api/
RUN set -eux \
    && pip install -qq --no-deps --editable /var/scitran/code/api

ARG VCS_BRANCH=NULL
ARG VCS_COMMIT=NULL
RUN set -eux \
    && /var/scitran/code/api/bin/build_info.sh $VCS_BRANCH $VCS_COMMIT > /var/scitran/version.json \
    && cat /var/scitran/version.json
COPY --from=sdk_build /local/src/python/sphinx/build /var/scitran/docs/python
COPY --from=sdk_build /local/src/matlab/build/gen/sphinx/build /var/scitran/docs/matlab
COPY --from=swagger /local/swagger/build/swagger-ui /var/scitran/docs/swagger


FROM base as testing
ENV MONGO_VERSION=3.2.9
RUN set -eux \
    && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927 \
    && echo "deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/${MONGO_VERSION%.*} multiverse" > /etc/apt/sources.list.d/mongodb-org-${MONGO_VERSION%.*}.list \
    && apt-get -yqq update \
    && apt-get -yqq install \
        mongodb-org=$MONGO_VERSION \
        mongodb-org-server=$MONGO_VERSION \
        mongodb-org-shell=$MONGO_VERSION \
        mongodb-org-mongos=$MONGO_VERSION \
        mongodb-org-tools=$MONGO_VERSION \
    && rm -rf /var/lib/apt/lists/* /var/lib/mongodb \
    && mkdir -p /data/db

COPY --from=dist /usr/local /usr/local

COPY tests/requirements.txt /var/scitran/code/api/tests/requirements.txt
RUN set -eux \
    && pip install -qq --ignore-installed --requirement /var/scitran/code/api/tests/requirements.txt

COPY --from=dist /var/scitran /var/scitran
