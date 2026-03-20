import pandas as pd

class Buoy():
    """
    A class to handle reading and processing Spotter buoy data in CSV format.
    Automatically detects the file format and processes accordingly.

    Inherits
    --------
    BaseLogger : abstract class
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def _detect_source(self, df: pd.DataFrame) -> str:
        """
        Detects the format of the Spotter CSV file based on column names.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame loaded from the CSV file.
        
        Returns
        -------
        str
            The detected source ('aqualink' or 'sofar').

        Raises
        ------
        ValueError
            If the CSV file source is not recognized.
        """
        if 'Epoch Time' in df.columns:
            return 'sofar'
        elif 'timestamp' in df.columns:
            return 'aqualink'
        else:
            raise ValueError("CSV file source is not recognized. Expected 'Epoch Time' or 'timestamp' column.")

    def _load_raw_dataframe(self) -> pd.DataFrame:
        """
        Loads the raw CSV file into a DataFrame and detects its format. Processes the DataFrame accordingly.

        Returns
        -------
        pd.DataFrame
            The processed DataFrame.
        """
        df = pd.read_csv(self.filepath)

        file_format = self._detect_source(df)

        if file_format == 'sofar':
            return self._process_format_sofar(df)
        else:
            return self._process_format_aqualink(df)

    def _process_format_sofar(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes Spotter CSV files coming from SOFAR with 'Epoch Time' column.

        Parameters
        ----------
        df : pd.DataFrame
            The raw DataFrame loaded from the CSV file.
        
        Returns
        -------
        pd.DataFrame
            The processed DataFrame with datetime index and standardized columns.
        """
        df = df[pd.to_numeric(df['Epoch Time'], errors='coerce').notnull()].copy()

        # Convert to datetime in UTC-5, remove timezone
        df['date'] = pd.to_datetime(df['Epoch Time'], unit='s', utc=True) \
                        .dt.tz_convert('America/Bogota') \
                        .dt.tz_localize(None)

        # Sort chronologically for correct slicing by date
        df = df.sort_values('date')

        # Set index
        df = df.set_index('date')
        return df

    def _process_format_aqualink(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes Spotter CSV files from AQUAlink website with 'timestamp' column in ISO 8601 format.

        Parameters
        ----------
        df : pd.DataFrame
            The raw DataFrame loaded from the CSV file.
        
        Returns
        -------
        pd.DataFrame
            The processed DataFrame with datetime index and standardized columns.
        """
        # Convert ISO timestamp to datetime in UTC-5
        df['date'] = pd.to_datetime(df['timestamp'], utc=True) \
                        .dt.tz_convert('America/Bogota') \
                        .dt.tz_localize(None)

        # Reverse sort if necessary (most recent first)
        if df['date'].is_monotonic_decreasing:
            df = df.sort_values('date')

        # Set index
        df = df.set_index('date')

        return df

    def get_raw_records(self) -> pd.DataFrame:
        """
        Public method to get the raw records from the Spotter CSV file, processed and standardized.

        Returns
        -------
        pd.DataFrame
            The processed DataFrame with datetime index and standardized columns.
        """
        df = self._load_raw_dataframe()
        return df
    
    def get_clean_records(self) -> pd.DataFrame:
        """
        Public method to get the cleaned records from the Spotter CSV file, with standardized columns and burst IDs.

        Returns
        -------
        pd.DataFrame
            The cleaned DataFrame ready for analysis.
        """
        df = self.get_raw_records()
        #TODO: Implement _standardize_columns, _assign_burst_id, and _parse_dates_and_trim methods
        return df

#     def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Renames and converts Spotter-specific columns to a standardized format.
#         Includes wave, wind, and temperature variables from Spotter buoys.
#         """

#         # Manual rename for known fields from both formats
#         rename_map = {
#             'Significant Wave Height (m)': 'Hs[m]',
#             'Peak Period (s)': 'Tp[s]',
#             'Mean Period (s)': 'Tm[s]',
#             'Peak Direction (deg)': 'Peak_dir[°]',
#             'Mean Direction (deg)': 'Mean_dir[°]',
#             'Peak Directional Spread (deg)': 'Peak_dir_spread[°]',
#             'Mean Directional Spread (deg)':'Mean_dir_spread[°]',
#             'significant_wave_height_spotter': 'Hs[m]',
#             'wave_mean_period_spotter': 'Tm[s]',
#             'wave_mean_direction_spotter': 'Mean_dir[°]',
#             'wind_speed_spotter': 'Wind[m/s]',
#             'wind_direction_spotter': 'WindDir[°]',
#             'top_temperature_spotter': 'TempTop[°C]',
#             'bottom_temperature_spotter': 'TempBottom[°C]'
#         }

#         # Apply renaming where applicable
#         df = df.rename(columns=rename_map)

#         # Detect all columns that contain "spotter" (renamed or not) for conversion
#         spotter_cols = [col for col in df.columns if 'spotter' in col.lower() or 'spotter' in rename_map.get(col, '')]

#         # Convert all spotter-related columns to float
#         for col in spotter_cols:
#             if col in df.columns:
#                 df[col] = pd.to_numeric(df[col], errors='coerce')

#         # Drop rows with NaNs in the core spotter wave variables, if they exist
#         key_wave_vars = ['Hs[m]', 'Tp[s]', 'Dir[°]']
#         vars_present = [v for v in key_wave_vars if v in df.columns]
#         if vars_present:
#             df = df.dropna(subset=vars_present, how='any')

#         return df




#     def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Assigns burst IDs based on hourly bins.
#         """
#         df['burstId'] = pd.factorize(df.index.floor('H'))[0] + 1
#         return df

#     def _parse_dates_and_trim(self, df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Trims the DataFrame to the time range specified in sampling_data.
#         """
#         start = pd.to_datetime(self.sampling_data['start_time'])
#         end = pd.to_datetime(self.sampling_data['end_time'])

#         df_trimmed = df[start:end]

#         if df_trimmed.empty:
#             raise ValueError(
#                 f"No data found in the range {start} to {end}. "
#                 f"Available data is from {df.index.min()} to {df.index.max()}"
#             )

#         return df_trimmed