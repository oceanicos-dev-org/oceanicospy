import os
from datetime import datetime, timedelta
from typing import List, Optional
import copernicusmarine


class CMDSDownloader:
    """
    Copernicus Marine Data Store (CMDS) downloader mirroring ERA5 input style.
    Supports downloading waves and winds (or any variables) to NetCDF or Zarr
    using the `copernicusmarine.subset` Python API.

    Notes
    -----
    - You MUST pass the correct `dataset_id` (dataset-level identifier in CMDS)
      and `variables` for the chosen product.
    - Time conversion uses a fixed local-to-UTC offset (difference_to_UTC) like ERA5Downloader.
      Example: UTC-5 -> difference_to_UTC = -5.
    """

    def __init__(self,
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
                 output_filename: Optional[str] = None):
        """
        Parameters
        ----------
        dataset_id : str
            CMDS dataset identifier (not product ID).
        variables : list[str]
            Variable names exposed by the dataset (e.g., ["VHM0"] or ["u10","v10"]).
        lon_min, lon_max, lat_min, lat_max : float
            Bounding box in degrees (EPSG:4326).
        start_datetime_local, end_datetime_local : datetime
            Start/end datetimes in local time.
        difference_to_UTC : float
            Local time minus UTC (hours). Example: UTC-5 -> -5.
        output_path : str
            Directory or filename path where the output will be written.
            If `output_filename` is None, `copernicusmarine.subset` will choose one inside `output_path`
            (treated as a directory). If `output_filename` is provided, it will be used.
        file_format : str, default "netcdf"
            One of {"netcdf", "zarr"} depending on dataset support.
        output_filename : str | None, default None
            Desired output filename (e.g., "waves.nc"). If None, CMDS assigns one.
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

        # Convert local datetimes to UTC using the signed hour difference, like the ERA5 class
        if self.difference_to_UTC >= 0:
            self.start_datetime_utc = self.start_datetime_local - timedelta(hours=self.difference_to_UTC)
            self.end_datetime_utc = self.end_datetime_local - timedelta(hours=self.difference_to_UTC)
        else:
            self.start_datetime_utc = self.start_datetime_local + timedelta(hours=abs(self.difference_to_UTC))
            self.end_datetime_utc = self.end_datetime_local + timedelta(hours=abs(self.difference_to_UTC))

    def download(self) -> str:
        """
        Execute the subset/download request via the Copernicus Marine Toolbox API.

        Returns
        -------
        str
            Absolute path to the created file or directory (NetCDF file or Zarr store).
        """
        # Ensure output directory exists when a directory is intended
        if self.output_filename is None:
            os.makedirs(self.output_path, exist_ok=True)
            output_directory = self.output_path
        else:
            # If a filename was given, ensure its parent directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.output_path)) or ".", exist_ok=True)
            output_directory = os.path.dirname(os.path.abspath(self.output_path)) or "."

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

        # If a custom filename was requested, prefer it over the auto-named default
        if self.output_filename is not None:
            subset_kwargs["output_filename"] = self.output_filename

        result_path = copernicusmarine.subset(**subset_kwargs)

        # The API returns the resulting path; make it absolute for consistency
        abs_path = os.path.abspath(result_path if isinstance(result_path, str) else output_directory)
        return abs_path

    # ---------------- Convenience constructors (optional) ----------------

    @classmethod
    def for_waves(cls,
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
                  output_filename: Optional[str] = "waves.nc") -> "CMDSDownloader":
        """
        Convenience constructor for wave datasets (e.g., variables like VHM0, VTM10).
        """
        return cls(dataset_id, variables, lon_min, lon_max, lat_min, lat_max,
                   start_datetime_local, end_datetime_local, difference_to_UTC,
                   output_path, file_format, output_filename)

    @classmethod
    def for_winds(cls,
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
                  output_filename: Optional[str] = "winds.nc") -> "CMDSDownloader":
        """
        Convenience constructor for wind datasets (e.g., variables like u10/v10
        or eastward_wind/northward_wind, depending on dataset naming).
        """
        return cls(dataset_id, variables, lon_min, lon_max, lat_min, lat_max,
                   start_datetime_local, end_datetime_local, difference_to_UTC,
                   output_path, file_format, output_filename)
