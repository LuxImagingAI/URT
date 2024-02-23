FROM debian:bookworm-20231030

# install apt dependencies
RUN apt-get update
RUN apt-get install curl ruby -y 

SHELL ["/bin/bash", "--login", "-c"]

# install mambaforge
RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/Mambaforge-23.3.1-1-Linux-x86_64.sh" &&\
    bash Mambaforge-23.3.1-1-Linux-x86_64.sh -b -p /mambaforge &&\
    /mambaforge/bin/mamba init bash

# Mamba setup
COPY environment.yaml /URT/environment.yaml
RUN mamba env create -f /URT/environment.yaml --quiet

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
COPY utils /URT/utils
COPY downloader /URT/downloader
COPY URT.py /URT/URT.py
COPY datasets /URT/datasets
COPY config /URT/config

RUN chmod -R a+rwx /URT

RUN echo "#!/bin/bash" > /startup.sh &&\
    echo "export HOME=/root" >> /startup.sh &&\
    chmod a+x /startup.sh

ENTRYPOINT ["/bin/bash",  "--login", "-c", "source /startup.sh && cd /URT && /mambaforge/bin/mamba run --no-capture-output -n CoGMI_downloader python URT.py \"$0\" \"$@\" --output /URT/output --temp_dir /URT/temp --cache_dir /URT/cache"]
