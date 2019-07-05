# UBUNTU VERSION: 16.04 (xenial)
FROM ubuntu:xenial

ARG BOWTIE2_VER
ARG MINICONDA3_VER
ARG KALLISTO_VER
ARG MINICONDA3_URL=https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-Linux-x86_64.sh
ARG KALLISTO_URL=https://github.com/pachterlab/kallisto/releases/download/v$KALLISTO_VER/kallisto_linux-v$KALLISTO_VER.tar.gz

# Install dependencies
RUN apt-get update && apt-get install -y \
    bzip2 \
    software-properties-common \
    curl \
    git-core

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
    && conda install bowtie2==$BOWTIE2_VER

RUN pip install git+https://github.com/milesrichardson/ParsePy.git

##### KALLISTO INSTALLATION #####
RUN curl -L $KALLISTO_URL --create-dirs -o /kallisto/kallisto.tar.gz \
    && tar -xvzf /kallisto/kallisto.tar.gz -C /kallisto --strip-components=1 \
    && rm /kallisto/kallisto.tar.gz
# add kallisto to PATH
ENV PATH="/kallisto:${PATH}"
