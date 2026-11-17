"""
Flood metrics from SFINCS output.

All functions take the Dataset returned by
:meth:`SfincsOutputReader.read_map` (or :meth:`~SfincsOutputReader.read_his`)
and an optional boolean ``mask`` of cells (``y, x``), e.g. from
:func:`zone_mask` combined with a bed-level condition such as
``ds["zb"] > 0``. Map variables stored per output window (``timemax``) are
reduced over the whole run.
"""
from pathlib import Path
from typing import Dict, Optional, Sequence, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

__all__ = [
    "zone_mask",
    "flooded_area",
    "water_volume",
    "wet_duration",
    "hazard",
    "compound_effect",
    "difference",
    "sink_shortfall",
    "downscale",
]


def _overall_max(ds: xr.Dataset, var: str) -> xr.DataArray:
    if var not in ds:
        raise KeyError(f"'{var}' is not in the output; enable it in sfincs.inp before the run.")
    da = ds[var]
    return da.max("timemax") if "timemax" in da.dims else da


def _apply(da: xr.DataArray, mask) -> xr.DataArray:
    return da if mask is None else da.where(np.asarray(mask, dtype=bool))


def zone_mask(ds: xr.Dataset, zones: Union[str, Path, gpd.GeoDataFrame, shapely.Geometry]) -> xr.DataArray:
    """
    Cells whose centre falls inside the given polygons.

    Parameters
    ----------
    ds : xarray.Dataset
        Map output with cell-centre coordinates ``xc`` and ``yc``.
    zones : str, Path, GeoDataFrame or shapely geometry
        Polygons (reprojected to the model CRS when they carry a CRS).

    Returns
    -------
    xarray.DataArray
        Boolean mask ``(y, x)``.
    """
    if isinstance(zones, (str, Path)):
        zones = gpd.read_file(zones)
    if isinstance(zones, gpd.GeoDataFrame):
        if zones.crs is not None and ds.raster.crs is not None:
            zones = zones.to_crs(ds.raster.crs)
        geom = zones.union_all()
    else:
        geom = zones
    inside = shapely.contains_xy(geom, ds["xc"].values, ds["yc"].values)
    return xr.DataArray(inside, dims=("y", "x"), coords={"xc": ds["xc"], "yc": ds["yc"]})


def flooded_area(ds: xr.Dataset, threshold: float, mask=None, var: str = "hmax") -> float:
    """
    Area (m²) of the cells whose maximum depth exceeds ``threshold`` (m).
    """
    hmax = _apply(_overall_max(ds, var), mask)
    return float(ds["cell_area"].where(hmax > threshold).sum())


def water_volume(ds: xr.Dataset, mask=None, min_depth: float = 0.0) -> pd.Series:
    """
    Water volume (m³) on the selected cells at every map output time.

    Parameters
    ----------
    ds : xarray.Dataset
        Map output with ``h``.
    mask : array-like of bool, optional
        Cells to include.
    min_depth : float, optional
        Depths at or below this value (m) are not counted, e.g. 0.01 to
        leave out the thin film of a recently wetted surface.
    """
    h = _apply(ds["h"], mask)
    vol = (h.where(h > min_depth) * ds["cell_area"]).sum(("y", "x"))
    return vol.to_series().rename("volume_m3")


def wet_duration(ds: xr.Dataset, mask=None) -> xr.DataArray:
    """
    Time (hours) each cell stayed wet over the run.

    Uses ``tmax``, which SFINCS writes with ``storetwet = 1``; a cell counts
    as wet while its depth exceeds ``twet_threshold`` (``sfincs.inp``).
    """
    if "tmax" not in ds:
        raise KeyError("'tmax' is not in the output; set storetwet = 1 (and twet_threshold) before the run.")
    dur = ds["tmax"].sum("timemax", min_count=1) if "timemax" in ds["tmax"].dims else ds["tmax"]
    return _apply(dur / 3600.0, mask).rename("wet_duration_h")


