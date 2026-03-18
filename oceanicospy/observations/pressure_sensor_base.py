from abc import ABC, abstractmethod
import pandas as pd
from scipy.signal import detrend
import numpy as np

from oceanicospy.utils import constants


class BaseLogger(ABC):
    """
    Initializes the BaseLogger class with the given directory path, sampling data.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the sensor pressure files.
    sampling_data : dict
        Dictionary containing information on device installation, including:
        
        - ``start_time``: The start time of the sampling period.
        - ``end_time``: The end time of the sampling period.
        - ``sampling_rate``: The sampling rate of the device (Hz)
        - ``burst_duration``: The duration of each burst (seconds)
    """
    def __init__(self, directory_path: str, sampling_data: dict):

        self.directory_path = directory_path
        self.sampling_data = sampling_data

    @property
    def first_record_time(self):
        """
        Returns the timestamp of the first record in the dataset.

        Returns
        -------
        pandas.Timestamp
            The timestamp of the first available record.
        """
        try:
            time=self._load_raw_dataframe()['date']

        except:
            time=self._load_raw_dataframe()['Time']

        return pd.to_datetime(time.values[0])

    @property
    def first_submerged_record_time(self):
        """
        Returns the timestamp of the first record in the dataset where the sensor is submerged.

        Returns
        -------
        pandas.Timestamp
            The timestamp of the first available record where the sensor is submerged.
        """
        df = self._load_raw_dataframe()
        df = self._standardize_columns(df)
        if 'depth[m]' in df.columns:
            sign_depth = np.sign(df['depth[m]'])

            # identifying changes in depth from negative to positive (submerged)
            idx_changes = np.where(np.diff(sign_depth) > 0)[0] +1
            if len(idx_changes) > 0:
                timestamp = pd.to_datetime(df.index[idx_changes[0]])
                if timestamp.minute != 0:
                    return timestamp.ceil('h')
                else:
                    return timestamp
            else:
                return "Sensor was never submerged"
    
    @property
    def last_record_time(self):
        """
        Returns the timestamp of the last record in the dataset.

        Returns
        -------
        pandas.Timestamp
            The timestamp of the first available record.
        """
        try:
            time=self._load_raw_dataframe()['date']
        except:
            time=self._load_raw_dataframe()['Time']

        return pd.to_datetime(time.values[-1])
    
    @property
    def last_submerged_record_time(self):
        """
        Returns the timestamp of the last record in the dataset where the sensor is submerged.

        Returns
        -------
        pandas.Timestamp
            The timestamp of the last available record where the sensor is submerged.
        """
        df = self._load_raw_dataframe()
        df = self._standardize_columns(df)
        if 'depth[m]' in df.columns:
            sign_depth = np.sign(df['depth[m]'])

            # identifying changes in depth from positive to negative (emerged)
            idx_changes = np.where(np.diff(sign_depth) < 0)[0] + 1 # what if there are many?

            if len(idx_changes) > 0:
                timestamp = pd.to_datetime(df.index[idx_changes[0]])
            else:
                timestamp = pd.to_datetime(df.index[-1])
            return timestamp.floor('h')

    def get_raw_records(self) -> pd.DataFrame:
        """
        Reads the records file from the device to create a DataFrame containing data.

        Returns
        -------
        pandas.DataFrame
            A DataFrame containing the raw data indexed by timestamp.
        """
        df = self._load_raw_dataframe()
        df = self._standardize_columns(df)
        df = self._parse_dates_and_trim(df)
        return df

    def get_clean_records(self, detrended: bool = True) -> pd.DataFrame:
        """
        Processes the raw data by grouping the series per each burst

        Parameters
        ----------
        detrended : bool, optional
            If True, applies a linear detrending to the depth data within each burst. Default is ``True``.

        Returns
        -------
        pandas.DataFrame
            A cleaned DataFrame with bursts identified by a 'burstId' column.
        """

        df = self.get_raw_records()
        df = self._compute_depth_from_pressure(df)
        df = self._assign_burst_id(df)
        df['eta[m]'] = df.groupby('burstId')['depth[m]'].transform(lambda x: x - x.mean())

        if detrended:
            df['eta[m]'] = df.groupby('burstId')['eta[m]'].transform(lambda x: detrend(x.values, type='linear'))

        return df

    def _parse_dates_and_trim(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            start = self.first_submerged_record_time
            end = self.last_submerged_record_time
            print(start,end)
        except KeyError:
            raise KeyError("Missing 'start_time' or 'end_time' in sampling_data.")
        except Exception as e:
            raise ValueError(f"Invalid time format in 'sampling_data': {e}")

        return df[start:end]

    def _compute_depth_from_pressure(self, df: pd.DataFrame) -> pd.DataFrame:
        df['depth_aux[m]'] = ((df['pressure[bar]'] - constants.ATM_PRESSURE_BAR) * 1e5) / (constants.WATER_DENSITY * constants.GRAVITY)

        if (df['depth_aux[m]'] - df['depth[m]']).abs().max() <= 0.1:
            df = df.drop(columns=['depth_aux[m]'])
        return df

    @abstractmethod
    def _get_records_file(self) -> pd.DataFrame:
        """Returns the first records file found in the directory. Raises if none are found."""
        pass

    @abstractmethod
    def _load_raw_dataframe(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        pass