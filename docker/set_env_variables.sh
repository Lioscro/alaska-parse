#!/bin/bash
MINICONDA_VER="4.5.12"
BOWTIE2_VER="2.3.5"
SAMTOOLS_VER="1.9"
RSEQC_VER="3.0.0"
FASTQC_VER="0.11.8"
MULTIQC_VER="1.7"
KALLISTO_VER="0.45.0"
SLEUTH_VER="0.30.0"

# Note: some bioconda packages require python2, which is why
#       there is also a link for miniconda 2.
MINICONDA2_URL="https://repo.continuum.io/miniconda/Miniconda2-$MINICONDA_VER-\
Linux-x86_64.sh"
MINICONDA3_URL="https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-\
Linux-x86_64.sh"
KALLISTO_URL="https://github.com/pachterlab/kallisto/releases/download/\
v$KALLISTO_VER/kallisto_linux-v$KALLISTO_VER.tar.gz"
