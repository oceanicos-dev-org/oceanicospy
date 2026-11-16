from pathlib import Path
from typing import Optional, Union

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString

from hydromt_sfincs import SfincsModel

__all__ = ["Structures"]


class Structures:
    """
    Hydraulic structures for SFINCS models (``weirfile``).

    Weirs are lines on the model grid with a crest elevation. Flow between
    the cells on either side is computed with a weir formula once the water
    level exceeds the crest, so they represent levees, walls or curbs
    without changing the cell elevations (``dep``). Built on
    ``SfincsModel.setup_structures``.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT (grid already set).

    Notes
    -----
    Do not combine weirs with ``BathyMaker.preserve_crests`` on the same
    lines: the barrier would be represented twice.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    def setup_weirs(
        self,
        lines: Union[str, Path, gpd.GeoDataFrame],
        dem: Optional[Union[str, Path]] = None,
        buffer: float = 0.0,
        dz: float = 0.0,
        spacing: Optional[float] = None,
        par1: float = 0.6,
        merge: bool = True,
    ) -> gpd.GeoDataFrame:
        """
        Add weirs to the model.

        The crest elevation can be given in three ways:

        1. a ``z`` column in ``lines`` (one value per line);
        2. 3D line geometries (``LineString Z``), one value per vertex;
        3. sampled from a DEM (``dem``): the maximum elevation within
           ``buffer`` of each point along the line, plus ``dz``.

        Parameters
        ----------
        lines : str, Path or GeoDataFrame
            Weir line geometries (file path, data catalog name or
            GeoDataFrame). Optional columns: ``name``, ``z`` and ``par1``.
        dem : str or Path, optional
            DEM to sample the crest from (file path or data catalog name).
            If given, it overrides any ``z`` column or Z coordinates.
        buffer : float, optional
            Distance (m) from the line within which the maximum DEM elevation
            is taken. Default is 0 (the DEM pixel under each point).
        dz : float, optional
            Height (m) added to the sampled crest. Only used with ``dem``.
            Default is 0.
        spacing : float, optional
            Distance (m) between the points where the DEM is sampled. Default
            is the DEM resolution. Only used with ``dem``.
        par1 : float, optional
            Weir discharge coefficient for lines without a ``par1`` column.
            Default is 0.6.
        merge : bool, optional
            If True (default), add to the weirs already in the model;
            otherwise replace them.

        Returns
        -------
        geopandas.GeoDataFrame
            The weirs set in the model (``model.geoms["weir"]``).

        Raises
        ------
        ValueError
            If no crest elevation can be obtained, or the DEM has no data
            along a line.

        Notes
        -----
        Lines are clipped to the model region. When sampling the DEM, the
        lines are densified first: HydroMT alone samples only at the line
        vertices.

        Examples
        --------
        >>> structures = Structures(model)
        >>> structures.setup_weirs("levees.shp", dem="dem_1m.tif", buffer=1.0)
        >>> structures.setup_weirs(walls_gdf)          # with a "z" column
        """
        if isinstance(lines, gpd.GeoDataFrame):
            gdf = lines.copy()
        else:
            gdf = self.model.data_catalog.get_geodataframe(str(lines))
        gdf = gpd.clip(gdf.to_crs(self.model.crs), self.model.region).explode(index_parts=False)
        gdf = gdf[~gdf.geometry.is_empty].reset_index(drop=True)
        if gdf.empty:
            raise ValueError("No weir lines inside the model region.")

        if dem is not None:
            gdf = self._crest_from_dem(gdf, dem, buffer, dz, spacing)
        elif "z" not in gdf.columns and not gdf.geometry.has_z.all():
            raise ValueError(
                "Weir crest unknown: give a 'z' column, 3D line geometries or a dem."
            )

        if "par1" not in gdf.columns:
            gdf["par1"] = par1
        else:
            gdf["par1"] = gdf["par1"].fillna(par1)

        self.model.setup_structures(gdf, stype="weir", merge=merge)
        return self.model.geoms["weir"]

    def _crest_from_dem(self, gdf, dem, buffer, dz, spacing):
        da = self.model.data_catalog.get_rasterdataset(
            str(dem), geom=self.model.region, buffer=10
        ).raster.mask_nodata()
        z = da.values
        res = abs(da.raster.res[0])
        inv = ~da.raster.transform
        wdw = int(np.ceil(buffer / res))
        spacing = spacing or res

        geoms = []
        for i, line in enumerate(gdf.geometry):
            line = LineString([c[:2] for c in line.coords]).segmentize(spacing)
            xy = np.asarray(line.coords)
            col, row = inv * (xy[:, 0], xy[:, 1])
            col, row = np.floor(col).astype(int), np.floor(row).astype(int)
            crest = np.full(len(xy), np.nan)
            for dr in range(-wdw, wdw + 1):
                for dc in range(-wdw, wdw + 1):
                    r, c = row + dr, col + dc
                    ok = (r >= 0) & (r < z.shape[0]) & (c >= 0) & (c < z.shape[1])
                    vals = np.full(len(xy), np.nan)
                    vals[ok] = z[r[ok], c[ok]]
                    crest = np.fmax(crest, vals)
            if np.isnan(crest).any():
                raise ValueError(f"The DEM has no data along weir line {i}.")
            geoms.append(LineString(np.column_stack([xy, crest + dz])))

        return gdf.drop(columns="z", errors="ignore").set_geometry(
            gpd.GeoSeries(geoms, crs=gdf.crs)
        )
