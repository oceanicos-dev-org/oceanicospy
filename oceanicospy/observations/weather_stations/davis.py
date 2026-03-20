import numpy as np
import pandas as pd
from .weather_station_base import WeatherStationBase


class DavisVantagePro(WeatherStationBase):
    """
    A sensor-specific reader for Davis Vantage Pro weather station files.

    Inherits from :class:`BaseWeatherStation` and implements file parsing methods
    specific to the Davis Vantage Pro comma-separated text format, including column
    renaming, unit conversion, and timestamp parsing.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the ``*_data.txt`` files.
    """

    def _load_raw_dataframe(self):
        """
        Reads weather station records from a specified file and processes the data into a pandas DataFrame.

        Returns
        -------
        df : pandas.DataFrame
            A DataFrame containing the processed weather station data

        Notes
        -----
            - The function assumes that the first two lines of the file are headers or metadata and skips them.
            - The 'AM/PM' column values are replaced with 'AM' and 'PM' for consistency.
        """
        
        with open(self.filepath, 'r') as file:
            data = file.read().split('\n')[2:-1]
        
        processed_data = [(' '.join(line.split())).split(' ') for line in data]
        
        columns = ['Date', 'time', 'AM/PM', 'Out', 'Temp1', 'Temp2', 'Hum', 'Pt.', 'Speed', 'Dir1', 'Run', 'Speed2', 'Dir2', 
                   'Chill', 'Index1', 'Index2', 'Bar', 'Rain', 'Rate', 'D-D1', 'D-D2', 'Temp4', 'Hum2', 'Dew', 'Heat', 'EMC', 
                   'Density', 'Samp', 'Tx', 'Recept', 'Int.']
        
        df = pd.DataFrame(processed_data, columns=columns)
        df['AM/PM'] = df['AM/PM'].replace({'a': 'AM', 'p': 'PM'})
        
        return df

    def _standardize_columns(self, df):
        df.replace('---', np.nan, inplace=True)
        df.dropna(axis=1, how='all', inplace=True)
        
        df['date'] = pd.to_datetime(df['Date'] + ' ' + df['time'] + ' ' + df['AM/PM'], 
                               format='%m/%d/%y %I:%M %p')
        df = df.drop(['Date', 'time', 'AM/PM'], axis=1)
        df = df.set_index('date')
        dtypes = {'Speed': float}
        df = df.astype(dtypes)
        return df

    def _compute_direction_degrees(self, df):
        direction_mapping = {
            'N': 0,
            'NE': 45,
            'E': 90,
            'SE': 135,
            'S': 180,
            'SW': 225,
            'W': 270,
            'NW': 315
        }
        df['Direction'] = df['Dir1'].map(direction_mapping)
        return df