#!/bin/bash
# Builds the alaska_kallisto image with appropriate options.
source set_env_variables.sh

# build kallisto image
docker build -t "alaska-kallisto" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --build-arg KALLISTO_URL="$KALLISTO_URL" \
             --force-rm \
             quant/

# exit with return value of the above command
exit $?
