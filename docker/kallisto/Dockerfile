# Kallisto automation using docker container
# UBUNTU VERSION: 16.04 (xenial)
FROM ubuntu:xenial
# Timezone
ARG TIMEZONE=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TIMEZONE /etc/localtime && \
    echo $TIMEZONE > /etc/timezone

# versions
ARG MINICONDA_VER
ARG KALLISTO_VER
ARG MINICONDA3_URL=https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-Linux-x86_64.sh
ARG KALLISTO_URL=https://github.com/pachterlab/kallisto/releases/download/v$KALLISTO_VER/kallisto_linux-v$KALLISTO_VER.tar.gz

##### DEPENDENCIES #####
RUN apt-get update && apt-get install -y \
    curl \
    bzip2 \
    git-core

##### KALLISTO INSTALLATION #####
RUN curl -L $KALLISTO_URL --create-dirs -o /kallisto/kallisto.tar.gz \
    && tar -xvzf /kallisto/kallisto.tar.gz -C /kallisto --strip-components=1 \
    && rm /kallisto/kallisto.tar.gz
# add kallisto to PATH
ENV PATH="/kallisto:${PATH}"

##### MINICONDA (PYTHON) INSTALLATION #####
# fetch miniconda installation script
RUN curl $MINICONDA3_URL --create-dirs -o /downloads/miniconda.sh \
    && chmod +x /downloads/miniconda.sh \
    && /downloads/miniconda.sh -b -f -p /miniconda/ \
    && rm /downloads/miniconda.sh
# add miniconda to PATH
ENV PATH="/miniconda/bin:${PATH}"

RUN pip install git+https://github.com/milesrichardson/ParsePy.git
