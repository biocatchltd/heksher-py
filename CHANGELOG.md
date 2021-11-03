# heksher Changelog
### 0.1.6
### Added
* Added support for setting alias in declaration
### 0.1.5
### Added
* Added add_validator method for Setting; Validators added to each Setting will be called by order they were added 
  (each validator will receive value of previous validator); Validators will be called each time the Setting is updated
* Added close checks to async client exit
### Changed
* Changing main client between similar clients that track the same contexts is now possible, but not recommended. Changed for testing purposes.
## 0.1.4
### Changed
* Changed httpx version limitation in poetry.toml to `*`
## 0.1.3
### Added
* Added get_settings method to thread and async clients
### Internal
* Changed linters to mypy and isort
### Fixed
* Added headers to httpx.AsyncClient and httpx.Client, that supports content in body to be json
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
