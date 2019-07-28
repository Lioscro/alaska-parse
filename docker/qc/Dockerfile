FROM lioscro/alaska:base

ARG BOWTIE2_VER=2.3.4
ARG SAMTOOLS_VER=1.7
ARG RSEQC_VER=2.6.4
ARG FASTQC_VER=0.11.6
ARG MULTIQC_VER=1.4
ARG SAMBAMBA_VER=0.6.6

# Add channels.
RUN conda install fontconfig \
    && conda install conda-forge::openjdk \
    && conda install multiqc==$MULTIQC_VER \
                  bowtie2==$BOWTIE2_VER \
                  samtools==$SAMTOOLS_VER \
                  fastqc==$FASTQC_VER \
                  rseqc==$RSEQC_VER \
    && conda install -c r r
