# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0b6][0.1.0b6] - 2026-04-30

### Added

- `xbeachpy` subpackage promoted to beta — XBeach case preparation tools are considered
  feature-complete and undergoing stabilization before the final 0.1.0 release
- `Initializer` — creates the project folder tree (`input/`, `pros/`, `run/`, `output/`)
  and stamps `params.txt` from the bundled template with user-supplied configuration flags
- `GridMaker` — unified grid builder for 1D profiles and 2D rectangular domains;
  delegates coordinate geometry to `ProfileAxis` (`build_profile`) and `Grid`
  (`build_rectangular_grid`) from the `gis` subpackage
- `BathyMaker` — cross-shore bathymetry interpolation from scattered XYZ data onto the
  profile axis, and direct loading of pre-built `.dep` files
- `BoundaryConditions` — processes SWAN spectral output (`SpecSWAN.out`) into per-timestep
  `.sp2` files and generates the `filelist_<i>.txt` / `loclist.txt` file structure required
  by XBeach for both 1D and 2D non-stationary boundary conditions
- `WindForcing` — integrates with `ERA5Downloader` to fetch hourly U10/V10 winds and
  convert them to the XBeach single-point ASCII wind file format
- `WaterLevelForcing` — downloads UHSLC research-quality tide-gauge records and converts
  them to the XBeach water level ASCII format
- `Vegetation` — vegetation parameter file preparation for surf-beat simulations
- `CaseRunner` (`execution`) — finalises `params.txt` with output filenames, field and
  point variable selection, gauge coordinates, and the computation time window
- RST API documentation for the `xbeachpy` subpackage under `docs/models/xbeachpy/`
- 1D walkthrough example notebook (`xbeach_1D_case.ipynb`) covering a non-stationary
  Caribbean coast profile case including full pre-processing and post-processing steps
- 2D walkthrough example notebook (`xbeach_2D_case.ipynb`) covering a non-stationary
  Sound Bay domain case with spatial field plots and point time-series post-processing

### Fixed

- `BoundaryConditions.spectra_from_swan` — parsing guard now correctly skips only
  all-digit tokens, preventing valid spectral data lines from being silently dropped
  when processing multi-point SWAN output files

## [0.1.0b5][0.1.0b5] - 2026-04-29

### Added

- `gis` subpackage promoted to beta — GIS-based geometry, grid construction, and spatial
  I/O tools are considered feature-complete and undergoing stabilization before the final
  0.1.0 release
- `ProfileAxis` — cross-shore profile geometry with automatic extension and coordinate
  transformation support
- `Grid` — 2-D rectangular grid data class built from a shapefile boundary
- `PointFileIO` — XYZ point-file reader/writer with configurable format specification
  (`XYZFormatSpec`) and auto-detection of delimiter and header
- `ProfileInterpolator` — bathymetry interpolation onto a profile axis from scattered
  XYZ point data
- RST API documentation for the `gis` subpackage under `docs/gis/`

## [0.1.0b4][0.1.0b4] - 2026-04-23

### Added

- `swanpy` subpackage promoted to beta — SWAN case preparation and post-processing tools
  are considered feature-complete and undergoing stabilization before the final 0.1.0 release
- Updated stationary and non-stationary example notebooks to reflect the refactored API

### Changed

- `BoundaryConditions` — boundary file construction extracted from inline logic into
  `_build_side_boundary_line`; `_process_boundary_points` now delegates to a callable
  `single_tpar_fn` so ERA5 and CMDS code paths share one loop
- `WindForcing` — download helpers (`_download_ERA5` / `_download_CMDS`) delegated to
  `utils.wind.download_era5_winds` / `download_cmds_winds`; `share_winds` flag controls
  whether non-primary domains skip download and reuse domain-01 ASCII files

## [0.1.0b3][0.1.0b3] - 2026-04-21

### Added

- `downloads` subpackage promoted to beta — ERA5, Copernicus Marine (CMDS), and UHSLC
  downloaders are considered feature-complete and undergoing stabilization before the
  final 0.1.0 release
