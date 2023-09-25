FROM debian:bookworm

# install apt dependencies
RUN apt-get update
RUN apt-get install curl ruby -y


SHELL ["/bin/bash", "--login", "-c"]

# install mambaforge
RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/Mambaforge-23.3.1-1-Linux-x86_64.sh"
RUN bash Mambaforge-23.3.1-1-Linux-x86_64.sh -b &&\
    ~/mambaforge/bin/mamba init bash

# Mamba setup
COPY environment.yaml /downloader/environment.yaml
RUN mamba env create -f /downloader/environment.yaml --quiet

# Install aspera-cli
RUN gem install aspera-cli

# Install ascp
RUN ascli conf ascp install

# Install openneuro downloader
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" &&\
    unzip awscliv2.zip &&\
    ./aws/install

# Copy files
COPY utils /downloader/utils
COPY downloader.py /downloader/downloader.py
COPY datasets /downloader/datasets

WORKDIR /downloader

ENTRYPOINT ["/bin/bash",  "--login", "-c", "mamba run --no-capture-output -n CoGMI_downloader python downloader.py --output /downloader/output --temp_dir /downloader/temp_dir --cache_dir /downloader/cache_dir \"$0\" \"$@\""]



