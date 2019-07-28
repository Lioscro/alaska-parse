# Base image for Alaska
# Installs miniconda3, docker, and a few shared python libraries by default.
FROM ubuntu:xenial

# versions
ARG MINICONDA_VER
ARG MINICONDA3_URL=https://repo.continuum.io/miniconda/Miniconda3-$MINICONDA_VER-Linux-x86_64.sh
ARG TZ=America/Los_Angeles
ENV TZ=$TZ

# Install dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    apt-utils \
    bzip2 \
    ca-certificates \
    curl \
    git-core \
    software-properties-common \
    tzdata

# Install docker
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - \
    && add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable" \
    && apt-get update \
    && apt-get install -y docker-ce

##### MINICONDA (PYTHON) INSTALLATION #####
# fetch miniconda installation script
RUN curl $MINICONDA3_URL --create-dirs -o /downloads/miniconda.sh \
    && chmod +x /downloads/miniconda.sh \
    && /downloads/miniconda.sh -b -f -p /miniconda/ \
    && rm /downloads/miniconda.sh
# add miniconda to PATH
ENV PATH="/miniconda/bin:${PATH}"

# Set conda channels.
RUN conda config --add channels defaults \
    && conda config --add channels conda-forge \
    && conda config --add channels bioconda

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
