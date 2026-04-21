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
        )

        if not stationary:
            return self._parse_nonstat_points(raw, header_cols)

        # Stationary: Time is listed in the header but its field is blank in data rows
        stat_cols = [c for c in header_cols if c != "Time"]
        raw.columns = stat_cols
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

    def read_spatial_output(
        self,
        output_dir: Path,
        filename: str = "wave_field.mat",
        grid_info: dict = None,
    ) -> xr.Dataset:
        """Read ``wave_field.mat`` into an :class:`xarray.Dataset`.

        The ``.mat`` file is expected to contain 2-D arrays (ny+1 × nx+1) for
        variables ``Hsig``, ``TPsmoo``, ``Tm01``, and ``Dir``.

        Parameters
        ----------
        output_dir : Path
            Directory that contains the output file.
        filename : str
            Output file name (default ``"wave_field.mat"``).
        grid_info : dict, optional
            Grid metadata dictionary (same format as :class:`GridMaker`).
            When provided the Dataset is assigned proper lon/lat coordinates.
            Expected keys: ``lon_ll_corner``, ``lat_ll_corner``,
            ``x_extent``, ``y_extent``.

        Returns
        -------
        xr.Dataset
            Dataset with variables ``Hsig``, ``TPsmoo``, ``Tm01``, ``Dir``
            on dimensions ``(lat, lon)`` (or ``(row, col)`` when no grid
            info is supplied).
        """
        filepath = Path(output_dir) / filename
        mat = sio.loadmat(str(filepath))
        variables = {k: v for k, v in mat.items() if not k.startswith("_")}
        ny1, nx1 = next(iter(variables.values())).shape

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
            coords = {"lat": lats, "lon": lons}
            dims = ("lat", "lon")
        else:
            coords = {"row": np.arange(ny1), "col": np.arange(nx1)}
            dims = ("row", "col")

        data_vars = {
            name: xr.DataArray(arr.astype(float), dims=dims)
            for name, arr in variables.items()
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

    def _parse_nonstat_points(self, raw: pd.DataFrame, cols: list) -> pd.DataFrame:
        raw.columns = cols
        raw["Time"] = pd.to_datetime(
            raw["Time"].astype(str), format="%Y%m%d.%H%M%S", errors="coerce"
        )
        raw = raw.dropna(subset=["Time"])

        point_ids = list(range(1, self.n_points + 1))
        raw["point"] = (point_ids * (len(raw) // self.n_points + 1))[: len(raw)]

        raw = raw.set_index("Time")
        raw.index.name = "time"
        return raw
