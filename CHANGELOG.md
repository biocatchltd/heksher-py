# heksher-py Changelog
## 0.2.2
### Added
* support for python 3.10
## 0.2.1
### Fixed
* fixed a declaration bug where the wrong method was called
### 0.2.0
This version is only compatible with heksher 0.5.0 and above.
### Added
* Added support for setting alias in declaration
* `__version__` is now a module-level attribute
* documentation site
* HeksherEnum, HeksherFlags, HeksherMapping, and HeksherSequence are now public, and are the 
  preferred way to create complex setting types.
* client.get_settings() also includes the setting's version and alias
* setting.on_coerce, a callable to use if value coercion occurs.
* type coercion and rejection is now supported
* added overridable callback methods ```on_update_error``` and ```on_update_success``` to Async and
  Thread clients.
### Removed
* stub rules no longer accept `None` feature values
### Changed
* only the new heksher API is now supported
* stub rules now don't have to all have the same context features.
* the server's default value is now respected over the local default value.
* validators now accept the rule object as retrieved from the server
* Each setting now only requires its configurable features to be specified.
* If an async client fails startup or reload, it raises an error.
* default values are now required for settings.
### Deprecated
* Creating settings with an alias type, enum type, or flags type is deprecated. use HeksherEnum, HeksherFlags, 
  HeksherMapping, or HeksherSequence instead.
* using ``patch`` for stub clients is now deprecated. Prefer to set the ``rules`` attribute instead.
* ``AsyncContextManagerMixin.close`` is now deprecated. Use ``AsyncContextManagerMixin.aclose`` instead.
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
