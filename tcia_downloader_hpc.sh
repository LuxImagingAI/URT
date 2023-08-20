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

python tcia_downloader.py --collection "$collection" --output "$output" --temp_dir "$temp_dir" #--user "$user" --password "$password"


