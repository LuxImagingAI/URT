#!/bin/bash -l
#SBATCH -J TCIA_Downloader
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH -c 8                 
#SBATCH --time=0-36:00:00
#SBATCH -p batch

conda activate CoGMI_downloader

# Name of the collection
collection="UCSF-PDGM"

# Output directory of the final .tar.xz archive
output=$SCRATCH/output

# Directory of the downloaded folder before compression
temp_dir=$SCRATCH/temp

# Cache directory
cache_dir=$SCRATCH/cache

# Username for TCIA
user=None

# Password for TCIA
password=None

python downloader.py --collection $collection --output $output --temp_dir $temp_dir --cache_dir $cache_dir --user $user --password $password --compress #--bids

