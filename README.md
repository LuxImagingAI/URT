# tcia_downloader [0.2.0]
Python script with matching slurm bash file for downloading datatasets from the TCIA (The Cancer Imaging Archive) in HPC environments, where other methods do not work well. The datasets are directly converted to a compressed archive (tar.xz). Currently suppports the nbia datasets (datasets with limited access not tested yet). Will support the aspera downloader in the future as well.

## The tcia_downloader.py file
The script takes up to 5 arguments as input:

--collection: 
The name of the collection which should be downloaded

--output:
The output directory for the data

--temp_dir:
The directory where the data is stored temporarily, e.g. for downloading (before compression). Can be useful in the HPC use case (inode limit). If no argument is given the output folder will be used.

--user:
The username of a TCIA acount. Needed when restricted collections are accessed.

--password:
The password of a TCIA acount. Needed when restricted collections are accessed.

--compression:
The output folder will be automatically compressed

--mode:
The mode of the downloader. Can be either 'nbia' or 'aspera'. Default is 'nbia'. ('aspera' not implemented yet)

--cache_dir:
Directory which is used for the output of the logs and the http cache. Default: "~/.cache/tcia_downloader"

## The tcia_downloader_hpc.sh file
This is just a template containing slurm directives. It can therefore be used locally as well as in an HPC environment. Adjust this file according to your application. It can be used as follows:

```
using slurm:
sbatch tcia_downloader_hpc.sh

using locally:
./tcia_downloader_hpc.sh
```



# Changelog

## [0.2.0] - 2023.09.15

### Added
- Non-cached GET and POST requests use sessions even with caching is disabled: avoids re-establishing of the TCP connection during data download (speedup especially noticeable on smaller images)
- Added the option to change the cache and logs path

### Changed
- Bugfix: exception is not thrown anymore when the metadata does not contain a value for SeriesDate ("unkown_date" used instead)
- Changed default position of logs and cache (now at "~/.cache/tcia_downloader")
- Logs are named by their creation date

## [0.1.2] - 2023.09.13

### Changed
- Fix in token renewal: user and password were not stored in tcia_utils object


## [0.1.1] - 2023.09.12

### Changed
- In case no compression is used: the data will be copied to the output folder after downloading


## [0.1.0] - 2023.09.11

### Added
- Added new tcia_api class for handling the api calls
- Simplified handling of tokens and token renewal
- Logging via python logging library: better readability and flexibility
- Logs are stored in the "logs" folder with two different levels of verbosity
- API queries are now fault tolerant: multiple retries and increasing timeouts
- Downloader checks data integrity using MD5 hashes
- Checks for already downloaded data: works with renamed and mixed folders as well (if the script was interrupted during renaming)
- GET requests (not carrying large files) are cached to avoid overhead
- Removes unkown dicom files: avoids contamination by other datasets

### Changed
- Code refactored: better readability
- Replaced getDicomTag API call with metadata from getSeriesMetadata: substantial reduction of API calls
- Checks for file corruption are now much faster: removed calls to API (retrieves MD5 hash with image download instead)

### Removed
- Multiprocessing: now token renewal is handled in tcia_api
- tcia_utils library (replaced by own tcia_api class)
