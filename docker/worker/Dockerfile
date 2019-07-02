FROM ubuntu:xenial

RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    git-core \
    apt-transport-https

# Install docker
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - \
    && add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable" \
    && apt-get update \
    && apt-get install -y docker-ce

RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y python3.7 python3-pip

RUN pip3 install docker \
    && pip3 install git+https://github.com/milesrichardson/ParsePy.git

WORKDIR /worker

CMD ["python3", "worker.py"]
