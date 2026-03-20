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
    filepath : str
        Path to the file containing the raw Davis Vantage Pro weather station data.

    Notes
    -----
    The raw file format uses single-character tokens for AM/PM (``'a'``/``'p'``)
    and ``'---'`` as a sentinel for missing values. Both are normalized during
    loading and cleaning respectively.
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
        - ``'a'`` and ``'p'`` tokens in the ``AM/PM`` column are replaced with ``'AM'`` and ``'PM'`` respectively.
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
        """
        Clean and standardize the raw DataFrame for analysis.

        Parameters
        ----------
        df : pandas.DataFrame
            Raw DataFrame as returned by ``_load_raw_dataframe``, with
            string-typed columns and ``'---'`` as the missing-value token.

        Returns
        -------
        pandas.DataFrame
            Cleaned DataFrame indexed by ``date`` (``datetime64[ns]``),
            with all-NaN columns removed and ``Speed`` cast to ``float``.

        Notes
        -----
        Timestamp parsing uses the format ``'%m/%d/%y %I:%M %p'``, which
        matches the Davis Vantage Pro 12-hour clock export (e.g.
        ``'01/15/24 02:30 PM'``). Files with a different clock format will
        raise a ``ValueError`` at the ``pd.to_datetime`` call.
        """
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
        """
        Convert cardinal wind direction labels to decimal degrees.

        Maps the string values in the ``Dir1`` column to their corresponding
        compass bearings using an 8-point rose (N, NE, E, SE, S, SW, W, NW).
        The result is stored in a new ``Direction`` column. Any ``Dir1`` value
        not present in the mapping (including ``NaN``) will produce ``NaN`` in
        the output column.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame containing a ``Dir1`` column with cardinal direction
            strings (e.g. ``'N'``, ``'SW'``).

        Returns
        -------
        pandas.DataFrame
            The input DataFrame with an additional ``Direction`` column
            (``float64``) holding wind direction in decimal degrees (0–360),
            where 0° = North, increasing clockwise.
        """
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