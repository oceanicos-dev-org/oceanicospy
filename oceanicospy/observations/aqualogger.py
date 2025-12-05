import pandas as pd
import glob
import os
import re

from .pressure_sensor_base import BaseLogger


class AQUAlogger(BaseLogger):
    """
    Sensor-specific reader for AQUAlogger CSV files.

    The class standardizes columns to:
    - 'date' (datetime index later)
    - 'pressure[bar]'
    - optional 'depth[m]'
    - optional 'UNITS' (for burst markers)
    """

    @property
    def first_record_time(self):
        return super().first_record_time

    @property
    def last_record_time(self):
        return super().last_record_time

    # ----------------------------- I/O helpers -----------------------------
    def _get_records_file(self):
        files = glob.glob(os.path.join(self.directory_path, "*.csv"))
        if not files:
            raise FileNotFoundError("No .csv file found in the specified directory.")
        # If there are multiple CSVs, take the first deterministically (sorted)
        return sorted(files)[0]

    def _load_raw_dataframe(self) -> pd.DataFrame:
        """
        Load raw CSV with a two-stage strategy:
        1) Try legacy 'AQ3_in_ALM' schema (header=21, fixed columns).
        2) Fallback: detect the 'HEADING' row (AQMayAgo2018-like) and parse from there,
        mapping to canonical columns: 'UNITS', 'date', 'Raw1', 'pressure[bar]'.
        """
        filepath = self._get_records_file()
        if self.sampling_data.get('temperature', False):
            columns = ['UNITS', 'date', 'Raw1', 'temperature', 'Raw2', 'pressure[bar]', 'Raw3', 'depth[m]', 'nan']
            drop_cols = ['Raw1', 'Raw2', 'Raw3', 'nan']
        else:
            columns = ['UNITS', 'date', 'Raw1', 'pressure[bar]', 'Raw2', 'depth[m]', 'nan']
            drop_cols = ['Raw1', 'nan']

        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if line.startswith("HEADING"):
                    line_header = lineno
                    break

        df = pd.read_csv(filepath, names=columns, header=line_header, encoding='latin-1') # will be 21 depending on the file format
        df = df.drop(columns=drop_cols)
        return df

        
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Make column names canonical without assuming that 'date' must be in columns
        (it may already be the DatetimeIndex after _parse_dates_and_trim).
        Canonical targets:
        - 'pressure[bar]'
        - optional 'depth[m]'
        - optional 'Raw1' (raw counts)
        - keep 'UNITS' if present (used later to assign bursts)
        """
        import re
        cols = list(df.columns)

        # 1) Pressure -> 'pressure[bar]'
        if 'pressure[bar]' not in df.columns:
            press_col = None
            # common: 'Pressure', 'Pressure       ', 'bar', 'Bar', etc.
            for c in cols:
                if re.search(r'press', c, re.IGNORECASE):
                    press_col = c
                    break
            if press_col is None:
                for c in cols:
                    # columns literally named 'bar' (with or without spaces)
                    if re.fullmatch(r'\s*bar\s*', c, re.IGNORECASE):
                        press_col = c
                        break
            if press_col is not None and press_col != 'pressure[bar]':
                df = df.rename(columns={press_col: 'pressure[bar]'})

        # 2) Depth -> 'depth[m]' (if present; if not, BaseLogger._compute_depth_from_pressure will create it)
        if 'depth[m]' not in df.columns:
            depth_candidates = ['Depth_[m]', 'DEPTH_[m]', 'Depth[m]', 'depth', 'DEPTH']
            depth_col = next((c for c in cols if c in depth_candidates), None)
            if depth_col is None:
                for c in cols:
                    if re.search(r'depth\s*\[?m\]?', c, re.IGNORECASE):
                        depth_col = c
                        break
            if depth_col is not None and depth_col != 'depth[m]':
                df = df.rename(columns={depth_col: 'depth[m]'})

        # 3) Raw counts -> 'Raw1'
        if 'Raw1' not in df.columns:
            for c in cols:
                if c.strip().lower() == 'raw':
                    df = df.rename(columns={c: 'Raw1'})
                    break


        if 'date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            for cand in ('date', 'Date', 'DATE', 'Time', 'time', 'DATETIME', 'Datetime', 'timestamp', 'Timestamp', 'Timecode'):
                if cand in cols:
                    if cand != 'date':
                        df = df.rename(columns={cand: 'date'})
                    break
            if 'date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError("No recognizable datetime column found.")

        return df



    # ----------------------------- burst assignment -----------------------------
    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        If 'UNITS' exists, use 'BURSTSTART' markers.
        Otherwise, create fixed-length bursts from sampling_data (sampling_freq * burst_length_s).
        """
        if 'UNITS' in df.columns:
            df['burstId'] = (df['UNITS'] == 'BURSTSTART').cumsum()
            return df.drop(columns=['UNITS'])

        # No UNITS column: use fixed-length bursting
        fs = float(self.sampling_data.get('sampling_freq', 0.0))
        bl = int(self.sampling_data.get('burst_length_s', 0))
        if fs <= 0.0 or bl <= 0:
            raise ValueError("Missing 'sampling_freq' or 'burst_length_s' in sampling_data for fixed-length bursts.")

        samples_per_burst = int(round(fs * bl))
        if samples_per_burst <= 1:
            raise ValueError("Computed samples_per_burst <= 1. Check 'sampling_freq' and 'burst_length_s'.")

        n = len(df)
        burst_ids = (pd.Series(range(n), index=df.index) // samples_per_burst) + 1
        df['burstId'] = burst_ids.to_numpy()
        return df

