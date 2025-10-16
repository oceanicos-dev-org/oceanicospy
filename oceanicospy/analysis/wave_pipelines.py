# wave_params_pipeline.py
# Minimal OOP wrapper that *uses* your existing classes:
# - oceanicospy.observations.aqualogger.AQUAlogger
# - oceanicospy.analysis.spectral.WaveSpectralAnalyzer
# It reads raw AQUAlogger CSV for a user-given time window, computes Hs/Tp via
# 'welch' (smoothed) or 'fft', and writes a CSV indexed by 'date' with columns
# 'Hs[m]' and 'Tp[s]'.

from pathlib import Path
from datetime import datetime
import warnings
import numpy as np
import pandas as pd

# Prefer package imports; fall back to relative imports if running inside the package tree
try:
    from oceanicospy.observations.aqualogger import AQUAlogger
    from oceanicospy.analysis.spectral import WaveSpectralAnalyzer
except Exception:
    from ..observations.aqualogger import AQUAlogger
    from .spectral import WaveSpectralAnalyzer


class WaveParamsPipeline:
    """Compact pipeline: AQUAlogger -> WaveSpectralAnalyzer -> Hs/Tp CSV (for a required time window)."""

    def __init__(
        self,
        default_fs: float = 1.0,
        default_window_type: str = "hamming",
        default_window_length: int = 1024,
        default_overlap: int | None = 512,
        default_smoothing_bins: int = 6,
    ):
        """
        Notes
        -----
        - default_fs is used only if sampling frequency cannot be inferred from timestamps.
        - Welch parameters are used when method='welch'.
        """
        self.default_fs = float(default_fs)
        self.default_window_type = default_window_type
        self.default_window_length = int(default_window_length)
        self.default_overlap = None if default_overlap is None else int(default_overlap)
        self.default_smoothing_bins = int(default_smoothing_bins)

    @staticmethod
    def _resolve_input_dir(raw_csv_path: str | Path) -> Path:
        """AQUAlogger expects a directory; accept a CSV path or a directory."""
        p = Path(raw_csv_path)
        return p if p.is_dir() else p.parent

    @staticmethod
    def _infer_fs(idx: pd.DatetimeIndex) -> float:
        """Infer sampling frequency [Hz] from median Δt."""
        if len(idx) < 3:
            return np.nan
        dts = np.diff(idx.view("i8")) / 1e9  # seconds
        dts = dts[dts > 0]
        if dts.size == 0:
            return np.nan
        dt_med = float(np.median(dts))
        return 1.0 / dt_med if dt_med > 0 else np.nan

    @staticmethod
    def _estimate_burst_length_s(clean_df: pd.DataFrame, fs: float) -> int:
        """Estimate burst length (s) from median burst size and fs."""
        if "burstId" not in clean_df.columns or fs <= 0:
            return 0
        sizes = clean_df.groupby("burstId").size().to_numpy()
        if sizes.size == 0:
            return 0
        samples = int(np.median(sizes))
        return max(0, int(round(samples / fs)))

    @staticmethod
    def _mk_sampling(start_dt: datetime, end_dt: datetime, fs: float, burst_len_s: int) -> dict:
        """Build sampling_data dict required by WaveSpectralAnalyzer/AQUAlogger."""
        return dict(
            sampling_freq=float(fs),
            anchoring_depth=1.0,   # placeholders (kept for API compatibility)
            sensor_height=0.1,
            burst_length_s=int(burst_len_s),
            start_time=start_dt,
            end_time=end_dt,
        )

    def run(
        self,
        raw_csv_path: str | Path,
        method: str,                       
        output_csv_path: str | Path,
        start_dt: datetime,
        end_dt: datetime,
        burst_len_s: int,                  # NEW: user must provide
        window_type: str | None = None,
        window_length: int | None = None,
        overlap: int | None = None,
        smoothing_bins: int | None = None
    ) -> pd.DataFrame:
        """
        Compute Hs/Tp in the given time window and export a minimal CSV.

        Returns
        -------
        DataFrame with index 'date' and columns ['Hs[m]', 'Tp[s]'].
        """
        if start_dt > end_dt:
            raise ValueError("start_dt must be <= end_dt")

        folder = self._resolve_input_dir(raw_csv_path)

        # Build sampling_data like in your reference scripts
        sampling = dict(
            anchoring_depth=1,
            sensor_height=0.2,
            sampling_freq=self.default_fs,
            burst_length_s=burst_len_s,
            temperature=False,
            start_time=start_dt,
            end_time=end_dt
        )

        aq = AQUAlogger(str(folder), sampling)
        clean_df = aq.get_clean_records(detrended=True)
        if clean_df.empty:
            raise RuntimeError("No data available after cleaning (check time window).")

        analyzer = WaveSpectralAnalyzer(measurement_signal=clean_df, sampling_data=sampling)

        use_method = method.strip().lower()
        if use_method not in ("welch", "fft"):
            raise ValueError("Unsupported method. Use 'welch' or 'fft'.")

        wtype = self.default_window_type if window_type is None else window_type
        wlen = self.default_window_length if window_length is None else int(window_length)
        ovlp = self.default_overlap if overlap is None else (None if overlap is None else int(overlap))
        sbins = self.default_smoothing_bins if smoothing_bins is None else int(smoothing_bins)

        wave_spectra, wave_params = analyzer.get_spectra_and_params_for_bursts(
            method=use_method,
            window_type=wtype,
            window_length=wlen,
            overlap=ovlp,
            smoothing_bins=sbins,
        )

        if wave_params is None or wave_params.empty:
            raise RuntimeError("Wave parameter table is empty.")

        df_out = wave_params.loc[:, ["Hm0", "Tp"]].copy()
        df_out.columns = ["Hs[m]", "Tp[s]"]
        df_out.index.name = "date"
        df_out = df_out.sort_index()

        out_path = Path(output_csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_path, float_format="%.6f")
        return df_out

