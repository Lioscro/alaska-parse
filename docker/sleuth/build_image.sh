#!/bin/bash
# Builds the alaska_sleuth image with appropriate options.
source ../shared.env

# build request image
docker build -t "$DOCKER_REPO:sleuth" \
             --build-arg SLEUTH_VER="$SLEUTH_VER" \
             --force-rm \
             sleuth/

# exit with return value of the above command
exit $?
