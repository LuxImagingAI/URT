# CoGMI_downloader [2.0.0]
Tool for automatic download and BIDS conversion of TCIA and OpenNeuro datasets.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Arguments](#arguments)
4. [Usage](#usage)
    - [Basic Usage](#basic-usage)
    - [Advanced Usage](#advanced-usage)

# Prerequisites
- Python 3.x
- OPTIONAL: conda or mamba
- OPTIONAL: aws cli (required for downloads from OpenNeuro)
- OPTIONAL: aspera-cli (required for downloads from TCIA which are stored as NIFTI)

Alternatively docker can be used.

# Arguments

`--collection`: 
The name of the collection which should be downloaded. Alternatively a .yaml file containing a list of collections for batch-processing of multiple datasets. An example can be seen in "config/collections.yaml".

`--output`:
The output directory for the data. Default: "./output"

`--temp_dir`:
The directory where the data is stored temporarily, e.g. for downloading (before compression). Can be useful in situations where not much space is left on the output drive. Default: output folder

`--cache_dir`:
Directory which is used for the output of the logs and the http cache. Default: "~/.cache/tcia_downloader"

`--credentials`:
Path to credentials.yaml file containing the credentials (seperate for each downloader). Default is "config/credentials.yaml"

`--bids`:
If this argument is given the dataset(s) will be converted to bids after the download (if the required data for the conversion is given in datasets)

`--compression`:
If this argument is added the output folder will be automatically compressed.


# Usage
## Basic usage
The following command will start the downloader with the given arguments.
```bash
python downloader.py --collection COLLECTION [--output OUTPUT] [--temp_dir TEMP_DIR] [--cache_dir CACHE_DIR] [--credentials CREDENTIALS_FILE] [--bids] [--compress]
```
The downloader will choose the appropriate downloader for the given collection (based on datasets/datasets.yaml). If the collection cannot be found it will fallback to donwloading via the nbia REST API and attempt a download of the collection. BIDS conversion is not possible in this case.

If datasets from OpenNeuro or TCIA via Aspera are downloaded make sure that the additional dependencies are installed.

### Advanced usage
### Slurm
The file CoGMI_downloader_hpc.sh is an example SLURM script for deployment on HPCs. By default it uses the $SCRATCH directory as temp_dir.

In a slurm environment:
```Bash
sbatch tcia_downloader_hpc.sh
```
or locally:
```Bash
./tcia_downloader_hpc.sh
```

### Docker
> **Warning:** As long as the project is not published yet the docker image is only available through a private repo on dockerhub. Before running the image you need to login to dockerhub by executing: 
> ```bash
> docker login --username raphaelmaser@gmail.com
>```
> with the password "dckr_pat_2H7B0b4fIYPndw4hl1vXFr72KHs"

By using docker you can avoid the installation of any dependencies and achieve higher reproducibility.

The container can be started by executing:
```Bash
docker run -v ./output:/URT/output -v ./temp_dir:/URT/temp_dir [-v ./cache_dir:/URT/cache_dir] [-v ./config:/URT/config] ydkq4eu2vrqc2uuy8x3c/cogmi_downloader:latest --collection COLLECTION [--credentials CREDENTIALS_FILE] [--bids] [--compress]
```
In the case of docker the output, temporary directory and cache directory can be changed by modifying the mounted volumes in the docker run command. E.g. replacing "./output:/downloader/output" by "~/output:/downloader/output" will move the output folder to the home directory.

### Docker compose
> **Warning:** The same restrictions concerning the private repo apply here.

The usage of docker compose is supported as well. Start docker compose by executing:
```Bash
docker compose up
```
The arguments and volumes can be changed in the compose.yaml file.

### Singularity
> **Warning:** As long as the project is not published yet the docker image is only available through a private repo on dockerhub. Before running the image you need to set two environment variables for singularity: 
> ```bash
> export SINGULARITY_DOCKER_USERNAME=raphaelmaser@gmail.com
>export SINGULARITY_DOCKER_PASSWORD=dckr_pat_2H7B0b4fIYPndw4hl1vXFr72KHs
>
>```

Singularity is supported as well. The following command can be used to pull the docker image from dockerhub, convert it to the singularity image format .sif and run it:

```bash
singularity run --cleanenv --writable-tmpfs --no-home --bind ./output:/downloader/output --bind ./temp_dir:/downloader/temp_dir [--bind ./cache_dir:/downloader/cache_dir] [--bind ./config:/URT/config] docker://ydkq4eu2vrqc2uuy8x3c/cogmi_downloader:latest --collection COLLECTION [--credentials CREDENTIALS_FILE] [--bids] [--compress]
```

Similar to docker, the output folder can be changed by changing the path of the mounted directories.

# Changelog
Only the last version updates are indicated here. The full changelog can be found in the CHANGELOG.md.

## [2.0.0] - 2021.11.05

### Added
- Automatic creation of dseg.tsv for supported datasets
- Support for dataset: Brats-2021
- Automatically removes unwanted Patients from BTC_preop and BTC_postop
- Modules: allow arbitrary modifications of the downloaded datasets
- Credentials file supporting seperate credentials for every downloader

### Changed
- Readme.md: error in docker and singularity command (mounting collections.yaml)
- Minor changes in logger
- Increased modularity of the downloaders
- Downloader class: every downloader has to inherit from "Downloader"
- Numerous enhancements concerning readability and simplicity
- Manual download represented by the "Manual" downloader class instead of "none"
- Changed format of datasets in datasets.yaml

### Removed
- Username and password are not given as argument anymore
- Duplicate code: opening dataset.yaml (now opened once during object initialization)

