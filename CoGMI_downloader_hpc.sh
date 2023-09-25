#!/bin/bash -l
#SBATCH -J TCIA_Downloader
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH -c 8                 
#SBATCH --time=0-36:00:00
#SBATCH -p batch

# Activates the correct environment
conda activate tcia_downloader

# Name of the collection
collection="QIN GBM Treatment Response"

# Output directory of the final .tar.xz archive
output=$SCRATCH

# Directory of the downloaded folder before compression
temp_dir=$SCRATCH

# Username for TCIA
user="" 

# Password for TCIA
password=""

export SINGULARITY_DOCKER_USERNAME=raphaelmaser@gmail.com
export SINGULARITY_DOCKER_PASSWORD=dckr_pat_2H7B0b4fIYPndw4hl1vXFr72KHs

module load tools/Singularity/3.8.1

singularity pull docker://ydkq4eu2vrqc2uuy8x3c/cogmi_downloader:1.0.0
singularity run \
    --writable-tmpfs \
    --no-home \
    --fakeroot \
    --bind ./output:/downloader/output \
    --bind ./temp_dir:/downloader/temp_dir \
    --bind ./cache_dir:/downloader/cache_dir \
    --bind ./collections.yaml:/downloader/collections.yaml \
    docker://ydkq4eu2vrqc2uuy8x3c/cogmi_downloader:1.0.0 \
    --user $user \
    --password $password \
    --collection UCSF-PDGM \
    --compress \
    #--bids