def hazard(
    ds: xr.Dataset,
    bounds: Sequence[float],
    labels: Optional[Sequence[str]] = None,
    min_depth: float = 0.0,
    mask=None,
) -> xr.Dataset:
    """
    Flood hazard from depth times velocity, classified by user bounds.

    Parameters
    ----------
    ds : xarray.Dataset
        Map output with ``hmax`` and ``vmax`` (``storevelmax = 1``).
    bounds : sequence of float
        Increasing upper limits of h·v (m²/s) for each class except the
        last, e.g. ``[0.25, 0.5, 1.0]`` gives four classes.
    labels : sequence of str, optional
        One name per class (``len(bounds) + 1``).
    min_depth : float, optional
        Cells with maximum depth below this value (m) get no class.
    mask : array-like of bool, optional
        Cells to evaluate.

    Returns
    -------
    xarray.Dataset
        ``hv`` (m²/s) and ``hazard_class`` (0 for the lowest class, NaN
        where not evaluated); the labels are in ``hazard_class.attrs``.

    Notes
    -----
    The maximum depth and the maximum velocity of a cell may occur at
    different times, so h·v is an upper estimate.
    """
    if labels is not None and len(labels) != len(bounds) + 1:
        raise ValueError("labels needs one entry more than bounds.")
    if np.any(np.diff(bounds) <= 0):
        raise ValueError("bounds must be increasing.")
    h, v = _overall_max(ds, "hmax"), _overall_max(ds, "vmax")
    hv = _apply((h * v).where(h >= min_depth), mask)
    cls = xr.apply_ufunc(np.digitize, hv, kwargs={"bins": np.asarray(bounds)}).where(hv.notnull())
    cls.attrs["labels"] = list(labels) if labels is not None else [str(i) for i in range(len(bounds) + 1)]
    cls.attrs["bounds"] = list(bounds)
    return xr.Dataset({"hv": hv, "hazard_class": cls})


def compound_effect(
    coastal: xr.Dataset,
    pluvial: xr.Dataset,
    compound: xr.Dataset,
    var: str = "hmax",
    wet: float = 0.1,
    tolerance: float = 0.05,
    mask=None,
) -> xr.Dataset:
    """
    Compound amplification and dominant driver per cell.

    Parameters
    ----------
    coastal, pluvial, compound : xarray.Dataset
        Map output of the runs with only the coastal driver, only the
        pluvial driver, and both, on the same grid.
    var : str, optional
        Variable compared. Default ``"hmax"``.
    wet : float, optional
        Minimum value (m) in the compound run for a cell to be classified.
    tolerance : float, optional
        Amplification (m) above which a cell is "compound".
    mask : array-like of bool, optional
        Cells to evaluate.

    Returns
    -------
    xarray.Dataset
        ``effect`` = compound − max(coastal, pluvial), and ``driver``:
        0 coastal, 1 pluvial, 2 compound (NaN where not classified); the
        names are in ``driver.attrs["labels"]``.
    """
    c, p, cp = (_overall_max(d, var).fillna(0.0) for d in (coastal, pluvial, compound))
    effect = _apply(cp - np.maximum(c, p), mask)
    driver = xr.where(effect > tolerance, 2, xr.where(c >= p, 0, 1)).astype(float)
    driver = driver.where((cp > wet) & effect.notnull())
    driver.attrs["labels"] = ["coastal", "pluvial", "compound"]
    return xr.Dataset({"effect": effect, "driver": driver})


def difference(a: xr.Dataset, b: xr.Dataset, var: str = "hmax", mask=None) -> xr.DataArray:
    """
    Change ``b − a`` of a map variable between two runs on the same grid.
    """
    return _apply(_overall_max(b, var) - _overall_max(a, var), mask).rename(f"d{var}")


