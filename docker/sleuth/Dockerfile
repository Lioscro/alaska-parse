FROM lioscro/alaska:base

ARG SLEUTH_VER

##### DEPENDENCIES #####
RUN apt-get update && apt-get install -y \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    gcc

##### R INSTALLATION #####
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9 \
    && add-apt-repository 'deb [arch=amd64,i386] https://cran.rstudio.com/bin/linux/ubuntu xenial/' \
    && apt-get update \
    && apt-get install r-base -y

##### SLEUTH INSTALLATION #####
# copy r script for installing packages
COPY install_sleuth.R /sleuth/install_sleuth.R
RUN Rscript /sleuth/install_sleuth.R $SLEUTH_VER \
    && rm /sleuth/install_sleuth.R

# default port for Sleuth Live
EXPOSE 42427
