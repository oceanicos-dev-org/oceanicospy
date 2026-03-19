from datetime import datetime
import glob
import os
import pandas as pd

from .pressure_sensor_base import BaseLogger

class Bluelog(BaseLogger):
    """
    A reader for BlueLog files.

    Inherits from ``BaseLogger`` and implements methods specific to BlueLog file formats.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing the BlueLog .csv file.
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
        # TODO: this has to be modified to be more specific to the bluelog file, maybe looking for a specific name or pattern in the name.
        files = glob.glob(os.path.join(self.directory_path, '*.csv'))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        return files[0]
    
    def _load_raw_dataframe(self):
        """
        Reads the CSV file, extracts the configured start time, finds the data start index,
        and loads the data into a filtered pandas DataFrame.
        """
        filepath = self._get_records_file()
        # Read file content line by line
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                # Look for the configured start time
                if line.startswith("# Configured Start Time:"):
                    time_str = line.strip().split(": ")[1]
                    self.start_time = datetime.strptime(time_str, "%Y%m%d%H%M")
                # Find the '---' line that separates header from data
                if line.strip() == "---":
                    line_header_number = lineno + 1
                    break

        if self.start_time is None or line_header_number is None:
            raise ValueError("Configured start time or data section not properly found.")

        # Load the data into a DataFrame, skipping lines before the header
        df = pd.read_csv(filepath, skiprows=line_header_number-1)
        return df

    def _standardize_columns(self, df):
        new_columns = {}
        
        for col in df.columns:
            col_lower = col.lower()
            col_lower = col_lower.replace("(", "[")  
            col_lower = col_lower.replace(")", "]")  
            col_lower = col_lower.strip() # Remove spaces for easier matching

            if 'timestamp' in col_lower:
                new_columns[col] = 'date'
            # Rename pressure[dbar] → pressure [bar]
            elif 'pressure' in col_lower and 'dbar' in col_lower:
                new_columns[col] = 'pressure[bar]'
            else:
                new_columns[col] = col_lower  # keep as is
        
        # Apply renaming
        df = df.rename(columns=new_columns)
        
        # Convert units if pressure column exists
        if 'pressure[bar]' in df.columns:
            df['pressure[bar]'] = df['pressure[bar]'] / 10.0
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.set_index('date')
        return df
    
    def _assign_burst_id(self, df):
        df['burstId'] = pd.factorize(df.index.floor('h'))[0] + 1
        return df

