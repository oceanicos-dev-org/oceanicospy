import shutil
from pathlib import Path
from typing import Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
import shapely

from hydromt_sfincs import SfincsModel

__all__ = ["Precipitation"]

_CONFIG_KEYS = ("precipfile", "prcfile", "netamprfile", "amprfile")
_FORCING_KEYS = ("precip", "precip_2d")


class Precipitation:
    """
    Precipitation forcing for SFINCS models.

    SFINCS accepts rainfall as a spatially uniform series (``precipfile``),
    a gridded field (``netamprfile``), or inside a tropical-cyclone
    spiderweb (``spwfile`` / ``netspwfile``). This class builds each of
    them; setting a uniform or gridded forcing removes the other one.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT, with grid and model
        times (``tref``, ``tstart``, ``tstop``) already set.

    Notes
    -----
    - Rates are in mm/h. SFINCS interpolates the uniform series linearly in
      time; gridded fields are held constant over each interval unless
      ``time_interpolation="linear"`` (``amprblock`` in ``sfincs.inp``).
    - Rainfall from stations is not converted here: aggregate or
      interpolate the station records with the method of choice and pass
      the result to :meth:`uniform`, :meth:`from_zones` or :meth:`from_grid`.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    # --------------------------------------------------
    # Uniform
    # --------------------------------------------------
    def uniform(self, rate: Union[float, pd.Series]) -> None:
        """
        Set a spatially uniform rainfall rate (``precipfile``).

        Parameters
        ----------
        rate : float or pandas.Series
            Constant rate, or a series with a datetime index, in mm/h. The
            series is clipped to the model period.

        Raises
        ------
        ValueError
            If the series has no values within the model period.

        Examples
        --------
        >>> precip = Precipitation(model)
        >>> precip.uniform(rain_series)        # mm/h, datetime index
        """
        self._clear()
        if isinstance(rate, (int, float)):
            self.model.setup_precip_forcing(magnitude=float(rate))
            return
        tstart, tstop = self.model.get_model_time()
        series = rate.sort_index().loc[tstart:tstop].astype(float).dropna()
        if series.empty:
            raise ValueError("The rainfall series has no values within the model period.")
        series.name, series.index.name = "precip", "time"
        self.model.set_forcing(series.to_xarray(), name="precip")

    # --------------------------------------------------
    # Gridded
    # --------------------------------------------------
    def from_zones(
        self,
        rates: Union[pd.Series, pd.DataFrame],
        zones: Union[str, Path, gpd.GeoDataFrame],
        zone_col: Optional[str] = None,
        resolution: Optional[float] = None,
        time_interpolation: str = "block",
    ) -> xr.DataArray:
        """
        Set gridded rainfall that is uniform within each zone and zero outside.

        Typical uses: rainfall restricted to a catchment (one zone), or one
        series per zone of any partition the user defines (e.g. polygons
        drawn around rain gauges).

        Parameters
        ----------
        rates : pandas.Series or pandas.DataFrame
            Rates in mm/h with a datetime index. A Series applies to every
            zone; a DataFrame has one column per zone.
        zones : str, Path or GeoDataFrame
            Zone polygons. Where zones overlap, the later one wins.
        zone_col : str, optional
            Column of ``zones`` whose values match the DataFrame columns.
            Default is the ``zones`` index. Ignored for a Series.
        resolution : float, optional
            Cell size (m) of the rainfall grid. Default is a third of the
            model cell size, fine enough for every model cell to read
            exactly the value of its own zone.
        time_interpolation : {'block', 'linear'}, optional
            Hold each rate over its interval (default) or interpolate
            linearly in time.

        Returns
        -------
        xarray.DataArray
            The rainfall field (time, y, x) set in the model.

        Raises
        ------
        ValueError
            If the rates have no values in the model period, or a zone has
            no matching column.

        Notes
        -----
        A model cell belongs to the zone that contains its centre, the same
        rule SFINCS uses when it samples the rainfall grid at cell centres.
        Each point of the rainfall grid takes the value of the model cell it
        falls in, so a cell is never mixed with its neighbours.

        Examples
        --------
        >>> precip.from_zones(rain_series, "catchment.shp")
        >>> precip.from_zones(rain_by_zone, zones_gdf, zone_col="gauge")
        """
        tstart, tstop = self.model.get_model_time()
        gdf = zones if isinstance(zones, gpd.GeoDataFrame) else gpd.read_file(zones)
        gdf = gdf.to_crs(self.model.crs).reset_index(drop=zone_col is not None)
        df = rates.to_frame() if isinstance(rates, pd.Series) else rates
        df = df.sort_index().loc[tstart:tstop].astype(float).fillna(0.0)
        if df.empty:
            raise ValueError("The rainfall rates have no values within the model period.")

        if isinstance(rates, pd.Series):
            keys = [df.columns[0]] * len(gdf)
        else:
            keys = list(gdf[zone_col] if zone_col else gdf.index)
            missing = [k for k in keys if k not in df.columns]
            if missing:
                raise ValueError(f"No rainfall column for zones {missing}.")

        # Zone of every model cell, from its centre
        t = self.model.reggrid.transform
        nmax, mmax = int(self.model.config["nmax"]), int(self.model.config["mmax"])
        jj, ii = np.meshgrid(np.arange(nmax), np.arange(mmax), indexing="ij")
        xc, yc = t * (ii + 0.5, jj + 0.5)
        cell_zone = np.zeros((nmax, mmax), dtype="int32")
        for k, geom in enumerate(gdf.geometry):
            if geom is not None:
                cell_zone[shapely.contains_xy(geom, xc, yc)] = k + 1

        if not cell_zone.any():
            raise ValueError("No model cell centre falls inside the zones.")

        # Rainfall grid around the zoned cells only (SFINCS reads 0 outside the
        # grid); each point takes the zone of the model cell it falls in
        res = resolution or float(self.model.config["dx"]) / 3.0
        pad = max(float(self.model.config["dx"]), float(self.model.config["dy"])) + 2 * res
        zx, zy = xc[cell_zone > 0], yc[cell_zone > 0]
        x = np.arange(zx.min() - pad, zx.max() + pad, res)
        y = np.arange(zy.min() - pad, zy.max() + pad, res)
        X, Y = np.meshgrid(x, y)
        m, n = ~t * (X, Y)
        m, n = np.floor(m).astype(int), np.floor(n).astype(int)
        inside = (m >= 0) & (m < mmax) & (n >= 0) & (n < nmax)
        zone_id = np.zeros(X.shape, dtype="int32")
        zone_id[inside] = cell_zone[n[inside], m[inside]]

        series = np.column_stack([np.zeros(len(df))] + [df[k].values for k in keys])
        da = xr.DataArray(
            series[:, zone_id].astype("float32"), dims=("time", "y", "x"),
            coords={"time": df.index.values, "y": y, "x": x},
            name="precip_2d", attrs={"units": "mm/hr"},
        )
        self._set_grid_forcing(da, time_interpolation)
        return self.model.forcing["precip_2d"]

    def from_grid(
        self,
        precip,
        cumulative: bool,
        time_label: str = "right",
        aggregate: bool = False,
        resolution: Optional[float] = None,
        time_interpolation: str = "block",
    ) -> None:
        """
        Set rainfall from a gridded product (reanalysis, satellite, radar, ...).

        Wraps ``SfincsModel.setup_precip_forcing_from_grid``: the data are
        clipped to the model domain and period and reprojected to the model
        CRS (``netamprfile``), or averaged over the domain into a uniform
        series (``aggregate=True``).

        Parameters
        ----------
        precip : str, Path or xarray.DataArray
            Gridded precipitation (data catalog name, file path or
            DataArray with a ``precip`` variable).
        cumulative : bool
            True if values are depths (mm) accumulated over each time step,
            False if they are rates (mm/h). No default, to avoid a silent
            unit error.
        time_label : {'right', 'left'}, optional
            For cumulative data, whether each depth is labelled at the end
            (default) or the start of its interval.
        aggregate : bool, optional
            If True, apply the domain mean as a uniform series.
        resolution : float, optional
            Cell size (m) after reprojection. Default keeps the source one.
        time_interpolation : {'block', 'linear'}, optional
            For gridded output only; see :meth:`from_zones`.

        Examples
        --------
        >>> precip.from_grid("era5_hourly", cumulative=True)
        """
        self._clear()
        self.model.setup_precip_forcing_from_grid(
            precip=precip, dst_res=resolution, cumulative_input=cumulative,
            time_label=time_label, aggregate=aggregate,
        )
        if not aggregate:
            # HydroMT stores cell-centre coordinates; rewrite them in the
            # convention SFINCS reads (see _set_grid_forcing)
            self._set_grid_forcing(self.model.forcing.pop("precip_2d"), time_interpolation)

    # --------------------------------------------------
    # Spiderweb
    # --------------------------------------------------
    def from_spiderweb(
        self,
        path: Union[str, Path],
        use_precip: bool = True,
        merge_frac: Optional[float] = None,
    ) -> str:
        """
        Use an existing tropical-cyclone spiderweb file.

        The file also drives wind and pressure. It is copied to the model
        folder and registered as ``spwfile`` (ASCII) or ``netspwfile``
        (NetCDF, ``.nc``).

        Parameters
        ----------
        path : str or Path
            Spiderweb file.
        use_precip : bool, optional
            Use the rainfall stored in the spiderweb (``usespwprecip``).
            Default is True.
        merge_frac : float, optional
            Fraction of the spiderweb radius beyond which its wind is merged
            with the background wind (``spwmergefrac``; SFINCS default 0.5).

        Returns
        -------
        str
            Path of the copied file.

        Notes
        -----
        Within the spiderweb radius its rainfall is used; outside it SFINCS
        uses the uniform or gridded rainfall, if any.

        Examples
        --------
        >>> precip.from_spiderweb("hurricane.spw")
        """
        src = Path(path)
        dst = Path(self.model.root) / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        key = "netspwfile" if src.suffix.lower() == ".nc" else "spwfile"
        self.model.config.pop("spwfile", None)
        self.model.config.pop("netspwfile", None)
        self.model.set_config(key, src.name)
        self.model.set_config("usespwprecip", int(use_precip))
        if merge_frac is not None:
            self.model.set_config("spwmergefrac", float(merge_frac))
        return str(dst)

    # --------------------------------------------------
    # Options
    # --------------------------------------------------
    def set_factor(self, factor: float) -> None:
        """
        Multiply every rainfall input by ``factor`` (``factor_prcp``).

        Useful for sensitivity runs without rewriting the forcing.
        """
        self.model.set_config("factor_prcp", float(factor))

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _set_grid_forcing(self, da, time_interpolation):
        if time_interpolation not in ("block", "linear"):
            raise ValueError("time_interpolation must be 'block' or 'linear'.")
        self._clear()
        da = da.transpose("time", "y", "x").astype("float32").sortby("x").sortby("y")
        dx = float(da["x"].values[1] - da["x"].values[0])
        dy = float(da["y"].values[1] - da["y"].values[0])
        # SFINCS places value i at x[i] + dx/2 (sfincs_ncinput.F90): write the
        # lower-left corner of each cell instead of its centre
        da = da.assign_coords(x=("x", da["x"].values - dx / 2), y=("y", da["y"].values - dy / 2))
        da["x"].attrs["units"] = da["y"].attrs["units"] = "m"
        da.name = "precip_2d"
        self.model.set_forcing(da, name="precip_2d")
        self.model.set_config("netamprfile", "precip_2d.nc")
        self.model.set_config("amprblock", 1 if time_interpolation == "block" else 0)
        step = pd.Series(da["time"].values).diff().dt.total_seconds().min()
        if np.isfinite(step) and float(self.model.config.get("dtwnd", 1800)) > step:
            self.model.set_config("dtwnd", float(step))

    def _clear(self):
        for key in _CONFIG_KEYS:
            self.model.config.pop(key, None)
        for key in _FORCING_KEYS:
            self.model.forcing.pop(key, None)
