from abc import ABC, abstractmethod
import pandas as pd
from scipy.signal import detrend
from oceanicospy.utils import constants


class BaseLogger(ABC):
    """
    Initializes the BaseLogger class with the given directory path and sampling data.

    sampling_data must include:
      - 'start_time' (datetime-like)
      - 'end_time'   (datetime-like)
      - 'sampling_freq' (Hz) and 'burst_length_s' (s) are recommended for bursting when markers are absent.
    """

    def __init__(self, directory_path: str, sampling_data: dict):
        self.directory_path = directory_path
        self.sampling_data = sampling_data

    # ----------------------------- basic metadata -----------------------------
    @property
    def first_record_time(self) -> pd.Timestamp:
        """Timestamp of the first available record (raw dataframe)."""
        df = self._load_raw_dataframe()
        col = "date" if "date" in df.columns else ("Time" if "Time" in df.columns else None)
        if col is None:
            # try additional candidates
            for c in ("DATETIME", "Datetime", "timestamp", "Timestamp"):
                if c in df.columns:
                    col = c
                    break
        if col is None:
            raise ValueError("Cannot infer time column for first_record_time.")
        return pd.to_datetime(df[col], errors="coerce").iloc[0]

    @property
    def last_record_time(self) -> pd.Timestamp:
        """Timestamp of the last available record (raw dataframe)."""
        df = self._load_raw_dataframe()
        col = "date" if "date" in df.columns else ("Time" if "Time" in df.columns else None)
        if col is None:
            for c in ("DATETIME", "Datetime", "timestamp", "Timestamp"):
                if c in df.columns:
                    col = c
                    break
        if col is None:
            raise ValueError("Cannot infer time column for last_record_time.")
        return pd.to_datetime(df[col], errors="coerce").iloc[-1]

    # ----------------------------- public API -----------------------------
    def get_raw_records(self) -> pd.DataFrame:
        """Read raw records, parse dates, trim to time window, and standardize columns."""
        df = self._load_raw_dataframe()
        df = self._parse_dates_and_trim(df)
        df = self._standardize_columns(df)
        return df

    def get_clean_records(self, detrended: bool = True) -> pd.DataFrame:
        """
        Processes the raw data by bursting and building 'eta[m]' as a detrended elevation per burst.
        """
        df = self.get_raw_records()
        df = self._compute_depth_from_pressure(df)
        df = self._assign_burst_id(df)

        # Build eta = depth - mean(depth per burst), then optional linear detrend
        df["eta[m]"] = df.groupby("burstId")["depth[m]"].transform(lambda x: x - x.mean())
        if detrended:
            df["eta[m]"] = df.groupby("burstId")["eta[m]"].transform(lambda x: detrend(x.values, type="linear"))
        return df

    # ----------------------------- internal helpers -----------------------------
    def _parse_dates_and_trim(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize a time column to 'date', set it as index, sort, and trim to [start_time, end_time].
        Uses robust parsing (dayfirst) and boolean masking to avoid KeyError on unsorted indexes.
        """
        # 1) Normalize a time column to 'date'
        if 'date' in df.columns:
            pass
        elif 'Time' in df.columns:
            df = df.rename(columns={'Time': 'date'})
        else:
            for c in ('DATETIME', 'Datetime', 'timestamp', 'Timestamp', 'Timecode'):
                if c in df.columns:
                    df = df.rename(columns={c: 'date'})
                    break
            if 'date' not in df.columns:
                raise ValueError("No recognizable datetime column found.")

        # 2) Optional: normalize Spanish AM/PM markers to standard AM/PM before parsing
        if df['date'].dtype == object:
            # Replace common Spanish markers like 'a.m.'/'p.m.' with 'AM'/'PM'
            df['date'] = (
                df['date']
                .astype(str)
                .str.replace(r'\ba\.m\.\b', 'AM', regex=True)
                .str.replace(r'\bp\.m\.\b', 'PM', regex=True)
            )

        # 3) Parse to datetime (dayfirst for formats like 10/05/2018)
        df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True)

        # 4) Drop rows that failed to parse and sort by time
        df = df.dropna(subset=['date']).sort_values('date').set_index('date')

        # 5) Required time window (robust boolean mask instead of label slice)
        try:
            start = pd.to_datetime(self.sampling_data['start_time'])
            end   = pd.to_datetime(self.sampling_data['end_time'])
        except KeyError:
            raise KeyError("Missing 'start_time' or 'end_time' in sampling_data.")
        except Exception as e:
            raise ValueError(f"Invalid time format in sampling_data: {e}")

        mask = (df.index >= start) & (df.index <= end)
        return df.loc[mask]



    def _compute_depth_from_pressure(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'pressure[bar]' not in df.columns:
            raise ValueError("pressure[bar] column is required to compute depth.")
        df['pressure[bar]'] = pd.to_numeric(df['pressure[bar]'], errors='coerce')
        depth_aux = ((df['pressure[bar]'] - constants.ATM_PRESSURE_BAR) * 1e5) / (
            constants.WATER_DENSITY * constants.GRAVITY
        )
        if 'depth[m]' not in df.columns:
            df['depth[m]'] = depth_aux
            return df
        try:
            max_diff = (depth_aux - df['depth[m]']).abs().max()
            if pd.notna(max_diff) and max_diff <= 0.10:
                return df
            else:
                df['depth[m]'] = depth_aux
                return df
        except Exception:
            df['depth[m]'] = depth_aux
            return df

        if (df['depth_aux[m]'] - df['depth[m]']).abs().max() <= 0.1:
            df = df.drop(columns=['depth_aux[m]'])
        return df 


    # ----------------------------- subclass contract -----------------------------
    @abstractmethod
    def _get_records_file(self) -> pd.DataFrame:
        """Return the first records file found in the directory. Raise if none are found."""
        pass

    @abstractmethod
    def _load_raw_dataframe(self) -> pd.DataFrame:
        """Implement reading/parsing for the concrete sensor format."""
        pass

    @abstractmethod
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize/rename raw columns to a canonical set."""
        pass

    @abstractmethod
    def _assign_burst_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attach a 'burstId' column to the dataframe."""
