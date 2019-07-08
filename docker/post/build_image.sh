#!/bin/bash
# Builds the alaska_sleuth image with appropriate options.
source ../shared.env

# build request image
docker build -t "$DOCKER_REPO:post" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --force-rm \
             post/

# exit with return value of the above command
exit $?
