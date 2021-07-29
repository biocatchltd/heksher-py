# heksher Changelog
## unreleased
### Added
* Added get_settings method to thread and async clients
### Internal
* Changed linters to mypy and isort
### Fixed
* Added headers to httpx.AsyncClient, that supports content in body to be json
* Setting.metadata default value is now an empty dict
## 0.1.2
#### Fixed
* Removed redundant warning from `subclasses.py` when using `TRACK_ALL` feature.
* Cached time was time-zone dependant causing cache issues.
### Internal
* `poetry.lock`, `.coverage`, `pycache`, `coverage.xml` to gitignore
* Make `scripts` files executable (+x) and add shebang to the header.
## 0.1.1
### Fixed
* Send metadata on settings declaration.
## 0.1.0
* initial release
