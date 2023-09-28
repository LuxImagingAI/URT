# CoGMI_downloader [1.0.1]
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
The name of the collection which should be downloaded. Alternatively a .yaml file containing a list of collections for batch-processing of multiple datasets. An example can be seend in "collections.yaml".

`--output`:
The output directory for the data. Default: "./output"

`--temp_dir`:
The directory where the data is stored temporarily, e.g. for downloading (before compression). Can be useful in situations where not much space is left on the output drive. Default: output folder

`--cache_dir`:
Directory which is used for the output of the logs and the http cache. Default: "~/.cache/tcia_downloader"


`--user`:
The username of a TCIA acount. Needed when restricted collections are accessed.

`--password`:
The password of a TCIA acount. Needed when restricted collections are accessed.

`--bids`:
If this argument is given the dataset(s) will be converted to bids after the download (if the required data for the conversion is given in datasets)

`--compression`:
If this argument is added the output folder will be automatically compressed.


# Usage
## Basic usage
The following command will start the downloader with the given arguments.
```bash
python downloader.py --collection COLLECTION [--output OUTPUT] [--temp_dir TEMP_DIR] [--cache_dir CACHE_DIR] [--user USER] [--password PASSWORD] [--bids] [--compress]
```
The downloader will choose the appropriate downloader for the given collection (based on datasets/datasets.yaml). If the collection cannot be found it will fallback to donwloading via the nbia REST API and attempt a download of the collection. BIDS conversion is not possible in this case.

If datasets from OpenNeuro or TCIA via Aspera are downloaded make sure that the additional dependencies are installed.

### Advanced usage
### Slurm
The file CoGMI_downloader_hpc.sh is an example SLURM script for deployment on HPCs. By default it uses the $SLURM directory as temp_dir.

In a slurm environment:
```Bash
sbatch tcia_downloader_hpc.sh
```
or locally:
```Bash
./tcia_downloader_hpc.sh
```

### Docker
By using docker you can avoid the installation of the dependencies and achieve higher reproducibility.
First build the image by executing the following command in the main folder.

```Bash
docker build . cogmi_downloader:1.0.0
```

Afterwards the container can be started by executing:
```Bash
docker run -v ./output:/downloader/output -v ./temp_dir:/downloader/temp_dir -v ./cache_dir:/downloader/cache_dir cogmi_downloader:1.0.0 -collection COLLECTION [--user USER] [--password PASSWORD] [--bids] [--compress]
```
In the case of docker the output, temporary directory and cache directory can be changed by modifying the mounted volumes in the docker run command. E.g. replacing "./output:/downloader/output" by "~/output:/downloader/output" will move the output folder to the home directory.
### Docker compose
The usage of docker compose is supported as well. Start docker compose by executing:
```Bash
docker compose up
```
The arguments and volumes can be changed in the compose.yaml file.

### Singularity
The docker image should be able to work with singularity as long as --fakeroot and --no-home arguments are given. 

# Changelog
Only the last version updates are indicated here. The full changelog can be found in the CHANGELOG.md.

## [1.0.1] - 2023.09.28
### Changed
- Bugfix in .sh script: fixed error with spaces in arguments


## [1.0.0] - 2023.09.26

### Added
- Aspera integration
- Openneuro integration using aws-cli (BTC_prepo and BTC_postop datasets)
- Automatic detection of the correct downloader and source (Openneuroa, aspera, nbia)
- Dockerfile
- compose.yaml for docker compose
- Support for automatic bids conversion
- Support for lists of datasets in .yaml format: batch download and conversion of datasets
- Support for datasets which cannot be downloaded automatically (i.e. BraTS)

## Changed
- Code refactored: better modularity
- Representation of the datasets in datasets.yaml (previously: config.yaml)
- Subprocesses: raise exception if subprocess exits with error
- Subprocesses: output is appended to debug level logger 
- Bids argument takes no longer a boolean as input
- Bugfix: error with SeriesDate (some datasets do not contain this field)
  
## Removed
- Unnecessary imports
- Removed "mode" argument