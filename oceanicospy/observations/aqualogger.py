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
        temperature_mode = bool(self.sampling_data.get('temperature', False))

        # --- Attempt 1: legacy header-offset schema (AQ3_in_ALM-like) ---
        try:
            if temperature_mode:
                columns = ['UNITS', 'date', 'Raw1', 'temperature', 'Raw2', 'pressure[bar]', 'Raw3', 'depth[m]', 'nan']
                drop_cols = ['Raw1', 'Raw2', 'Raw3', 'nan']
            else:
                columns = ['UNITS', 'date', 'Raw1', 'pressure[bar]', 'Raw2', 'depth[m]', 'nan']
                drop_cols = ['Raw1', 'Raw2', 'nan']

            df = pd.read_csv(
                filepath,
                names=columns,
                header=21,              # legacy offset (line 22 is header)
                encoding='latin-1',
                engine='python'
            )
            if 'date' not in df.columns or 'pressure[bar]' not in df.columns:
                raise ValueError("Legacy schema read but key columns missing -> fallback.")
            df = df.drop(columns=[c for c in drop_cols if c in df.columns])
            return self._standardize_columns(df)
        except Exception:
            pass  # try fallback

        # --- Attempt 2: AQMayAgo2018-like (uses HEADING/UNITS/BURSTSTART/DATA) ---
        # Find the line index where 'HEADING' appears
        with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
            lines = f.read().splitlines()
        heading_idx = None
        for i, line in enumerate(lines):
            if line.startswith('HEADING'):
                heading_idx = i
                break
        if heading_idx is None:
            # Flexible generic read (delimiter sniffing) as last resort
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin-1')
            except pd.errors.ParserError:
                try:
                    df = pd.read_csv(filepath, sep=';', engine='python', encoding='latin-1')
                except Exception:
                    df = pd.read_csv(filepath, sep=',', engine='python', encoding='latin-1', on_bad_lines='skip')
            return self._standardize_columns(df)

        # Read from HEADING row; keep first 4 columns (UNITS/date/raw/pressure)
        df = pd.read_csv(
            filepath,
            header=heading_idx,
            engine='python',
            encoding='latin-1',
            usecols=[0, 1, 2, 3]
        )
        # Normalize column names and map to canonical ones
        df.columns = [c.strip() for c in df.columns]
        # Example at header: ['HEADING','Timecode','Pressure','Unnamed: 3']
        df = df.rename(columns={
            df.columns[0]: 'UNITS',
            df.columns[1]: 'date',
            df.columns[2]: 'Raw1',             # integer raw counts
            df.columns[3]: 'pressure[bar]'     # pressure in bar
        })
        # Keep only BURSTSTART/DATA rows
        df = df[df['UNITS'].isin(['BURSTSTART', 'DATA'])].copy()

        return self._standardize_columns(df)


        
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

