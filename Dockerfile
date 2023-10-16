FROM debian:bookworm

# install apt dependencies
RUN apt-get update
RUN apt-get install curl ruby -y 

SHELL ["/bin/bash", "--login", "-c"]

# install mambaforge
RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/Mambaforge-23.3.1-1-Linux-x86_64.sh" &&\
    bash Mambaforge-23.3.1-1-Linux-x86_64.sh -b -p /mambaforge &&\
    /mambaforge/bin/mamba init bash

# Mamba setup
COPY environment.yaml /downloader/environment.yaml
RUN mamba env create -f /downloader/environment.yaml --quiet

# Install aspera-cli
RUN gem install aspera-cli &&\
    ascli conf ascp install

# Install openneuro downloader
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" &&\
    unzip awscliv2.zip &&\
    ./aws/install

RUN chmod -R a+rwx /mambaforge &&\
    chmod -R a+rwx /usr &&\
    chmod -R a+rwx /root &&\
    chmod -R a+rwx /aws &&\
    chmod -R a+rwx /tmp

# Copy files
COPY utils /downloader/utils
COPY downloader.py /downloader/downloader.py
COPY datasets /downloader/datasets

RUN chmod -R a+rwx /downloader

RUN echo "#!/bin/bash" > /startup.sh &&\
    echo "export HOME=/root" >> /startup.sh &&\
    chmod a+x /startup.sh

ENTRYPOINT ["/bin/bash",  "--login", "-c", "source /startup.sh && cd /downloader && /mambaforge/bin/mamba run --no-capture-output -n CoGMI_downloader python downloader.py \"$0\" \"$@\" --output /downloader/output --temp_dir /downloader/temp_dir --cache_dir /downloader/cache_dir"]



