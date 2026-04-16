# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- `retrievals` subpackage — ERA5, Copernicus Marine, UHSLC downloaders
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
