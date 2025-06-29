#!/bin/sh

. /start/.healthcheck.env

if [ -z "${X_HEALTHCHECK}" ]; then
  exit 0
fi

if [ -z "${X_HEALTHCHECK_SCHEME}" ]; then
  X_HEALTHCHECK_SCHEME=http
fi

if [ -z "${X_HEALTHCHECK_HOST}" ]; then
  X_HEALTHCHECK_HOST=localhost
fi

if [ -z "${X_HEALTHCHECK_PORT}" ]; then
  X_HEALTHCHECK_PORT=9091
fi

wget --quiet --no-check-certificate --tries=1 --spider "${X_HEALTHCHECK_SCHEME}://${X_HEALTHCHECK_HOST}:${X_HEALTHCHECK_PORT}${X_HEALTHCHECK_PATH}/api/health" || exit 1