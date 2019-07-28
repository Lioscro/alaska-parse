#!/bin/bash
source ../shared.env

# build kallisto image
docker build -t "$DOCKER_REPO:base" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --build-arg TZ="$TIMEZONE" \
             --force-rm \
             base/

# exit with return value of the above command
exit $?
