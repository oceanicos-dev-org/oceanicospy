import glob
import pandas as pd
import os

from .pressure_sensor_base import BaseLogger

class AQUAlogger(BaseLogger):
    """
    A sensor-specific reader for AQUAlogger files.

    Inherits from ``BaseLogger`` and implements methods specific to AQUAlogger file formats.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the .csv files.
    sampling_data : dict
        Dictionary containing information on device deployment, including:
        
        - ``start_time``: The start time of the sampling period.
        - ``end_time``: The end time of the sampling period.
        - ``sampling_rate``: The sampling rate of the device (Hz)
        - ``burst_duration``: The duration of each burst (seconds)

    Notes
    -----
    The following models are supported: AQUAlogger520PT5 and AQUAlogger520P4 

    """
    @property
    def first_record_time(self):
        """
        See :attr:BaseLogger.first_record_time
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
        See :attr:BaseLogger.last_record_time 
        """
        return super().last_record_time
    
    @property
    def last_submerged_record_time(self):
        """
        See :attr:BaseLogger.last_submerged_record_time
        """
        return super().last_submerged_record_time

    def _get_records_file(self):
        files = glob.glob(os.path.join(self.directory_path, '*.csv'))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        
        if len(files) == 1:
            return files[0]

        if not self.filename:
            raise ValueError("Multiple .csv files found. Please specify the filename to use.")
        
        if not self.filename.endswith('.csv'):
            self.filename += '.csv'
        
        matching_files = [f for f in files if os.path.basename(f) == self.filename]
        if not matching_files:
            raise FileNotFoundError(f"No file named '{self.filename}' found in the directory.")
        return matching_files[0]          
    
    def _load_raw_dataframe(self):
        filepath = self._get_records_file()
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if line.startswith("HEADING"):
                    line_header_number = lineno
                    line_units = next(f)
                    break
    
        header = line.strip().split(",")
        units = line_units.strip().split(",")

        header_names = [h.strip().lower() for h in header]
        units_names = [u.strip().lower() for u in units]

        # Playing with the header and units to create column names
        col_names = []
        for i in range(len(header_names)):
            if units_names[i] == 'units':
                col_name = 'units'
            elif units_names[i] == 'timecode':
                col_name = 'date'
            elif units_names[i] == 'raw':
                col_name = header_names[i]+f'[{units_names[i]}]'
            elif header_names[i] == '':
                col_name = header_names[i-1]+f'[{units_names[i]}]'
            else:
                pass
            col_names.append(col_name)
        
        df = pd.read_csv(filepath, names=col_names, header=line_header_number, encoding='latin-1')
        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        # Extract columns containing 'raw' or '[]'
        raw_columns = [col for col in df.columns if 'raw' in col.lower() or '[]' in col]
        df = df.drop(columns=raw_columns)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')        
        df = df.set_index('date')
        return df

    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        df['burstId'] = (df['units'] == 'BURSTSTART').cumsum()
        return df.drop(columns=['units'])