#!/bin/bash
source ../shared.env

# build kallisto image
docker build -t "$DOCKER_REPO:index" \
             --build-arg BOWTIE2_VER="$BOWTIE2_VER" \
             --build-arg KALLISTO_URL="$KALLISTO_URL" \
             --force-rm \
             index/

# exit with return value of the above command
exit $?
