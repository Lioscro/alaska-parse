FROM lioscro/alaska:base

ARG BOWTIE2_VER
ARG KALLISTO_VER
ARG KALLISTO_URL=https://github.com/pachterlab/kallisto/releases/download/v$KALLISTO_VER/kallisto_linux-v$KALLISTO_VER.tar.gz

RUN conda install bowtie2==$BOWTIE2_VER

##### KALLISTO INSTALLATION #####
RUN curl -L $KALLISTO_URL --create-dirs -o /kallisto/kallisto.tar.gz \
    && tar -xvzf /kallisto/kallisto.tar.gz -C /kallisto --strip-components=1 \
    && rm /kallisto/kallisto.tar.gz
# add kallisto to PATH
ENV PATH="/kallisto:${PATH}"
