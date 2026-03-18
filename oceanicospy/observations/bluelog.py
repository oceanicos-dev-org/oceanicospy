import glob
import pandas as pd
import os
from datetime import datetime
from io import StringIO

from .pressure_sensor_base import BaseLogger

class BlueLog(BaseLogger):
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
        files = glob.glob(os.path.join(self.directory_path, '*.csv'))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        return files[0]
    
    def _load_raw_dataframe(self):
        filepath = self._get_records_file()
        pass

    # This method is specific to bluelog

    def load_filtered_data(self):
        """
        Reads the CSV file, extracts the configured start time, finds the data start index,
        and loads the data into a filtered pandas DataFrame.
        """
        # Read file content line by line
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

        # Initialize index and time
        data_start_index = None

        for i, line in enumerate(lines):
            # Look for the configured start time
            if line.startswith("# Configured Start Time:"):
                time_str = line.strip().split(": ")[1]
                self.start_time = datetime.strptime(time_str, "%Y%m%d%H%M")

            # Find the '---' line that separates header from data
            if line.strip() == "---":
                data_start_index = i + 1
                break

        if self.start_time is None or data_start_index is None:
            raise ValueError("Configured start time or data section not properly found.")

        # Extract the lines that represent actual data
        data_lines = lines[data_start_index:]
        data_str = ''.join(data_lines)

        # Read the data into a DataFrame
        df = pd.read_csv(
            StringIO(data_str),
            names=["Timestamp", "Pressure_bar", "Temperature_C"],
            skip_blank_lines=True
        )

        # Force conversion of Timestamp to datetime, drop rows with invalid timestamps
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
        df = df.dropna(subset=["Timestamp"])

        # Filter rows based on the configured start time
        df = df[df["Timestamp"] >= self.start_time]

        # Reset index and store the result
        self.df = df.reset_index(drop=True)

    def get_dataframe(self):
        """
        Returns the filtered DataFrame. Loads the data if not already loaded.
        """
        if self.df is None:
            self.load_filtered_data()
        return self.df

    def _standardize_columns(self, df):
        pass

    def _assign_burst_id(self, df):
        pass

