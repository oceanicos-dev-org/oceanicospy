import requests
import pandas as pd

from pathlib import Path

class UHSLCDownloader:
    """
    Downloader for hourly sea-level data from the University of Hawaii Sea Level Center (UHSLC).

    Fetches Fast-Delivery CSV files from the UHSLC public data server and writes
    them to a user-specified output directory.

    Parameters
    ----------
    station_id : str
        UHSLC station code (e.g. ``"057"``). Used to build the filename
        ``h<station_id>.csv`` as published on the UHSLC server.
    output_path : str or Path
        Directory where the downloaded file will be saved.
    start_date : str, optional
        Start of the date range to keep after cleaning (e.g. ``"2010-01-01"``).
        Passed to ``pandas.to_datetime``; if ``None`` the series is not trimmed
        at the start.
    end_date : str, optional
        End of the date range to keep after cleaning (e.g. ``"2020-12-31"``).
        Passed to ``pandas.to_datetime``; if ``None`` the series is not trimmed
        at the end.
    """

    BASE_URL = "https://uhslc.soest.hawaii.edu/data/csv/fast/hourly/"

    def __init__(self, station_id: str, output_path: str | Path, start_date: str | None = None, end_date: str | None = None) -> None:
        self.station_id = station_id
        self.output_path = Path(output_path)
        self.start_date = start_date
        self.end_date = end_date

    def download(self) -> Path:
        """
        Download the hourly sea-level CSV for the configured station.

        Sends a GET request to the UHSLC Fast-Delivery server and writes
        the response content to ``output_path / h<station_id>.csv``.

        Returns
        -------
        Path
            Absolute path of the saved CSV file.

        Raises
        ------
        requests.HTTPError
            If the server returns a non-200 status code.
        OSError
            If the output directory cannot be created or the file cannot be written.
        """
        filename = f"h{self.station_id}.csv"
        file_url = self.BASE_URL + filename

        response = requests.get(file_url)
        response.raise_for_status()

        self.output_path.mkdir(parents=True, exist_ok=True)
        dest = self.output_path / filename
        dest.write_bytes(response.content)

        print(f"Downloaded {filename} to {dest}.")
        return dest
    
    def clean_data(self, filepath: str | Path) -> pd.DataFrame:
        """
        Load and clean a downloaded UHSLC CSV file.

        Parses the raw UHSLC hourly format (year, month, day, hour, depth in mm),
        converts depth to metres, and optionally trims the time series to the
        ``[start_date, end_date]`` window provided at construction time.

        Parameters
        ----------
        filepath : str or Path
            Path to the downloaded UHSLC CSV file.

        Returns
        -------
        pandas.DataFrame
            DataFrame indexed by datetime with a single column ``depth[m]``.
            If ``start_date`` or ``end_date`` were set on the instance, the
            returned series is trimmed accordingly; otherwise the full record
            is returned.

        Notes
        -----
        - Timestamps in the raw file are in UTC. A timezone shift to local time
          is not applied here yet (TODO).
        - Rows with ``depth[mm]`` equal to ``-32400`` (UHSLC missing-data flag)
          are not filtered out by this method.
        """
        df = pd.read_csv(
            filepath,
            header=None,
            names=["year", "month", "day", "hour", "depth[mm]"],
            sep=",",
        )

        df.index = pd.to_datetime(df[["year", "month", "day", "hour"]])
        df["depth[m]"] = df["depth[mm]"] / 1000.0
        df = df.drop(columns=["year", "month", "day", "hour", "depth[mm]"])

        if self.start_date is not None:
            df = df.loc[pd.to_datetime(self.start_date):]
        if self.end_date is not None:
            df = df.loc[:pd.to_datetime(self.end_date)]

        # TODO: add optional shift to local timezone (e.g. UTC-5)
        return df
