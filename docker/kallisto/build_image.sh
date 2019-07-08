#!/bin/bash
# Builds the alaska_kallisto image with appropriate options.
source ../shared.env

# build kallisto image
docker build -t "$DOCKER_REPO:kallisto" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --build-arg KALLISTO_URL="$KALLISTO_URL" \
             --force-rm \
             kallisto/

# exit with return value of the above command
exit $?
