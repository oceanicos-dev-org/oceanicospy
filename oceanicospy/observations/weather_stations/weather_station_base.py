from abc import ABC, abstractmethod


class WeatherStationBase(ABC): 
    """
        
    Notes
    -----
    19-Mar-2025 : initial version - Franklin Ayala
    16-Jul-2025 : adding weathersens model - Daniela Rosero
    """

    def __init__(self,filepath: str):
        self.filepath = filepath

    @property
    def first_record_time(self):
        """Get the first record time from the dataframe."""
        return self.clean_records.index.min()

    @property
    def last_record_time(self):
        """Get the last record time from the dataframe."""
        return self.clean_records.index.max()

    def get_raw_records(self):
        """Get raw records from the data source."""
        df = self._load_raw_dataframe()
        return df

    def get_clean_records(self):
        """Get clean records with standardized columns."""
        df = self.get_raw_records()
        df = self._standardize_columns(df)

        return df

    @abstractmethod
    def _load_raw_dataframe(self):
        """Load raw dataframe from source."""
        pass

    @abstractmethod
    def _standardize_columns(self, df):
        """Standardize column names and format."""
        pass

    @abstractmethod
    def _compute_direction_degrees(self, df):
        """Compute wind direction in degrees if applicable."""
        pass