### UHSLC section

**[EDITED]** fixed outdated prose — three required parameters (not two), and parameter name is `output_path` (not `output_dir`).
**[EDITED]** constructor call updated to pass the now-required `output_filename`.
**[EDITED]** `download_UHSLC_data.py::download`: print statement now reports `self.output_filename` instead of the remote-side `h<station_id>.csv`, so the log message matches the actual file written to disk.
**[EDITED]** `download_UHSLC_data.py::download`: docstring updated to state the response is written to `output_path / output_filename` (was still referring to `h<station_id>.csv` from the previous API).