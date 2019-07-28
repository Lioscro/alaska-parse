#!/bin/bash
source ../shared.env

# build qc image
docker build -t "$DOCKER_REPO:qc" \
             --build-arg BOWTIE2_VER="$BOWTIE2_VER" \
             --build-arg SAMTOOLS_VER="$SAMTOOLS_VER" \
             --build-arg RSEQC_VER="$RSEQC_VER" \
             --build-arg FASTQC_VER="$FASTQC_VER" \
             --build-arg MULTIQC_VER="$MULTIQC_VER" \
             --build-arg SAMBAMBA_VER="$SAMBAMBA_VER" \
             --force-rm \
             qc/

# exit with return value of the above command
exit $?
