import pandas as pd
import glob
import os

from .pressure_sensor_base import BaseLogger

class AQUAlogger(BaseLogger):
    """
    A sensor-specific reader for AQUAlogger CSV files.

    Inherits from ``BaseLogger`` and implements methods specific to AQUAlogger file formats.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the .csv files.
    sampling_data : dict
        Dictionary containing information on device installation, including:
        
        - ``start_time``: The start time of the sampling period.
        - ``end_time``: The end time of the sampling period.
        - ``sampling_rate``: The sampling rate of the device (Hz)
        - ``burst_duration``: The duration of each burst (seconds)

    """

    @property
    def first_record_time(self):
        """
        See :attr:BaseLogger.first_record_time
        """
        return super().first_record_time
    
    @property
    def last_record_time(self):
        """
        See :attr:BaseLogger.last_record_time 
        """
        return super().last_record_time

    def _get_records_file(self):
        files = glob.glob(os.path.join(self.directory_path, '*.csv'))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        return files[0]
    
    def _load_raw_dataframe(self) -> pd.DataFrame:
        filepath = self._get_records_file()
        if self.sampling_data.get('temperature', False):
            columns = ['UNITS', 'date', 'Raw1', 'temperature', 'Raw2', 'pressure[bar]', 'Raw3', 'depth[m]', 'nan']
            drop_cols = ['Raw1', 'Raw2', 'Raw3', 'nan']
        else:
            columns = ['UNITS', 'date', 'Raw1', 'pressure[bar]', 'nan']
            # columns = ['UNITS', 'date', 'Raw1', 'pressure[bar]', 'Raw2', 'depth[m]', 'nan']
            drop_cols = ['Raw1', 'nan']

        df = pd.read_csv(filepath, names=columns, header=13, encoding='latin-1') # will be 21 depending on the file format
        df = df.drop(columns=drop_cols)
        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        df['burstId'] = (df['UNITS'] == 'BURSTSTART').cumsum()
        return df.drop(columns=['UNITS'])