- `WaveTemporalAnalyzer` — `zero_centered` boolean parameter to indicate whether the
  measured pressure signal is already zero-centered; controls trend removal before
  zero-upcrossing wave statistics (default `False`)
- `WaveTemporalAnalyzer` — total sensor depth (`anchoring_depth + sensor_height`) now
  used for wavelength calculation in dispersion relation

### Fixed

- `CMDSDownloader` — file-update logic no longer raises on Windows when converting
  timestamps to local time format
- `CMDSDownloader` — NetCDF writing now works correctly across Linux, macOS, and Windows
- `CMDSDownloader` — `.cdsapi` credentials validator corrected; explicit overwrite flag
  added to prevent silent data loss
- UTC offset API unified across all downloader modules; sign-convention bugs corrected

### Changed

- Renamed `trend` parameter to `zero_centered` throughout `temporal.py` for clarity

## [0.1.0b2][0.1.0b2] - 2026-04-17

### Added

- `analysis` subpackage promoted to beta — spectral, temporal, and tidal analysis tools
  are considered feature-complete and undergoing stabilization before the final 0.1.0 release
- `WaveSpectralAnalyzer._verify_bursts_in_signal` — pre-processing step that removes
  bursts with incorrect sample count before spectral and wavelet computation
- `WaveTemporalAnalyzer._check_burst_length` and `_verify_bursts_in_signal` — same
  burst-validation logic ported to the temporal analyzer
- Tidal analysis documentation: theoretical foundations RST page and harmonic tide
  decomposition example notebook under `docs/analysis/tidal/`
- Reorganized `docs/analysis/` into `spectral/`, `temporal/`, and `tidal/` subdirectories

### Fixed

- `WaveSpectralAnalyzer._check_burst_length` now returns `bool` instead of `None`/raising
  on valid input, correcting the downstream logic in `_compute_spectrum_for_burst`
- `WaveTemporalAnalyzer.apply_zero_upcrossing_burst` call now uses `surface_level_column`
  instead of the hardcoded `'pressure[bar]'` column name
- PyEMD imports in `temporal.py` consolidated to a single `from PyEMD import EMD, EEMD, CEEMDAN`

## [0.1.0b1][0.1.0b1] - 2026-04-16

### Changed

- `observations` subpackage promoted to beta — readers for AWAC, CTD, RBR,
  pressure sensors, weather stations, and buoy data are considered feature-complete
  and undergoing stabilization before the final 0.1.0 release

## [0.0.1][0.0.1] - 2024

Initial scaffolding release.

### Added

- `swanpy` subpackage for SWAN wave model case preparation
  - `Initializer`, `preprocess` (GridMaker, BathyMaker, BoundaryConditions,
    WindForcing, WaterLevelForcing, BottomFriction), `execution.CaseRunner`
- `downloads` subpackage — ERA5, Copernicus Marine, UHSLC downloaders
- `analysis` subpackage — spectral analysis, wave statistics, EMD/wavelet tools
- `observations` subpackage — readers for AWAC, CTD, RBR, pressure sensors,
  weather stations, and buoy data
- `utils` subpackage — file templating, interpolation, link management helpers
- `plots` subpackage — figure styling and plot utilities
- Sphinx documentation skeleton with ReadTheDocs integration
- Example notebooks for SWAN stationary and non-stationary cases

[0.0.1]: https://github.com/oceanicos/oceanicospy/releases/tag/0.0.1
[Unreleased]: https://github.com/oceanicos/oceanicospy/compare/0.1.0...HEAD
[0.1.0b1]: https://github.com/oceanicos/oceanicospy/compare/0.1.0a1...0.1.0b1
[0.1.0b2]: https://github.com/oceanicos/oceanicospy/compare/0.1.0b1...0.1.0b2
[0.1.0b3]: https://github.com/oceanicos/oceanicospy/compare/0.1.0b2...0.1.0b3
[0.1.0b4]: https://github.com/oceanicos/oceanicospy/compare/0.1.0b3...0.1.0b4
[0.1.0b5]: https://github.com/oceanicos/oceanicospy/compare/0.1.0b4...0.1.0b5
[0.1.0b6]: https://github.com/oceanicos/oceanicospy/compare/0.1.0b5...0.1.0b6