def sink_shortfall(
    his: xr.Dataset,
    discharges: pd.DataFrame,
    stations: Dict[str, str],
    groups: Optional[Dict[str, str]] = None,
    dry_depth: float = 0.001,
) -> pd.DataFrame:
    """
    Estimate the extraction that SFINCS could not apply at point sinks.

    SFINCS removes at most the water present in the cell; a demand on a dry
    cell is silently not applied. With an observation point in each sink
    cell, the demand during the instants when that cell is dry is counted
    as not extracted.

    Parameters
    ----------
    his : xarray.Dataset
        Point output (:meth:`SfincsOutputReader.read_his`) with ``point_h``.
    discharges : pandas.DataFrame
        Imposed discharges (m³/s, negative = extraction), one column per
        sink, datetime index (as passed to ``DischargeForcing``).
    stations : dict
        ``{sink column: observation point name}``.
    groups : dict, optional
        ``{sink column: group}`` to also sum the result by group (e.g. by
        inlet).
    dry_depth : float, optional
        Depth (m) below which a cell is considered dry. Default 1 mm.

    Returns
    -------
    pandas.DataFrame
        Per sink (and per group, if given): demanded and not-extracted
        volume (m³) and their ratio.

    Notes
    -----
    The estimate is as fine as the point output interval (``dthisout``):
    use an interval of the order of a minute.
    """
    raw = his["station_name"].values if "station_name" in his else his["stations"].values
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in raw]
    names = [n.strip() for n in names]
    depth = pd.DataFrame(his["point_h"].values, index=pd.to_datetime(his["time"].values), columns=names)
    t = depth.index
    dt = np.diff(t.values).astype("timedelta64[s]").astype(float)
    dt = np.append(dt, dt[-1] if len(dt) else 0.0)

    rows = []
    for sink, station in stations.items():
        if station not in depth.columns:
            raise KeyError(f"Observation point '{station}' not in the point output.")
        q = discharges[sink].astype(float)
        q_t = np.interp(t.values.astype("int64"), q.index.values.astype("int64"), q.values)
        demand = np.clip(-q_t, 0.0, None) * dt
        dry = depth[station].values < dry_depth
        rows.append({"sink": sink, "demanded_m3": demand.sum(), "not_extracted_m3": demand[dry].sum()})
    out = pd.DataFrame(rows).set_index("sink")
    if groups is not None:
        out["group"] = [groups[s] for s in out.index]
        by = out.groupby("group")[["demanded_m3", "not_extracted_m3"]].sum()
        by.index = [f"group:{g}" for g in by.index]
        out = pd.concat([out.drop(columns="group"), by])
    out["ratio"] = out["not_extracted_m3"] / out["demanded_m3"].where(out["demanded_m3"] > 0)
    return out


def downscale(
    reader,
    dem: Union[str, Path, xr.DataArray],
    hmin: float = 0.05,
    mask: Optional[gpd.GeoDataFrame] = None,
    output: Optional[Union[str, Path]] = None,
    map_filename: str = "sfincs_map.nc",
) -> xr.DataArray:
    """
    Maximum flood depth at the resolution of a fine DEM.

    Wraps ``hydromt_sfincs.utils.downscale_floodmap``: the maximum water
    level of each model cell minus the DEM elevation, kept where it exceeds
    ``hmin``.

    Parameters
    ----------
    reader : SfincsOutputReader
        Reader of the run.
    dem : str, Path or xarray.DataArray
        Fine DEM in the model CRS or a reprojectable one.
    hmin : float, optional
        Minimum depth (m) kept. Default 0.05.
    mask : GeoDataFrame, optional
        Area to keep (e.g. land or the study area).
    output : str or Path, optional
        GeoTIFF to write.
    map_filename : str, optional
        Map file in the run folder.

    Returns
    -------
    xarray.DataArray
        Depth on the DEM grid.

    Notes
    -----
    Connectivity is not checked: a DEM depression below the cell water level
    shows as flooded even if water cannot reach it. Most useful when the
    model cells are coarser than the DEM.
    """
    from hydromt_sfincs import utils

    ds = reader.read_map(map_filename)
    zsmax = _overall_max(ds, "zsmax")
    if isinstance(dem, (str, Path)):
        dem = reader.model.data_catalog.get_rasterdataset(str(dem))
    return utils.downscale_floodmap(
        zsmax, dem, hmin=hmin, gdf_mask=mask,
        floodmap_fn=str(output) if output is not None else None,
    )
