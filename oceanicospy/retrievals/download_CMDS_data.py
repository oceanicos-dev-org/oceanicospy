# download_CMDS_data.py

import copernicusmarine
from datetime import datetime
from zoneinfo import ZoneInfo  # Use pytz if Python < 3.9
import os

class CMDSDownloader:
    """
    A class to handle downloading data from the Copernicus Marine Data Store (CMDS)
    with automatic UTC time conversion from user-defined local timezone.
    """

    def __init__(self,
                 dataset_id: str,
                 variables: list,
                 lon_min: float,
                 lon_max: float,
                 lat_min: float,
                 lat_max: float,
                 start_datetime_local: str,
                 end_datetime_local: str,
                 local_timezone: str = "America/Bogota",
                 output_path: str = "./"):
        """
        Initializes the CMDSDownloader.

        Parameters
        ----------
        dataset_id : str
            The ID of the dataset to download from CMDS.
        variables : list
            A list of variable names to request.
        lon_min : float
            Minimum longitude of the spatial domain.
        lon_max : float
            Maximum longitude of the spatial domain.
        lat_min : float
            Minimum latitude of the spatial domain.
        lat_max : float
            Maximum latitude of the spatial domain.
        start_datetime_local : str
            Start datetime in local timezone (e.g. "2025-08-17T00:00:00").
        end_datetime_local : str
            End datetime in local timezone (e.g. "2025-08-17T12:00:00").
        local_timezone : str
            IANA timezone string (e.g. "America/Bogota"). Default is UTC-5.
        output_path : str
            Path to save the downloaded file. Default is current directory.
        """
        self.dataset_id = dataset_id
        self.variables = variables
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.output_path = output_path

        # Convert from local timezone to UTC
        self.start_datetime_utc = self._convert_to_utc(start_datetime_local, local_timezone)
        self.end_datetime_utc = self._convert_to_utc(end_datetime_local, local_timezone)

    def _convert_to_utc(self, time_str: str, local_timezone: str) -> str:
        """
        Converts a datetime string in local timezone to UTC ISO 8601 format.
        """
        local_dt = datetime.fromisoformat(time_str).replace(tzinfo=ZoneInfo(local_timezone))
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
        return utc_dt.isoformat()

    def download(self):
        """
        Executes the download request using the copernicusmarine.subset API.
        """
        os.makedirs(self.output_path, exist_ok=True)

        copernicusmarine.subset(
            dataset_id=self.dataset_id,
            variables=self.variables,
            minimum_longitude=self.lon_min,
            maximum_longitude=self.lon_max,
            minimum_latitude=self.lat_min,
            maximum_latitude=self.lat_max,
            start_datetime=self.start_datetime_utc,
            end_datetime=self.end_datetime_utc,
            output_directory=self.output_path
        )

        print(f"Download completed from {self.start_datetime_utc} to {self.end_datetime_utc} (UTC).")
