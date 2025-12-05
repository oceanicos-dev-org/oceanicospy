from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd


@dataclass
class CleaningRules:
    """
    Container for simple quality-control/cleaning thresholds.
    Values are inclusive ranges; set to None to disable the bound.
    """
    # Temperature [°C]
    t_min: Optional[float] = -2.0
    t_max: Optional[float] = 45.0
    # Conductivity [µS/cm]
    c_min: Optional[float] = 0.0
    c_max: Optional[float] = 1_000_000.0  # broad range to include fresh/brackish/sea water (in uS/cm)


class HOBO:
    """
    Reader/cleaner for HOBO CSV exports with two formats:
    - TL: Temperature Logger
    - CL: Conductivity Logger (usually includes temperature too)

    This class:
    - Scans a directory for CSVs
    - Autodetects file format (by filename prefix 'TL'/'CL' and/or header contents)
    - Standardizes columns
    - Concatenates *per format* and returns one DataFrame for CL and one for TL
    - Sorts chronologically and optionally trims by start/end datetimes

    Standardized columns:
    - 'date'                       -> pandas datetime64[ns] (naive)
    - 'temperature[C]'             -> float (if present)
    - 'conductivity[uS/cm]'        -> float (if present)
    - 'seq'                        -> Int64 (if present)

    Parameters
    ----------
    directory_path : str
        Path to a directory containing HOBO CSV files.
    start_dt : datetime, optional
        Start datetime for trimming the merged dataset.
    end_dt : datetime, optional
        End datetime for trimming the merged dataset.
    sampling_data : dict, optional
        Backward-compatible container that may include 'start_time'/'end_time'
        as str or datetime. Ignored if explicit start_dt/end_dt are provided.
    rules : CleaningRules, optional
        Thresholds applied in `get_clean_records_split()`.
    encoding_main : str, optional
        Primary encoding used to read CSVs. Default 'utf-8-sig' handles BOM.
    encoding_fallback : str, optional
        Fallback encoding if the primary one fails. Default 'latin-1'.
    """

    def __init__(
        self,
        directory_path: str,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
        sampling_data: Optional[Dict] = None,
        rules: Optional[CleaningRules] = None,
        encoding_main: str = "utf-8-sig",
        encoding_fallback: str = "latin-1",
    ) -> None:
        self.directory_path = directory_path
        self.rules = rules or CleaningRules()
        self.encoding_main = encoding_main
        self.encoding_fallback = encoding_fallback

        # Backward compatibility with sampling_data, but explicit args win
        sampling_data = sampling_data or {}
        sd = sampling_data.get("start_time")
        ed = sampling_data.get("end_time")

        # Normalize to pandas Timestamp if provided; allow str or datetime
        self.start_dt = pd.to_datetime(start_dt if start_dt is not None else sd) if (start_dt is not None or sd is not None) else None
        self.end_dt   = pd.to_datetime(end_dt   if end_dt   is not None else ed) if (end_dt   is not None or ed is not None) else None

    # ------------------------ Public API ------------------------

    def get_raw_records_split(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Read and concatenate all CSVs, returning two DataFrames:
        one for CL files and one for TL files (both chronological).

        Returns
        -------
        (df_cl, df_tl) : Tuple[pandas.DataFrame, pandas.DataFrame]
            Each DataFrame contains standardized columns and is time-sorted.
        """
        files = self._get_csv_files()
        if not files:
            raise FileNotFoundError("No .csv files found in the specified directory.")

        frames: List[pd.DataFrame] = []
        for f in files:
            frames.append(self._read_and_standardize_single_file(f))

        df_all = pd.concat(frames, ignore_index=True)

        # Optional trimming by explicit start/end datetimes (or fallback)
        start, end = self._resolve_trim_range(df_all)
        if start is not None or end is not None:
            if start is None:
                start = df_all["date"].min()
            if end is None:
                end = df_all["date"].max()
            df_all = df_all[(df_all["date"] >= start) & (df_all["date"] <= end)]

        # Split by detected format
        df_cl = df_all[df_all["format"] == "CL"].drop(columns=["format"]).copy()
        df_tl = df_all[df_all["format"] == "TL"].drop(columns=["format"]).copy()

        # Sort chronologically and deduplicate by timestamp
        if not df_cl.empty:
            df_cl = df_cl.sort_values("date").drop_duplicates(subset=["date"], keep="first").reset_index(drop=True)
        if not df_tl.empty:
            df_tl = df_tl.sort_values("date").drop_duplicates(subset=["date"], keep="first").reset_index(drop=True)

        # Consistent column ordering
        df_cl = self._order_columns(df_cl)
        df_tl = self._order_columns(df_tl)

        return df_cl, df_tl

    def get_clean_records_split(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Return cleaned DataFrames for CL and TL:
        - Drop rows where all measured variables are NaN
        - Apply QC ranges for temperature and conductivity
        - Ensure numeric dtypes and consistent column ordering
        """
        df_cl, df_tl = self.get_raw_records_split()
        df_cl = self._apply_qc(df_cl)
        df_tl = self._apply_qc(df_tl)
        return df_cl, df_tl

    # --------------------- Internal helpers ---------------------

    def _get_csv_files(self) -> List[str]:
        """Return all CSV files in the target directory."""
        return sorted(glob.glob(os.path.join(self.directory_path, "*.csv")))

    def _read_and_standardize_single_file(self, path: str) -> pd.DataFrame:
        """
        Read a single HOBO CSV file, skip the first title row, detect columns and format,
        standardize names, and parse datetimes and numerics.
        """
        try:
            df = pd.read_csv(path, skiprows=1, encoding=self.encoding_main)
        except Exception:
            df = pd.read_csv(path, skiprows=1, encoding=self.encoding_fallback)

        fmt_fn = self._detect_format_from_filename(path)
        fmt_hd, dt_col, temp_col, cond_col, seq_col = self._detect_format_and_columns(df.columns.tolist())
        fmt = fmt_fn or fmt_hd  # prefer filename-based detection

        keep_cols = [dt_col]
        if seq_col:
            keep_cols = [seq_col] + keep_cols
        if temp_col:
            keep_cols.append(temp_col)
        if cond_col:
            keep_cols.append(cond_col)
        df = df[keep_cols].copy()

        rename_map = {dt_col: "date"}
        if seq_col:
            rename_map[seq_col] = "seq"
        if temp_col:
            rename_map[temp_col] = "temperature[C]"
        if cond_col:
            rename_map[cond_col] = "conductivity[uS/cm]"
        df = df.rename(columns=rename_map)

        # Spanish HOBOware datetime: 'MM/DD/YY hh:mm:ss AM/PM'
        df["date"] = pd.to_datetime(df["date"], format="%m/%d/%y %I:%M:%S %p", errors="coerce")

        for col in ("temperature[C]", "conductivity[uS/cm]"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "seq" in df.columns:
            df["seq"] = pd.to_numeric(df["seq"], errors="coerce").astype("Int64")

        df["format"] = fmt
        return df

    @staticmethod
    def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Return a view with standard column ordering."""
        if df.empty:
            return df
        ordered = ["date"]
        if "temperature[C]" in df.columns:
            ordered.append("temperature[C]")
        if "conductivity[uS/cm]" in df.columns:
            ordered.append("conductivity[uS/cm]")
        if "seq" in df.columns:
            ordered.append("seq")
        return df[ordered].copy()

    def _apply_qc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply simple QC ranges and drop rows without any measurements."""
        if df.empty:
            return df

        value_cols = [c for c in ["temperature[C]", "conductivity[uS/cm]"] if c in df.columns]
        if value_cols:
            df = df.dropna(subset=value_cols, how="all").copy()

        if "temperature[C]" in df.columns:
            if self.rules.t_min is not None:
                df.loc[df["temperature[C]"] < self.rules.t_min, "temperature[C]"] = pd.NA
            if self.rules.t_max is not None:
                df.loc[df["temperature[C]"] > self.rules.t_max, "temperature[C]"] = pd.NA

        if "conductivity[uS/cm]" in df.columns:
            if self.rules.c_min is not None:
                df.loc[df["conductivity[uS/cm]"] < self.rules.c_min, "conductivity[uS/cm]"] = pd.NA
            if self.rules.c_max is not None:
                df.loc[df["conductivity[uS/cm]"] > self.rules.c_max, "conductivity[uS/cm]"] = pd.NA

        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return self._order_columns(df).reset_index(drop=True)

    # --------------------- Trim helpers ---------------------

    def _resolve_trim_range(self, df_all: pd.DataFrame) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """
        Resolve trimming range using explicit start_dt/end_dt if provided,
        otherwise return (None, None) to keep full extent.
        """
        start = pd.to_datetime(self.start_dt) if self.start_dt is not None else None
        end = pd.to_datetime(self.end_dt) if self.end_dt is not None else None
        return start, end

    # --------------------- Detection helpers ---------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize header strings to help detection:
        - Remove stray bytes (Â, µ variants)
        - Keep ASCII subset
        - Collapse whitespace
        """
        if text is None:
            return text
        t = (
            text.replace("Â", "")
               .replace("µ", "u")
               .replace("Î¼", "u")
               .encode("latin-1", "ignore")
               .decode("latin-1")
        )
        t = t.encode("ascii", "ignore").decode("ascii")
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _detect_format_from_filename(self, path: str) -> Optional[str]:
        """
        Infer format from filename prefix if available:
        filenames like 'CL1-1_0524.csv' -> 'CL', 'TL1-2_0524.csv' -> 'TL'.
        """
        base = os.path.basename(path).upper()
        if base.startswith("CL"):
            return "CL"
        if base.startswith("TL"):
            return "TL"
        return None

    def _detect_format_and_columns(
        self, columns: List[str]
    ) -> tuple[str, str, Optional[str], Optional[str], Optional[str]]:
        """
        Detect file format (TL vs CL) and return the original column names for:
        - datetime, temperature, conductivity, sequence

        Returns
        -------
        (fmt, dt_col, temp_col, cond_col, seq_col)
        """
        norm = [self._normalize(c) for c in columns]

        # Date-time header usually contains 'Fecha Tiempo' or 'Date Time'
        dt_idx = None
        for i, c in enumerate(norm):
            if ("Fecha Tiempo" in c) or (c.lower().startswith("date")) or ("Tiempo" in c):
                dt_idx = i
                break
        if dt_idx is None:
            dt_idx = 1  # fallback to a common position
        dt_col = columns[dt_idx]

        # Sequence column commonly labeled 'N.' or similar
        seq_idx = next((i for i, c in enumerate(norm) if c.startswith("N")), None)
        seq_col = columns[seq_idx] if seq_idx is not None else None

        # Temperature column (TL and also present in CL)
        temp_idx = next((i for i, c in enumerate(norm) if ("Temp" in c and ("C" in c or "degC" in c))), None)
        temp_col = columns[temp_idx] if temp_idx is not None else None

        # Conductivity column (CL)
        cond_idx = next((i for i, c in enumerate(norm) if ("S/cm" in c and ("Rango" in c or "Conductivity" in c))), None)
        cond_col = columns[cond_idx] if cond_idx is not None else None

        fmt = "CL" if cond_col is not None else "TL"
        return fmt, dt_col, temp_col, cond_col, seq_col
