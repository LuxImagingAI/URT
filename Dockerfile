FROM --platform=linux/amd64 ruby:slim

SHELL ["/bin/bash", "--login", "-c"]
ENV TZ=Europe/Berlin   
ENV DEBIAN_FRONTEND=noninteractive

# install apt dependencies
RUN apt-get -y update && apt-get -y install curl build-essential procps unzip awscli

# install mambaforge
RUN curl -L "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh" -o "miniforge3.sh" &&\
    bash miniforge3.sh -b -p /condaforge &&\
    /condaforge/bin/conda init bash &&\
    rm "miniforge3.sh"

# Mamba setup
COPY environment.yaml /URT/environment.yaml
RUN conda env create -f /URT/environment.yaml --quiet &&\ 
    conda clean -afy

# Install aspera-cli
RUN gem install aspera-cli -v 4.18.0
RUN /usr/local/bundle/gems/aspera-cli-4.18.0/bin/ascli conf ascp install


# RUN chmod -R a+rwx /condaforge 
RUN    chmod -R a+rwx /root 
# RUN    chmod -R a+rwx /aws 
# RUN    chmod -R a+rwx /tmp

# # Copy files
COPY utils /URT/utils
COPY downloader /URT/downloader
COPY URT.py /URT/URT.py
COPY datasets /URT/datasets
COPY config /URT/config

RUN chmod -R a+rwx /URT

# Create and set the startup script
RUN echo "#!/bin/bash" > /startup.sh &&\
    echo "export HOME=/root" >> /startup.sh &&\
    echo "export PATH=/usr/local/bundle/gems/aspera-cli-4.18.0/bin:/condaforge/bin:$PATH" >> /startup.sh &&\
    echo "cd /URT" >> /startup.sh &&\
    echo "exec conda run --no-capture-output -n URT python URT.py \"\$@\" --output /URT/output --temp_dir /URT/temp --cache_dir /URT/cache" >> /startup.sh &&\
    chmod a+x /startup.sh

ENTRYPOINT ["/startup.sh"]
