from typing import Dict, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from hydromt_sfincs import SfincsModel

__all__ = ["DischargeForcing"]


class DischargeForcing:
    """
    Point discharges for SFINCS (``srcfile`` / ``disfile``).

    Each point has a discharge series in m³/s: positive values add water to
    the model cell that contains the point, negative values remove it.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT, with grid and model
        times already set.

    Attributes
    ----------
    point_ids : dict
        ``{point name: SFINCS point number}`` for every point set so far
        (HydroMT numbers the points with integers).

    Notes
    -----
    - SFINCS limits an extraction to the water present in the cell
      (``sfincs_continuity.f90``): when a negative discharge asks for more,
      only the available volume is removed and the rest is not reported.
    - HydroMT writes ``sfincs.dis`` with two decimals (``%7.2f``), which
      rounds small discharges to zero. Write the case with
      ``SfincsCaseBuilder.write`` (six decimals), or call
      ``model.write_forcing(data_vars=["discharge"], fmt="%12.6f")``.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model
        self.point_ids: Dict[object, int] = {}

    def from_dataframe(
        self,
        df: pd.DataFrame,
        locations: Dict[object, Tuple[float, float]],
        merge: bool = True,
    ) -> Dict[object, int]:
        """
        Add discharge points from a table of series.

        Parameters
        ----------
        df : pandas.DataFrame
            Datetime index and one discharge column (m³/s) per point, named
            as the keys of ``locations``.
        locations : dict
            ``{point name: (x, y)}`` in the model CRS.
        merge : bool, optional
            If True (default), keep the points set by earlier calls (a point
            with the same name is replaced); otherwise replace them all.

        Returns
        -------
        dict
            :attr:`point_ids`.

        Raises
        ------
        ValueError
            If a point has no column in ``df``, or the series have no values
            within the model period.

        Examples
        --------
        >>> dq = DischargeForcing(model)
        >>> dq.from_dataframe(df, locations={"outfall": (423630.4, 1390276.2)})
        """
        missing = [pid for pid in locations if pid not in df.columns]
        if missing:
            raise ValueError(f"No discharge column for points {missing}.")
        tstart, tstop = self.model.get_model_time()
        ids = list(locations)
        df_out = df[ids].sort_index().loc[tstart:tstop].astype(float).dropna()
        if df_out.empty:
            raise ValueError("The discharge series have no values within the model period.")

        if not merge:
            self.point_ids = {}
            self.model.forcing.pop("dis", None)
        for pid in ids:
            if pid not in self.point_ids:
                self.point_ids[pid] = max(self.point_ids.values(), default=0) + 1

        numbers = [self.point_ids[pid] for pid in ids]
        gdf = gpd.GeoDataFrame(
            index=numbers,
            geometry=gpd.points_from_xy([locations[p][0] for p in ids], [locations[p][1] for p in ids]),
            crs=self.model.crs,
        )
        self.model.setup_discharge_forcing(
            timeseries=df_out.rename(columns=self.point_ids), locations=gdf, merge=True
        )
        return self.point_ids

    def distributed(
        self,
        series: pd.DataFrame,
        cells: Union[pd.DataFrame, gpd.GeoDataFrame],
        group_col: str = "group",
        weight_col: str = "weight",
        sign: float = -1.0,
        merge: bool = True,
        tol: float = 1e-3,
    ) -> pd.DataFrame:
        """
        Spread each group discharge over several cells with weights.

        For every row of ``cells`` a point discharge
        ``sign * weight * series[group]`` is added. Typical use: the inflow
        to a drainage inlet, computed by a sewer model, removed from the
        street cells that drain to it (``sign=-1``, so a negative inflow, a
        surcharge, returns water to those cells).

        Parameters
        ----------
        series : pandas.DataFrame
            Datetime index and one discharge column (m³/s) per group.
        cells : DataFrame or GeoDataFrame
            One row per cell with the group name (``group_col``), the
            weight (``weight_col``) and the position: ``x`` and ``y``
            columns in the model CRS, or point geometries.
        group_col, weight_col : str, optional
            Column names in ``cells``. Defaults ``"group"`` and ``"weight"``.
        sign : float, optional
            Factor applied to the group discharge. Default -1 (a positive
            group discharge leaves the model).
        merge : bool, optional
            Keep the points set by earlier calls (default).
        tol : float, optional
            Allowed deviation from 1 of the sum of weights of each group.

        Returns
        -------
        pandas.DataFrame
            The points added: name, group, x, y and weight.

        Raises
        ------
        ValueError
            If a group has no column in ``series``, its weights do not add up
            to 1, or a point is outside the active model cells.

        Examples
        --------
        >>> cells = pd.read_csv("capture_cells.csv")   # group, x, y, weight
        >>> dq.distributed(inlet_inflow, cells)
        """
        tab = pd.DataFrame(cells).copy()
        if isinstance(cells, gpd.GeoDataFrame):
            pts = cells.to_crs(self.model.crs).geometry
            tab["x"], tab["y"] = pts.x.values, pts.y.values
        missing = sorted(set(tab[group_col]) - set(series.columns))
        if missing:
            raise ValueError(f"No discharge column for groups {missing}.")
        sums = tab.groupby(group_col)[weight_col].sum()
        bad = sums[(sums - 1.0).abs() > tol]
        if not bad.empty:
            raise ValueError(f"Weights do not add up to 1 for groups: {bad.round(4).to_dict()}.")

        # every point must fall in an active cell
        msk = self.model.grid["msk"].values
        m, n = ~self.model.reggrid.transform * (tab["x"].values, tab["y"].values)
        m, n = np.floor(m).astype(int), np.floor(n).astype(int)
        nmax, mmax = msk.shape
        ok = (m >= 0) & (m < mmax) & (n >= 0) & (n < nmax)
        ok[ok] = msk[n[ok], m[ok]] > 0
        if not ok.all():
            raise ValueError(f"{int((~ok).sum())} points are outside the active model cells.")

        tab["name"] = [f"{g}_{k:03d}" for k, g in enumerate(tab[group_col])]
        df = pd.DataFrame(
            {r.name: sign * getattr(r, weight_col) * series[getattr(r, group_col)]
             for r in tab.itertuples()},
            index=series.index,
        )
        self.from_dataframe(df, {r.name: (r.x, r.y) for r in tab.itertuples()}, merge=merge)
        return tab[["name", group_col, "x", "y", weight_col]]
