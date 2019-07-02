#!/bin/bash
source set_env_variables.sh

# build qc image
docker build -t "alaska-qc" \
             --build-arg TIMEZONE="$TIMEZONE" \
             --build-arg MINICONDA3_URL="$MINICONDA3_URL" \
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
