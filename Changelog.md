This changelog follows the Semantic Versioning convention (version 2.0.0)

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
