import cdsapi
import xarray as xr
import numpy as np
from datetime import datetime,timedelta

c = cdsapi.Client()

class ERA5Downloader():
    """
    A class to handle downloading data from the Copernicus Marine Data Store (CMDS)
    with automatic UTC time conversion from user-defined local timezone.
    """
    def __init__(self,variables:list,
                 lon_min: float,
                 lon_max: float,
                 lat_min: float,
                 lat_max: float,
                 start_datetime_local: datetime,
                 end_datetime_local: datetime,
                 difference_to_UTC: float,
                 output_path: str):
        """
        Initializes the ERA5Downloader.

        Parameters
        ----------
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
        start_datetime_local : datetime.datetime
            Start datetime in local timezone 
        end_datetime_local : str
            End datetime in local timezone
        difference_to_UTC : float
            Difference in hours from local timezone to UTC (e.g. -5 for UTC-5)
        output_path : str
        """
        self.variables = variables
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.start_datetime_local = start_datetime_local
        self.end_datetime_local = end_datetime_local
        self.difference_to_UTC = difference_to_UTC
        self.output_path = output_path

        if self.difference_to_UTC>=0:
            self.start_datetime_utc = self.start_datetime_local - timedelta(hours=self.difference_to_UTC)
            self.end_datetime_utc   = self.end_datetime_local - timedelta(hours=self.difference_to_UTC)
        else: 
            self.start_datetime_utc = self.start_datetime_local + timedelta(hours=abs(self.difference_to_UTC))
            self.end_datetime_utc   = self.end_datetime_local + timedelta(hours=abs(self.difference_to_UTC))

    def _prepare_datetime_data(self):
        """
        Generates a dictionary mapping each (year, month) tuple to a list of day strings within the specified date range.
        Iterates from self.start_datetime_utc to self.end_datetime_utc (inclusive), grouping days by their corresponding year and month.
        The keys of the returned dictionary are tuples of (year, month_str), where month_str is a zero-padded month string (e.g., '01' for January).
        The values are lists of zero-padded day strings (e.g., '05' for the 5th day of the month) that fall within the specified date range.

        Returns:
        -------
            dict: A dictionary with keys as (year, month_str) and values as lists of day strings.
        """

        current = self.start_datetime_utc
        days_by_month = {}
        while current <= self.end_datetime_utc+timedelta(days=1):
            month_str = current.strftime("%m")
            days_by_month.setdefault((current.year, month_str), []).append(current.strftime("%d"))
            current += timedelta(days=1)
        
        years = list({str(y) for (y, _) in days_by_month.keys()})
        months = list({m for (_, m) in days_by_month.keys()})
        days = [d for (_, m) in days_by_month.keys() for d in days_by_month[(int(_), m)]]
        return years,months,days

    def download(self):
        """
        Executes the download request using the ERA5 API.
        """
        years_to_download,months_to_download,days_to_download = self._prepare_datetime_data()

        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'format': 'netcdf',
                'variable': self.variables,
                'year': years_to_download,
                'month': months_to_download,
                'day': days_to_download, # This has to be checked
                'time': [f"{h:02d}:00" for h in range(24)],
                'area': [self.lat_max,self.lon_min,self.lat_min,self.lon_max],  # North, West, South, East
                'grid': [0.025, 0.025],
            },
            self.output_path)
    
    def format_to_localtime(self):
        ds = xr.load_dataset(self.output_path)
        if self.difference_to_UTC>=0:
            ds['valid_time'] = ds['valid_time'] + np.timedelta64(self.difference_to_UTC, 'h')
        else:
            ds['valid_time'] = ds['valid_time'] - np.timedelta64(abs(self.difference_to_UTC), 'h')

        mask = (ds['valid_time'] >= np.datetime64(self.start_datetime_local)) & \
            (ds['valid_time'] <= np.datetime64(self.end_datetime_local))
        ds_cropped = ds.sel(time=mask) if 'time' in ds.dims else ds.sel(valid_time=mask)
        ds_cropped.to_netcdf(self.output_path, mode='w', format='NETCDF4')
