# --------------------------------------
# UHSLC section
# --------------------------------------

## Edited in source code 

**[EDITED]** `UHSLCDownloader.__init__`: `output_filename` promoted to required positional argument (previously filename was hardcoded as `h<station_id>.csv`), so the user controls the local filename.
**[EDITED]** `UHSLCDownloader.__init__`: `output_path` and `output_filename` are now normalized to `Path` inside the constructor (matching the pattern used by `CMDSDownloader` and `ERA5Downloader`). Removes the `isinstance` side effect that was previously in `download()`.
**[EDITED]** `UHSLCDownloader.__init__`: `start_datetime_local` and `end_datetime_local` typed as `datetime | None` instead of `str | None`, aligning the three downloaders on a single datetime API.
**[EDITED]** `UHSLCDownloader.__init__`: parameter renamed `difference_from_UTC` → `utc_offset_hours`, aligned with ISO 8601 terminology. Docstring includes an explicit sign example (UTC-5 → `-5`) and declares the `-5` default.
**[EDITED]** `UHSLCDownloader.__init__`: `self.last_result_path` initialized to `None` so the attribute always exists before `download()` is called.
**[EDITED]** `UHSLCDownloader.download`: sign of the UTC→local conversion fixed — was subtracting the offset, now adds it, matching the documented convention `local = UTC + (local − UTC)`. Previously yielded timestamps shifted 2·offset in the wrong direction.
**[EDITED]** `UHSLCDownloader.download`: added `timeout=60` to `requests.get` to prevent indefinite hangs if the UHSLC server is unresponsive. Docstring `Raises` section extended with `ConnectionError` and `Timeout`.
**[EDITED]** `UHSLCDownloader.download`: log message and docstring now reference `output_filename` (the actual local filename) instead of the remote `h<station_id>.csv`.
**[EDITED]** `UHSLCDownloader.download`: records the output path in `self.last_result_path`, mirroring the pattern used by `CMDSDownloader`.
**[EDITED]** `UHSLCDownloader.clean_data`: removed the `filepath` parameter; the method now reads from `self.last_result_path`. Eliminates the risk of applying `utc_offset_hours` to a file that doesn't belong to the instance, and simplifies the user-facing API to `download()` → `clean_data()` without manual path plumbing.

## Edited in notebook

**[EDITED]** prose realigned with the updated API — three required parameters (`station_id`, `output_path`, `output_filename`); renamed `difference_from_UTC` → `utc_offset_hours` with the `local - UTC` convention and the `-5` default made explicit; date-range example updated from strings to `datetime` objects.
**[EDITED]** `start_datetime_local` and `end_datetime_local` passed as `datetime` objects instead of strings.
**[EDITED]** clarified that `clean_data()` operates on the last downloaded file (no arguments required).
**[EDITED]** `clean_data(filepath)` → `clean_data()`, consistent with the new no-argument signature.

# --------------------------------------
# CMDS section
# --------------------------------------

### Edited in source code

**[EDITED]** `CMDSDownloader.__init__`: parameter renamed `difference_to_UTC` → `utc_offset_hours`, unifying the three downloaders on a single name and adopting ISO 8601 terminology. Docstring updated with the `local - UTC` convention and an explicit sign example (Colombia = `-5`). Same rename propagated to `for_waves` and `for_winds`.
**[EDITED]** `CMDSDownloader.__init__`: sign of the local → UTC conversion fixed — was `start_datetime_local + timedelta(hours=offset)`, now `- timedelta(...)`, matching the documented convention (`UTC = local − offset`). Previously produced subset requests shifted 2·|offset| hours from the intended UTC window.
**[EDITED]** `CMDSDownloader.format_to_localtime` docstring: reference to `difference_to_UTC` updated to `utc_offset_hours`.
**[EDITED]** `CMDSDownloader.download` docstring: return description changed from "file (or directory)" to "NetCDF file" for clarity.

## Edited in notebook

**[EDITED]** parameter list realigned with the current API — `start_datetime_local`/`end_datetime_local` typed as `datetime` (not `start_date_local`/`end_date_local`); `utc_offset_hours` (not `difference_to_utc`); `output_filename` (not `filename`). Optional parameters flagged. Dataset example and EST/UTC-5 ambiguity clarified.
**[EDITED]** `difference_to_UTC` → `utc_offset_hours` to match the renamed parameter.
**[EDITED]** fixed copy-paste error — text referred to "ERA5 dataset" inside the CMDS section; now says "CMDS dataset". Replaced "EST" with "UTC-5" to avoid DST ambiguity.
**[EDITED]** replaced "For wind" with "For waves", and corrected the product ID to `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i` (was `cmems_obs-wave_glo_wav_anfc_0.083deg_PT3H`, which did not match `CMDSDownloader.for_waves`).
**[EDITED]** `difference_to_UTC` → `utc_offset_hours` to match the renamed parameter.

# --------------------------------------
# ERA5 section
# --------------------------------------

### Edited in source code

**[EDITED]** `ERA5Downloader.__init__`: parameter renamed `difference_to_UTC` → `utc_offset_hours`, unifying the three downloaders on a single name and adopting ISO 8601 terminology. Docstring updated with the `local - UTC` convention and an explicit sign example (Colombia = `-5`). Same rename propagated to the attribute, the UTC conversion lines in `__init__`, and the docstring/body of `format_to_localtime`.
**[EDITED]** `ERA5Downloader.__init__`: added `self.last_result_path: Path | None = None` to mirror the pattern used by `UHSLCDownloader` and `CMDSDownloader`.
**[EDITED]** `ERA5Downloader.download`: records the resolved output path in `self.last_result_path` before returning, so the attribute reflects the actual file written by the CDS API.

## Edited in notebook

**[EDITED]** constructor keyword argument renamed `difference_to_UTC` → `utc_offset_hours` to match the renamed parameter in `ERA5Downloader`.
**[EDITED]** the `cdsapi_rc` argument pointing to the author's local path (`/Users/franklinayala/.cdsapirc`) was commented out so the notebook falls back to `cdsapi`'s default credential resolution (`~/.cdsapirc`).