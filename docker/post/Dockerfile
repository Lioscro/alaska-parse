# UBUNTU VERSION: 16.04 (xenial)
FROM ubuntu:xenial
# Timezone
ARG TIMEZONE=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TIMEZONE /etc/localtime && \
    echo $TIMEZONE > /etc/timezone

# default to 4.5.1
ARG MINICONDA_VER
ARG MINICONDA3_URL=https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-Linux-x86_64.sh

##### DEPENDENCIES #####
RUN apt-get update && apt-get install -y \
    bzip2 \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    curl \
    git-core

###### MINICONDA INSTALLATION ######
# fetch miniconda installation script
RUN curl $MINICONDA3_URL --create-dirs -o /downloads/miniconda.sh \
    && chmod +x /downloads/miniconda.sh \
    && /downloads/miniconda.sh -b -f -p /miniconda/ \
    && rm /downloads/miniconda.sh
# add miniconda to PATH
ENV PATH="/miniconda/bin:${PATH}"

# install python libraries
RUN conda install pandas \
    && pip install tissue_enrichment_analysis \
    && pip install git+https://github.com/milesrichardson/ParsePy.git
