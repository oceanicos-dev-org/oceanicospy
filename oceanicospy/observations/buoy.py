import pandas as pd
import os
import glob

from .pressure_sensor_base import BaseLogger

class Buoy(BaseLogger):
    """
    A class to handle reading and processing Spotter buoy data in CSV format.
    Automatically detects the file format and processes accordingly.

    Inherits
    --------
    BaseLogger : abstract class
    """

    def _get_records_file(self):
        files = glob.glob(os.path.join(self.directory_path, '*.csv'))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        return files[0]

    def _detect_format(self, df: pd.DataFrame) -> str:
        """
        Detects the format of the Spotter CSV file based on column names.
        Returns 'epoch' or 'iso8601'.
        """
        if 'Epoch Time' in df.columns:
            return 'epoch'
        elif 'timestamp' in df.columns:
            return 'iso8601'
        else:
            raise ValueError("CSV file format not recognized. Expected 'Epoch Time' or 'timestamp' column.")

    def _load_raw_dataframe(self) -> pd.DataFrame:
        filepath = self._get_records_file()
        df = pd.read_csv(filepath)

        file_format = self._detect_format(df)

        if file_format == 'epoch':
            return self._process_format_epoch(df)
        else:
            return self._process_format_iso8601(df)

    def _process_format_epoch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes old format Spotter CSVs with 'Epoch Time' column.
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

    def _process_format_iso8601(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes new format Spotter CSVs with 'timestamp' in ISO 8601 format.
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

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Renames and converts Spotter-specific columns to a standardized format.
        Includes wave, wind, and temperature variables from Spotter buoys.
        """

        # Manual rename for known fields from both formats
        rename_map = {
            'Significant Wave Height (m)': 'Hs[m]',
            'Peak Period (s)': 'Tp[s]',
            'Mean Period (s)': 'Tm[s]',
            'Peak Direction (deg)': 'Peak_dir[°]',
            'Mean Direction (deg)': 'Mean_dir[°]',
            'Peak Directional Spread (deg)': 'Peak_dir_spread[°]',
            'Mean Directional Spread (deg)':'Mean_dir_spread[°]',
            'significant_wave_height_spotter': 'Hs[m]',
            'wave_mean_period_spotter': 'Tm[s]',
            'wave_mean_direction_spotter': 'Mean_dir[°]',
            'wind_speed_spotter': 'Wind[m/s]',
            'wind_direction_spotter': 'WindDir[°]',
            'top_temperature_spotter': 'TempTop[°C]',
            'bottom_temperature_spotter': 'TempBottom[°C]'
        }

        # Apply renaming where applicable
        df = df.rename(columns=rename_map)

        # Detect all columns that contain "spotter" (renamed or not) for conversion
        spotter_cols = [col for col in df.columns if 'spotter' in col.lower() or 'spotter' in rename_map.get(col, '')]

        # Convert all spotter-related columns to float
        for col in spotter_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with NaNs in the core spotter wave variables, if they exist
        key_wave_vars = ['Hs[m]', 'Tp[s]', 'Dir[°]']
        vars_present = [v for v in key_wave_vars if v in df.columns]
        if vars_present:
            df = df.dropna(subset=vars_present, how='any')

        return df


    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Assigns burst IDs based on hourly bins.
        """
        df['burstId'] = pd.factorize(df.index.floor('H'))[0] + 1
        return df

    def _parse_dates_and_trim(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trims the DataFrame to the time range specified in sampling_data.
        """
        start = pd.to_datetime(self.sampling_data['start_time'])
        end = pd.to_datetime(self.sampling_data['end_time'])

        df_trimmed = df[start:end]

        if df_trimmed.empty:
            raise ValueError(
                f"No data found in the range {start} to {end}. "
                f"Available data is from {df.index.min()} to {df.index.max()}"
            )

        return df_trimmed