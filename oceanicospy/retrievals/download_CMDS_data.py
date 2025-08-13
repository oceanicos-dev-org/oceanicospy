import os
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import xarray as xr
import copernicusmarine


class CMDSDownloader:
    """
    Copernicus Marine Data Store (CMDS) downloader mirroring ERA5 input style.
    Includes an ERA5-like post-processing method to rewrite the NetCDF in LOCAL time (shift + crop).
    """

    def __init__(
        self,
        dataset_id: str,
        variables: List[str],
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        start_datetime_local: datetime,
        end_datetime_local: datetime,
        difference_to_UTC: float,
        output_path: str,
        file_format: str = "netcdf",
        output_filename: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        dataset_id : str
            CMDS dataset identifier (case-sensitive, as listed in the CMDS catalog).
        variables : List[str]
            Variables to request (dataset-specific names).
        lon_min, lon_max, lat_min, lat_max : float
            Bounding box in degrees (EPSG:4326).
        start_datetime_local, end_datetime_local : datetime
            Local-time window of interest.
        difference_to_UTC : float
            Local minus UTC (hours). Example: UTC-5 -> -5.
        output_path : str
            Directory where the output will be written.
        file_format : str
            "netcdf" or "zarr". The post-process method supports only "netcdf".
        output_filename : Optional[str]
            File name to write inside output_path (e.g., "winds_CMDS.nc").
        """
        self.dataset_id = dataset_id
        self.variables = variables
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.start_datetime_local = start_datetime_local
        self.end_datetime_local = end_datetime_local
        self.difference_to_UTC = difference_to_UTC
        self.output_path = output_path
        self.file_format = file_format
        self.output_filename = output_filename

        # Convert local datetimes to UTC (request window must be UTC for CMDS)
        if self.difference_to_UTC >= 0:
            self.start_datetime_utc = self.start_datetime_local - timedelta(hours=self.difference_to_UTC)
            self.end_datetime_utc = self.end_datetime_local - timedelta(hours=self.difference_to_UTC)
        else:
            self.start_datetime_utc = self.start_datetime_local + timedelta(hours=abs(self.difference_to_UTC))
            self.end_datetime_utc = self.end_datetime_local + timedelta(hours=abs(self.difference_to_UTC))

        # Will hold the absolute path returned or resolved after download
        self.last_result_path: Optional[str] = None

    def download(self) -> str:
        """
        Execute CMDS subset request. Returns absolute path to the created resource.
        """
        # Ensure output directory exists; always write inside self.output_path
        os.makedirs(os.path.abspath(self.output_path), exist_ok=True)
        output_directory = os.path.abspath(self.output_path)

        # Build request arguments for CMDS Toolbox API
        subset_kwargs = dict(
            dataset_id=self.dataset_id,
            variables=self.variables,
            minimum_longitude=self.lon_min,
            maximum_longitude=self.lon_max,
            minimum_latitude=self.lat_min,
            maximum_latitude=self.lat_max,
            start_datetime=self.start_datetime_utc.isoformat(),
            end_datetime=self.end_datetime_utc.isoformat(),
            output_directory=output_directory,
            file_format=self.file_format,
        )
        # If a custom filename is requested, pass it to the API
        if self.output_filename is not None:
            subset_kwargs["output_filename"] = self.output_filename

        # Perform the subset/download
        result_path = copernicusmarine.subset(**subset_kwargs)

        # Resolve absolute path to the file or directory created
        if self.output_filename is not None:
            abs_path = os.path.abspath(os.path.join(output_directory, self.output_filename))
        else:
            abs_path = os.path.abspath(result_path if isinstance(result_path, str) else output_directory)

        self.last_result_path = abs_path
        return abs_path

    def _resolve_target_nc(self) -> str:
        """
        Resolve the NetCDF file path to be opened for post-processing.
        Preference order:
          1) last_result_path if it is a .nc file.
          2) If last_result_path is a directory, find a single .nc inside it.
             - If multiple, prefer output_filename; otherwise, newest by mtime.
          3) Fallback to output_path/output_filename if it exists.
        """
        candidate = self.last_result_path or ""

        # Case 1: already a file path to .nc
        if candidate and os.path.isfile(candidate) and candidate.lower().endswith(".nc"):
            return candidate

        # Case 2: directory containing one or more .nc files
        if candidate and os.path.isdir(candidate):
            nc_files = [
                os.path.join(candidate, f)
                for f in os.listdir(candidate)
                if f.lower().endswith(".nc")
            ]
            if len(nc_files) == 1:
                return nc_files[0]
            if len(nc_files) > 1:
                if self.output_filename:
                    wanted = os.path.join(candidate, self.output_filename)
                    if os.path.isfile(wanted):
                        return wanted
                nc_files.sort(key=os.path.getmtime, reverse=True)
                return nc_files[0]

        # Case 3: fallback to output_path + output_filename
        if self.output_filename:
            fallback = os.path.join(self.output_path, self.output_filename)
            if os.path.isfile(fallback):
                return os.path.abspath(fallback)

        raise FileNotFoundError(
            "Could not resolve a NetCDF file to post-process. "
            "Ensure `download()` ran successfully and `output_filename` has a .nc extension."
        )

    def format_to_localtime(self) -> None:
        """
        Notes
        -----
        - Only supports NetCDF outputs. For Zarr, implement a separate workflow.
        """
        if self.file_format.lower() != "netcdf":
            raise ValueError("format_to_localtime only supports NetCDF outputs. Use file_format='netcdf'.")

        target_nc = self._resolve_target_nc()

        # Open dataset; specify engine to avoid guessing errors on some systems
        ds = xr.load_dataset(target_nc, engine="netcdf4")

        # Detect time coordinate name
        if "valid_time" in ds.variables:
            tcoord = "valid_time"
        elif "time" in ds.variables:
            tcoord = "time"
        else:
            raise KeyError("No time coordinate found in dataset ('valid_time' or 'time').")

        # Shift UTC -> local: local = UTC + difference_to_UTC (e.g., -5 -> subtract 5 hours)
        shift_hours = int(self.difference_to_UTC)
        ds[tcoord] = ds[tcoord] + np.timedelta64(shift_hours, "h")

        # Crop to the local-time window using the same time coordinate
        t0_local = np.datetime64(self.start_datetime_local)
        t1_local = np.datetime64(self.end_datetime_local)
        ds_cropped = ds.sel({tcoord: slice(t0_local, t1_local)})

        # Overwrite the same NetCDF file
        ds_cropped.to_netcdf(target_nc, mode="w", format="NETCDF4")

    # ---------------- Convenience constructors ----------------

    @classmethod
    def for_waves(
        cls,
        dataset_id: str,
        variables: List[str],
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        start_datetime_local: datetime,
        end_datetime_local: datetime,
        difference_to_UTC: float,
        output_path: str,
        file_format: str = "netcdf",
        output_filename: Optional[str] = "waves_CMDS.nc",
    ) -> "CMDSDownloader":
        return cls(
            dataset_id,
            variables,
            lon_min,
            lon_max,
            lat_min,
            lat_max,
            start_datetime_local,
            end_datetime_local,
            difference_to_UTC,
            output_path,
            file_format,
            output_filename,
        )

    @classmethod
    def for_winds(
        cls,
        dataset_id: str,
        variables: List[str],
        lon_min: float,
        lon_max: float,
        lat_min: float,
        lat_max: float,
        start_datetime_local: datetime,
        end_datetime_local: datetime,
        difference_to_UTC: float,
        output_path: str,
        file_format: str = "netcdf",
        output_filename: Optional[str] = "winds_CMDS.nc",
    ) -> "CMDSDownloader":
        return cls(
            dataset_id,
            variables,
            lon_min,
            lon_max,
            lat_min,
            lat_max,
            start_datetime_local,
            end_datetime_local,
            difference_to_UTC,
            output_path,
            file_format,
            output_filename,
        )
