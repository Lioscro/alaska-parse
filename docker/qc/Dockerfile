# Automated quality control docker
# UBUNTU VERSION: 16.04 (xenial)
FROM ubuntu:xenial

# Timezone
ARG TIMEZONE=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TIMEZONE /etc/localtime \
    && echo $TIMEZONE > /etc/timezone

# versions
ARG MINICONDA_VER
ARG MINICONDA3_URL=https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-Linux-x86_64.sh
ARG BOWTIE2_VER=2.3.4
ARG SAMTOOLS_VER=1.7
ARG RSEQC_VER=2.6.4
ARG FASTQC_VER=0.11.6
ARG MULTIQC_VER=1.4
ARG SAMBAMBA_VER=0.6.6

# Install dependencies
RUN apt-get update && apt-get install -y \
    apt-utils \
    bzip2 \
    software-properties-common \
    git-core \
    curl

##### MINICONDA (PYTHON) INSTALLATION #####
# fetch miniconda installation script
RUN curl $MINICONDA3_URL --create-dirs -o /downloads/miniconda.sh \
    && chmod +x /downloads/miniconda.sh \
    && /downloads/miniconda.sh -b -f -p /miniconda/ \
    && rm /downloads/miniconda.sh
# add miniconda to PATH
ENV PATH="/miniconda/bin:${PATH}"

# Add channels.
RUN conda config --add channels defaults \
    && conda config --add channels conda-forge \
    && conda config --add channels bioconda \
    && conda install fontconfig \
    && conda install conda-forge::openjdk \
    && conda install bowtie2==$BOWTIE2_VER \
    && conda install samtools==$SAMTOOLS_VER \
    && conda install fastqc==$FASTQC_VER \
    && conda install rseqc==$RSEQC_VER \
    && conda install multiqc==$MULTIQC_VER \
    && conda install -c r r

RUN pip install git+https://github.com/milesrichardson/ParsePy.git
