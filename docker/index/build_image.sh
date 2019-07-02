#!/bin/bash
source set_env_variables.sh

# build kallisto image
docker build -t "alaska-index" \
             --build-arg BOWTIE2_VER="$BOWTIE2_VER" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
             --build-arg KALLISTO_URL="$KALLISTO_URL" \
             --force-rm \
             index/

# exit with return value of the above command
exit $?
