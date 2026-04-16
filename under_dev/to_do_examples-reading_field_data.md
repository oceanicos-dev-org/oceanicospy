# Reading field data notebook — review notes

# Convention

- **[EDITED]** — change already applied to the notebook.
- `[NOTE]` — review comment or design decision pending discussion.

# --------------------------------------------------------------
# Pressure sensors
# --------------------------------------------------------------

**[EDITED]** Section title adjusted to match class naming convention (`AQUALogger` → `AQUAlogger`, `BlueLogger` → `Bluelog`).

## Data directories and sampling configuration
`[NOTE]` `start_time` and `end_time` are optional only for `get_raw_records()`. `get_clean_records()` requires both — `BaseLogger._parse_dates_and_trim()` raises `ValueError` if either is missing. The notebook text could reflect this distinction.

`[NOTE]` `HOBOBase._parse_dates_and_trim()` returns the full DataFrame when no dates are provided, while `BaseLogger` has no such fallback. Both base classes should align on this behavior.

`[NOTE]` Consider moving the `end_time` boundary adjustment (`- timedelta(seconds=1)`) inside `_parse_dates_and_trim()` rather than exposing it to the user in the notebook.

`[NOTE]` `temperature=False` in `sampling_Bluelog` has no effect — not used anywhere in `Bluelog` or `BaseLogger`. 

## Reading and storing data

**[EDITED]** Removed incorrect class reference (`PressureSensor`). Replaced with `get_clean_records()` called on each sensor object directly.

**[EDITED]** Added explanation of `depth_aux[m]` and its hydrostatic formula to the existing Markdown cell below `dict_clean_measurements['AQ'].head()`.

# --------------------------------------------------------------
# Weather stations: Davis Vantage Pro, WeatherSens and Rainwise
# --------------------------------------------------------------

**[EDITED]** Added brief description of measured variables to the introductory cell of the Weather stations section.

**[EDITED]** Removed incorrect class reference (`WeatherStation`). Replaced with `get_raw_records()` called on each sensor object directly.

**[EDITED]** Fixed grammar (`look to` → `look at`) and expanded explanation.

`[NOTE]` No Markdown cell explains the differences between the three clean DataFrames. Manuals pending review.

`[NOTE]` `.info()` loop lacks an introductory Markdown cell. Add explanation for consistency with the pressure sensors section.

# --------------------------------------------------------------
# CTD sensors
# --------------------------------------------------------------

**[EDITED]** Added introductory Markdown cell

**[EDITED]** Fixed grammar and merged both `has_header=False` and `has_header=True` explanations into a single Markdown cell for clarity.

**[EDITED]** An explanation of `cast_time` was added.

**[EDITED]** replaced full DataFrame display with `.head()` for consistency with other sections.

# --------------------------------------------------------------
# ADCP sensors: AWAC
# --------------------------------------------------------------

**[EDITED]** Added mention of required `.hdr` and `.wad` files in the introductory cell.

`[NOTE]` `temperature=False` in `sampling_AWAC` has no effect — `AWAC.__init__` does not use this key. 

`[NOTE]` Same `end_time - timedelta(seconds=1)` boundary workaround as in pressure sensors.

`[NOTE]` `help(AWAC)` is called, but not for any other sensor object.

**[EDITED]** Expanded `from_single_wad` parameter explanation before the two subsections that demonstrate each option.

**[EDITED]** Added transitional Markdown cells between raw and clean outputs

**[EDITED]** Added introductory Markdown cell in the current records subsection explaining the `.v1`/`.v2` files, east/north components, and `cell_N` column naming convention.

`[NOTE]` `help(AWAC.get_clean_currents_records)` is called.

`[NOTE]` `awac.py` contains a `#TODO` flag on the direction calculation inside `get_clean_currents_records()`. Review.

# --------------------------------------------------------------
# Spotter buoy
# --------------------------------------------------------------

**[EDITED]** Added introductory Markdown cell describing supported Spotter formats.

`[NOTE]` `csv_file.split('/')[-1].split('.')[0]` as a dictionary key is hard to read. Consider extracting it as `source_name = Path(csv_file).stem` for clarity.

**[EDITED]** Added inline comment in Cell 70 warning that format detection relies on the filename containing `'sofar'`.

**[EDITED]** Replaced `csv_file.split('/')[-1].split('.')[0]` with `source_name` variable using `replace('\\', '/')` for cross-platform compatibility and improved readability.

# --------------------------------------------------------------
# HOBO sensors
# --------------------------------------------------------------

**[EDITED]** Added introductory Markdown cell before Cell 80 describing supported HOBO models and measured variables.

**[EDITED]** Replaced vague "some columns are dropped" in Cell 84 with an accurate description of what `get_clean_records()` does, consistent with `hobo.py`.