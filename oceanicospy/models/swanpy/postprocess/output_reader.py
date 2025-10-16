from typing import Dict, Tuple
from pathlib import Path
import pandas as pd


class SwanOutputReader:
    # Fixed schema for SalidasSWAN.out
    _COLS  = ['Time','Xp','Yp','Depth','X-Windv','Y-Windv','Hsig','TPsmoo','Tm01','Tm02','Dir']
    _DTYPE = {'Time': str, 'Xp': float, 'Yp': float, 'Depth': float,
              'X-Windv': float, 'Y-Windv': float, 'Hsig': float,
              'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float}

from typing import Dict, Tuple
from pathlib import Path
import pandas as pd


class SwanOutputReader:
    """
    Minimal reader for SWAN ASCII 'SalidasSWAN.out' with interleaved points.
    - Assumes fixed column layout as below.
    - Splits interleaved series by striding using `n_points`.
    - Crops by [start, end] and returns per-variable dicts and a common time index.
    """

    # Fixed schema for SalidasSWAN.out
    _COLS  = ['Time','Xp','Yp','Depth','X-Windv','Y-Windv','Hsig','TPsmoo','Tm01','Tm02','Dir']
    _DTYPE = {'Time': str, 'Xp': float, 'Yp': float, 'Depth': float,
              'X-Windv': float, 'Y-Windv': float, 'Hsig': float,
              'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float}

    def __init__(self,
                 hs_col: str = "Hsig",
                 tp_col: str = "TPsmoo",
                 dir_col: str = "Dir",
                 tm01_col: str = "Tm01",
                 tm02_col: str = "Tm02",
                 n_points: int = 2):
        """
        Parameters
        ----------
        hs_col : str
            Column name for significant wave height.
        tp_col : str
            Column name for peak period (TPsmoo).
        dir_col : str
            Column name for mean wave direction.
        tm01_col : str
            Column name for mean wave period Tm01.
        tm02_col : str
            Column name for mean wave period Tm02.
        n_points : int
            Number of interleaved points in the file.
        """
        self.hs_col = hs_col
        self.tp_col = tp_col
        self.dir_col = dir_col
        self.tm01_col = tm01_col
        self.tm02_col = tm02_col
        self.n_points = int(n_points)

    def _read_domain_df(self, file_path: Path) -> pd.DataFrame:
        """Read SWAN ASCII output and return a clean, time-indexed DataFrame."""
        df = pd.read_csv(
            file_path, skiprows=7, sep=r"\s+", index_col=0,
            names=self._COLS, dtype=self._DTYPE, engine="python"
        )
        # Parse index to datetime, drop invalid, ensure tz-naive, sort
        idx = pd.to_datetime(df.index, format='%Y%m%d.%H%M%S', errors='coerce')
        mask = ~idx.isna()
        df = df.loc[mask].copy()
        df.index = idx[mask].tz_localize(None)
        return df.sort_index()

    def _build_stride_dict(self, series: pd.Series) -> Dict[int, pd.Series]:
        """Split an interleaved series into n_points sub-series by striding."""
        return {i + 1: series.iloc[i::self.n_points] for i in range(self.n_points)}

    def load_domain(self,
                    domain_dir: Path,
                    start: pd.Timestamp,
                    end: pd.Timestamp
                    ) -> Tuple[Dict[str, Dict[int, pd.Series]], pd.DatetimeIndex]:
        """
        Load one domain, crop by time, and return per-variable dictionaries.

        Returns
        -------
        time_series_sims : dict
            {
              'hs':   {point: Series},
              'tp':   {point: Series},
              'dir':  {point: Series},
              'tm01': {point: Series},
              'tm02': {point: Series}
            }
        time_index : pd.DatetimeIndex
            Common time vector taken from the first available variable at point 1.
        """
        df = self._read_domain_df(domain_dir / "SalidasSWAN.out")
        df_crop = df.loc[start:end]

        out: Dict[str, Dict[int, pd.Series]] = {}

        if self.hs_col in df_crop:
            out["hs"] = self._build_stride_dict(df_crop[self.hs_col])
        if self.tp_col in df_crop:
            out["tp"] = self._build_stride_dict(df_crop[self.tp_col])
        if self.dir_col in df_crop:
            out["dir"] = self._build_stride_dict(df_crop[self.dir_col])
        if self.tm01_col in df_crop:
            out["tm01"] = self._build_stride_dict(df_crop[self.tm01_col])
        if self.tm02_col in df_crop:
            out["tm02"] = self._build_stride_dict(df_crop[self.tm02_col])

        # Choose a robust time vector (prefer hs, then tp, then tm02, then tm01, then dir)
        for key in ("hs", "tp", "tm02", "tm01", "dir"):
            if key in out and 1 in out[key]:
                time_index = out[key][1].index
                break
        else:
            raise ValueError("None of the requested columns were found in the cropped DataFrame.")

        return out, time_index