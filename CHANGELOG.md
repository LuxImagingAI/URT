This changelog follows the Semantic Versioning convention (version 2.0.0)

# Changelog

## [1.0.2] - 2023.10.13
### Added
- Docker image now compatible with Singularity

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

### Changed
- Code refactored: better modularity
- Representation of the datasets in datasets.yaml (previously: config.yaml)
- Subprocesses: raise exception if subprocess exits with error
- Subprocesses: output is appended to debug level logger 
- Bids argument takes no longer a boolean as input
- Bugfix: error with SeriesDate (some datasets do not contain this field)
  
### Removed
- Unnecessary imports
- Removed "mode" argument

## [0.2.1] - 2023.09.18

### Changed
- bugfix: error in token renewal

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
