# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- xbeachpy documentation pages mirroring the swanpy structure
- Symlinked 2D case example notebook into xbeachpy docs

---

## [0.1.0] - TBD

First user-facing release. The `xbeachpy` subpackage is considered
feature-complete and stable enough for user testing.

### Added
- `xbeachpy` subpackage for end-to-end XBeach case preparation
  - `Initializer` — folder structure creation and `params.txt` stamping
  - `preprocess.GridMaker` — 1D profile and 2D uniform/segmented grid generation from shapefiles
  - `preprocess.BathyMaker` — XYZ-to-DEP conversion for 1D and 2D bathymetry
  - `preprocess.BoundaryConditions` — SWAN spectral output to XBeach `.sp2` / filelist / loclist
  - `preprocess.WindForcing` — ERA5 wind download and ASCII conversion
  - `preprocess.WaterLevelForcing` — UHSLC gauge download and ASCII conversion
  - `preprocess.Vegetation` — vegetation parameter setup
  - `execution.CaseRunner` — output configuration and `params.txt` finalisation
  - `postprocess.OutputReader` — lazy NetCDF output reader (field and point output)
- Sphinx documentation for `xbeachpy` (initializer, preprocess, execution, postprocess)
- 2D case walkthrough notebook (`examples/models/xbeach_2D_case.ipynb`)

### Changed
- NumPy-style docstrings added across all `xbeachpy` classes and methods
- `Initializer.create_folders_l1` renamed to `create_folders`

---

## [0.0.1] - 2024

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

[Unreleased]: https://github.com/oceanicos/oceanicospy/compare/0.1.0...HEAD
[0.1.0]: https://github.com/oceanicos/oceanicospy/compare/0.0.1...0.1.0
[0.0.1]: https://github.com/oceanicos/oceanicospy/releases/tag/0.0.1
