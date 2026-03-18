import pandas as pd
import glob
import os

from .pressure_sensor_base import BaseLogger

class RBR(BaseLogger):
    """
    A sensor-specific reader for RBR .txt files.

    Inherits from ``BaseLogger`` and implements methods specific to RBR file formats.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the .txt files.
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
        See :attr:`BaseLogger.first_record_time`
        """
        return super().first_record_time

    @property
    def first_submerged_record_time(self):
        """
        See :attr:BaseLogger.first_submerged_record_time
        """
        return super().first_submerged_record_time
    
    @property
    def last_record_time(self):
        """
        See :attr:`BaseLogger.last_record_time` 
        """
        return super().last_record_time

    def _get_records_file(self):
        files = glob.glob(os.path.join(self.directory_path, '*_data.txt'))

        if not files:
            raise FileNotFoundError("No .txt file found in the specified directory.")
        return files[0]

    def _load_raw_dataframe(self) -> pd.DataFrame:
        filepath = self._get_records_file()
        df = pd.read_csv(filepath)
        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop(columns=['Sea pressure'], errors='ignore')
        df = df.rename(columns={'Pressure': 'pressure[bar]', 'Depth': 'depth[m]'})
        df['pressure[bar]'] = df['pressure[bar]'] / 10  # dbar to bar
        df['Time'] = pd.to_datetime(df['Time'])
        df = df.rename(columns={'Time': 'date'})
        df = df.set_index('date')
        return df

    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        df['burstId'] = pd.factorize(df.index.floor('h'))[0] + 1
        return df
