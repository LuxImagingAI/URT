# Changelog
## [0.1.0] - 2023.09.11

### Added
- Added new tcia_api class for handling the api calls
- Simplified handling of tokens and token renewal
- Logging via python logging library: better readability and flexibility
- API queries are now fault tolerant: multiple retries and increasing timeouts
- Downloader checks data integrity in case of failed downloads and at the end by comparing MD5 hashes for each file
- GET requests (not carrying large files) are cached to avoid overhead due to the integrity check

### Changed
- Code refactored: better readability
- Renamed project to CoGMI_downloader
- Replaced getDicomTag API call with metadata from getSeriesMetadata: less API calls during renaming of the folders

### Removed
- Multiprocessing: now token renewal is handled in tcia_api
- tcia_utils library (replaced by own tcia_api class)
