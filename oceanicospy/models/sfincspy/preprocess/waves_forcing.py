import os
from typing import Optional

import numpy as np
import pandas as pd
import xarray as xr
from hydromt_sfincs import SfincsModel, utils


class WavesForcing:
    """
    Wave forcing at the water-level boundary (``bzifile``) for SFINCS, from
    1D XBeach output.

    Turns the free-surface elevation computed by XBeach at a profile point
    into the ``bzi`` signal SFINCS expects: a water-level oscillation
    **centred on zero**, added to the slow level of ``bzsfile``.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.

    Notes
    -----
    - The XBeach wave setup is **not** transferred to ``bzsfile``. Doing so
      (adding the XBeach mean level to the tide, with an incoming/outgoing
      split and a site-calibrated setup correction) needs a higher-fidelity
      reference or independent level/run-up data to calibrate it.
    - The ``bzi`` file written here has a single column with its own times.
      SFINCS reads ``bzifile`` with exactly as many rows as ``bzsfile``,
      ignores its times and expects one column per boundary point. It is
      therefore valid only with a single water-level boundary point and the
      same times as ``bzsfile``; otherwise SFINCS reads it wrongly without
      an error.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    def from_xbeach(
        self,
        nc_path: str,
        point_index: int = 0,
        nx_index: Optional[int] = None,
        out_filename: str = "sfincs.bzi",
    ) -> str:
        """
        Write the wave forcing from an XBeach NetCDF output.

        Parameters
        ----------
        nc_path : str
            XBeach NetCDF output (1D run).
        point_index : int, optional
            Index into ``pointx``, the XBeach "point" outputs (often a single
            run-up gauge). It is used to find the nearest position on the
            global profile (``globalx``), where ``zs`` is read. Ignored if
            ``nx_index`` is given.
        nx_index : int, optional
            Direct index on the global profile (``globalx`` / ``nx``), to
            force SFINCS from a chosen profile position (e.g. where the bed
            crosses a given depth) regardless of the XBeach point outputs.
            Takes precedence over ``point_index``.
        out_filename : str, optional
            Output file name (default ``"sfincs.bzi"``).

        Returns
        -------
        str
            Path of the written file.

        Raises
        ------
        KeyError
            If ``zs`` is not in the NetCDF.
        RuntimeError
            If no values are left within the model period.

        Notes
        -----
        Steps:

        1. Read the free-surface elevation ``zs`` (not the wave height
           ``H``: ``bzi`` is a water-level oscillation and must oscillate
           around zero).
        2. Take the selected profile point.
        3. Clip to the model period ``[tstart, tstop]``. The XBeach time is
           taken as seconds since ``tref``, so the XBeach run must start at
           the SFINCS reference time.
        4. Subtract the mean of ``zs`` over that clipped window, so the
           signal is centred on zero.
        5. Write ``time [s since tref]  bzi [m]`` in the ASCII format SFINCS
           reads, and register ``bzifile``.

        Examples
        --------
        >>> waves = WavesForcing(model)
        >>> waves.from_xbeach("xboutput.nc", nx_index=120)
        """
        tref = utils.parse_datetime(self.model.config["tref"])
        tstart = utils.parse_datetime(self.model.config["tstart"])
        tstop = utils.parse_datetime(self.model.config["tstop"])

        ds = xr.open_dataset(nc_path)
        if "zs" not in ds:
            raise KeyError("Variable 'zs' not found in the NetCDF.")

        zs = ds["zs"]                        # (globaltime, ny, nx)
        time = ds["globaltime"].values       # seconds since the start of the run
        X = ds["globalx"].values[0, :]

        if nx_index is not None:
            ix = nx_index
        else:
            xp = ds["pointx"].values[point_index]
            ix = np.argmin(np.abs(X - xp))
        zs_p = zs.isel(nx=ix, ny=0).values

        time_dt = pd.to_datetime(time, unit="s", origin=tref)
        df = pd.DataFrame({"zs": zs_p}, index=time_dt).loc[tstart:tstop]
        if df.empty:
            raise RuntimeError("The XBeach water-level series is empty within the model period.")

        df["bzi"] = df["zs"] - df["zs"].mean()

        time_sec = (df.index - tref).total_seconds().astype(int)
        df_out = pd.DataFrame({"time": time_sec, "bzi": df["bzi"].values})

        out_path = os.path.join(self.model.root, out_filename)
        df_out.to_csv(out_path, sep=" ", index=False, header=False, float_format="%.6f")

        self.model.set_config("bzifile", out_filename)
        return out_path

    def from_dataframe(
        self,
        df: pd.DataFrame,
        column_name: str,
        out_filename: str = "sfincs.bzi",
    ) -> str:
        """
        Write the wave forcing from a prepared series.

        Unlike :meth:`from_xbeach`, the signal is **not** re-centred: the
        column must already be an oscillation centred on zero (e.g. the
        output of :meth:`from_xbeach` scaled by a constant factor, which
        keeps it centred).

        Parameters
        ----------
        df : pandas.DataFrame
            Datetime index in local time (the model times) and a water-level
            oscillation column (m), centred on zero.
        column_name : str
            Oscillation column.
        out_filename : str, optional
            Output file name (default ``"sfincs.bzi"``).

        Returns
        -------
        str
            Path of the written file.

        Raises
        ------
        ValueError
            If ``column_name`` is not in ``df``.
        RuntimeError
            If no values are left within the model period.
        """
        tref = utils.parse_datetime(self.model.config["tref"])
        tstart = utils.parse_datetime(self.model.config["tstart"])
        tstop = utils.parse_datetime(self.model.config["tstop"])

        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in df.")

        serie = df[[column_name]].copy().loc[tstart:tstop]
        if serie.empty:
            raise RuntimeError("The wave series is empty within the model period.")

        time_sec = (serie.index - tref).total_seconds().astype(int)
        df_out = pd.DataFrame({"time": time_sec, "bzi": serie[column_name].values})

        out_path = os.path.join(self.model.root, out_filename)
        df_out.to_csv(out_path, sep=" ", index=False, header=False, float_format="%.6f")

        self.model.set_config("bzifile", out_filename)
        return out_path
