#!/bin/bash
# Builds the alaska_sleuth image with appropriate options.
source ../shared.env

# build request image
docker build -t "$DOCKER_REPO:webhook" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --force-rm \
             webhook/

# exit with return value of the above command
exit $?
