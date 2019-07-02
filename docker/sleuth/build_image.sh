#!/bin/bash
# Builds the alaska_sleuth image with appropriate options.
source set_env_variables.sh

# build request image
docker build -t "alaska-sleuth" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --build-arg SLEUTH_VER="$SLEUTH_VER" \
             --force-rm \
             diff/

# exit with return value of the above command
exit $?
