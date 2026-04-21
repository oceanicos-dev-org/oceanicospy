import re
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
import xarray as xr
from wavespectra import read_swan


class SwanOutputReader:
    """
    Reader for the three SWAN output types produced by oceanicospy runs:

    - ``PointSWAN.out``  – tabular wave parameters at output points
    - ``SpecSWAN.out``   – 2-D spectral density at output points (via wavespectra)
    - ``wave_field.mat`` – spatial wave-field snapshots (MATLAB binary)


    Parameters
    ----------
    n_points : int
        Number of output points written to ``PointSWAN.out``.
        Used only for non-stationary files where rows are interleaved.
    
    
    """

    def __init__(self, n_points: int = 1):

        self.n_points = int(n_points)

    def read_point_output(
        self,
        output_dir: Path | str,
        filename: str = "PointSWAN.out",
    ) -> pd.DataFrame:
        """Read ``PointSWAN.out`` into a DataFrame.

        For **stationary** runs the returned DataFrame has one row per output
        point (indexed 1 … n).  For **non-stationary** runs it has a
        ``DatetimeIndex`` and an additional ``point`` column (1-indexed) that
        identifies the interleaved site.

        Parameters
        ----------
        output_dir : Path | str
            Directory that contains the output file.
        filename : str
            Output file name (default ``"PointSWAN.out"``).

        Returns
        -------
        pd.DataFrame
        """

        filepath = Path(output_dir) / filename
        header_cols = self._read_header_cols(filepath)
        stationary = self._time_field_is_blank(filepath)

        raw = pd.read_csv(
            filepath,
            comment="%",
            sep=r"\s+",
            header=None,
            engine="python",
            keep_default_na=False,
            dtype=str,
        )

        if not stationary:
            return self._parse_nonstat_points(raw, header_cols)

        # Stationary: Time is listed in the header but its field is blank in data rows
        stat_cols = [c for c in header_cols if c != "Time"]            
        raw.columns = stat_cols

        for col in stat_cols:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")

        raw.index = pd.RangeIndex(1, len(raw) + 1)
        raw.index.name = "point"
        return raw

    def read_spectral_output(
        self,
        output_dir: Path,
        filename: str = "SpecSWAN.out",
        as_site: bool = True,
    ) -> xr.Dataset:
        """Read ``SpecSWAN.out`` using :func:`wavespectra.read_swan`.

        Parameters
        ----------
        output_dir : Path
            Directory that contains the output file.
        filename : str
            Output file name (default ``"SpecSWAN.out"``).
        as_site : bool
            Passed to ``read_swan``.  When ``True`` locations are stored on a
            1-D ``site`` dimension instead of a spatial grid.

        Returns
        -------
        xr.Dataset
            ``SpecDataset`` with ``efth(time, site, freq, dir)`` and
            ``lat``/``lon`` coordinates per site.
        """
        filepath = Path(output_dir) / filename
        return read_swan(str(filepath), as_site=as_site)

    # Matches keys of the form  <VariableName>_<6–14 digits>
    # e.g. Hsig_20230507, TPsmoo_202305071200, Dir_20230507120000
    _SPATIAL_DATE_RE = re.compile(r"^(.+)_(\d{8})_(\d{6})$")

    def read_spatial_output(
        self,
        output_dir: Path,
        filename: str = "wave_field.mat",
        grid_info: dict = None,
    ) -> xr.Dataset:
        """Read ``wave_field.mat`` into an :class:`xarray.Dataset`.

        SWAN writes one 2-D array (``ny × nx``) per variable per timestep.
        Time-varying snapshots are identified by a date suffix in the key name
        (e.g. ``Hsig_20230507``, ``Hsig_202305071200``).  Snapshots for the
        same base variable are stacked in chronological order along a leading
        ``time`` dimension.  Keys without a date suffix are treated as
        stationary.

        Parameters
        ----------
        output_dir : Path
            Directory that contains the output file.
        filename : str
            Output file name (default ``"wave_field.mat"``).
        grid_info : dict, optional
            Grid metadata dictionary (same format as :class:`GridMaker`).
            When provided the Dataset gets proper lon/lat coordinates.
            Expected keys: ``lon_ll_corner``, ``lat_ll_corner``,
            ``x_extent``, ``y_extent``.

        Returns
        -------
        xr.Dataset
            Variables on ``(lat, lon)`` for stationary output, or
            ``(time, lat, lon)`` for non-stationary output
            (``row``/``col`` replace ``lat``/``lon`` when no ``grid_info``
            is supplied).
        """
        filepath = Path(output_dir) / filename
        mat = sio.loadmat(str(filepath))

        # Only 2-D arrays are spatial snapshots; skip scalars and metadata
        flat_vars = {
            k: v for k, v in mat.items()
            if not k.startswith("_") and isinstance(v, np.ndarray) and v.ndim == 2
        }
        if not flat_vars:
            raise ValueError(f"No 2-D arrays found in {filepath}.")

        # Separate time-stamped keys (e.g. Hsig_20230507) from static ones
        time_keyed: dict[str, dict[str, np.ndarray]] = {}
        static_vars: dict[str, np.ndarray] = {}

        for key, arr in flat_vars.items():
            m = self._SPATIAL_DATE_RE.match(key)
            if m:
                base, date_str = m.group(1), m.group(2) + m.group(3)
                time_keyed.setdefault(base, {})[date_str] = arr
            else:
                static_vars[key] = arr

        is_nonstationary = bool(time_keyed)

        ny1, nx1 = next(iter(flat_vars.values())).shape

        if grid_info is not None:
            lons = np.linspace(
                grid_info["lon_ll_corner"],
                grid_info["lon_ll_corner"] + grid_info["x_extent"],
                nx1,
            )
            lats = np.linspace(
                grid_info["lat_ll_corner"],
                grid_info["lat_ll_corner"] + grid_info["y_extent"],
                ny1,
            )
            spatial_coords = {"lat": lats, "lon": lons}
            spatial_dims = ("lat", "lon")
        else:
            spatial_coords = {"row": np.arange(ny1), "col": np.arange(nx1)}
            spatial_dims = ("row", "col")

        if not is_nonstationary:
            data_vars = {
                name: xr.DataArray(arr.astype(float), dims=spatial_dims)
                for name, arr in static_vars.items()
            }
            return xr.Dataset(data_vars, coords=spatial_coords)

        # Non-stationary: stack snapshots in chronological order
        date_strings = sorted(next(iter(time_keyed.values())).keys())
        time_coords = self._parse_spatial_date_strings(date_strings)
        dims = ("time",) + spatial_dims
        coords = {"time": time_coords, **spatial_coords}

        data_vars = {
            base: xr.DataArray(
                np.stack([snapshots[d] for d in date_strings], axis=0).astype(float),
                dims=dims,
            )
            for base, snapshots in time_keyed.items()
        }
        return xr.Dataset(data_vars, coords=coords)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_header_cols(self, filepath: Path) -> list:
        """Return column names from the header comment block of a SWAN table file.

        The column-names line is identified as the comment line immediately
        followed by the units line (the one that contains ``[``).
        """
        with open(filepath) as fh:
            comment_lines = []
            for line in fh:
                if not line.startswith("%"):
                    break
                comment_lines.append(line.lstrip("%").strip())

        for current, nxt in zip(comment_lines, comment_lines[1:]):
            tokens = current.split()
            if tokens and "[" not in current and "[" in nxt:
                return tokens
        return []

    def _time_field_is_blank(self, filepath: Path) -> bool:
        """Return True if the Time field in the first data row is blank (stationary run).

        In a stationary SWAN table the Time column is declared in the header
        but the corresponding field in each data row is left empty (pure
        leading whitespace), so the line starts with a space character.
        """
        with open(filepath) as fh:
            for line in fh:
                if not line.startswith("%"):
                    return line[0] == " "
        return False

    def _parse_spatial_date_strings(self, date_strings: list) -> pd.DatetimeIndex:
        """Parse SWAN date-suffix strings into a :class:`pandas.DatetimeIndex`.

        Tries common SWAN date formats from most to least specific and returns
        the first one that parses without error.
        """
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d%H", "%Y%m%d", "%y%m%d"):
            try:
                return pd.to_datetime(date_strings, format=fmt)
            except ValueError:
                continue
        raise ValueError(
            f"Could not parse date strings from .mat keys: {date_strings[:3]} …"
        )

    def _parse_nonstat_points(self, raw: pd.DataFrame, cols: list) -> pd.DataFrame:
        raw.columns = cols

        for col in cols:
            if col != "Time":
                raw[col] = pd.to_numeric(raw[col], errors="coerce")

        raw["Time"] = pd.to_datetime(
            raw["Time"].astype(str), format="%Y%m%d.%H%M%S", errors="coerce"
        )
        raw = raw.dropna(subset=["Time"])

        point_ids = list(range(1, self.n_points + 1))
        raw["point"] = (point_ids * (len(raw) // self.n_points + 1))[: len(raw)]

        raw = raw.set_index("Time")
        raw.index.name = "time"

        raw.set_index("point", append=True, inplace=True)

        return raw
