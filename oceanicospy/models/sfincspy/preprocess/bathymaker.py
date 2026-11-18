from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import warnings

import geopandas as gpd
import numpy as np
from affine import Affine
from rasterio import features
from rasterio.warp import Resampling, reproject
from scipy.ndimage import maximum_filter
from shapely.ops import transform as shp_transform

from hydromt_sfincs import SfincsModel

from .bottom_friction import ROUGHNESS_ATTR

LinesLike = Union[str, Path, gpd.GeoDataFrame]


class BathyMaker:
    """
    Topobathymetry and mask setup for SFINCS models.

    Builds the elevation raster (``dep``), optionally merging several
    topobathymetric datasets with the native HydroMT-SFINCS merge rules, and
    defines the active cells (``msk == 1``) and the boundary cells
    (``msk == 2`` or ``3``). The datasets are read from a HydroMT
    ``data_catalog``.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.
    data_catalog : str
        Path to the ``data_catalog.yml`` file defining the datasets
        (e.g. topography and bathymetry).

    Notes
    -----
    - ``dep`` holds elevations (positive on land, negative at sea).
    - ``msk`` values: 0 inactive, 1 active, 2 water-level boundary,
      3 outflow boundary.
    - The resulting rasters live in ``model.grid`` and can be plotted with
      :func:`oceanicospy.utils.plots.plot_field` together with
      ``GridMaker.cell_corners``.
    - :meth:`preserve_crests` is an optional extra step for narrow linear
      barriers (walls, curbs) that the cell averaging would dilute.
    - :meth:`setup_subgrid` builds subgrid tables from the fine DEM, so a
      coarse grid keeps the effect of the fine topography and roughness.
      It cannot be combined with :meth:`preserve_crests`.
    """

    def __init__(self, model: SfincsModel, data_catalog: str) -> None:
        self.model = model
        self.data_catalog = data_catalog
        self.datasets_dep: Optional[List[Dict[str, Any]]] = None
        self.crests_applied = False

    def setup_bathy(
        self,
        datasets_dep: Optional[List[Dict[str, Any]]] = None,
        zmin_active: float = -4,
        zmax_bounds: float = -2,
        btype: str = "waterlevel",
        mask: Optional[str] = None,
        drop_area: float = 0.0,
        reset_mask: bool = True,
        reset_bounds: bool = True,
    ) -> None:
        """
        Set up the topobathymetry and masks of the SFINCS model.

        Runs, in order: elevation raster (``dep``), active cells and
        hydraulic boundary cells.

        Parameters
        ----------
        datasets_dep : list of dict, optional
            Topobathymetric datasets to merge, in the format expected by
            ``SfincsModel.setup_dep``: each entry is a dict with the key
            ``"elevtn"`` (dataset name in the ``data_catalog``) and,
            optionally, merge arguments such as ``zmin``, ``zmax``,
            ``offset``, ``merge_method`` or ``reproj_method`` (see
            :py:func:`hydromt.workflows.merge_multi_dataarrays`). For
            example, to give priority to a fine survey over a coarser
            filler DEM::

                [
                    {"elevtn": "topobathy_fine"},
                    {"elevtn": "topobathy_coarse", "merge_method": "first"},
                ]

            Defaults to a single dataset named ``"topobathy"``.
        zmin_active : float, optional
            Minimum elevation (m) of active cells; cells at or above this
            value are active. Default is -4.
        zmax_bounds : float, optional
            Maximum elevation (m) of the boundary cells. The SFINCS manual
            recommends placing the offshore boundary around the swash zone,
            roughly 2 m deep, hence the default of -2.
        btype : str, optional
            Boundary type, ``"waterlevel"`` (default) or ``"outflow"``.
        mask : str, optional
            Domain polygon (name of a ``GeoDataFrame`` in the
            ``data_catalog`` or path to a vector file). Only cells inside it
            can be active; outside it the model is inactive and its land
            edges are closed. If None, the whole grid rectangle is a
            candidate.
        drop_area : float, optional
            Maximum area (km²) of isolated active regions to discard (e.g.
            small cays or shoals that would otherwise remain as active
            islands with their own boundary). Default is 0.0 (none).
        reset_mask : bool, optional
            If True (default), reset the existing active mask.
        reset_bounds : bool, optional
            If True (default), reset existing boundaries of type ``btype``
            before setting the new ones.

        Returns
        -------
        None

        Notes
        -----
        Every dataset referenced in ``datasets_dep`` must be defined in the
        ``data_catalog`` (see ``Initializer.write_data_catalog``).

        Examples
        --------
        >>> bathy = BathyMaker(model, "data_catalog.yml")
        >>> bathy.setup_bathy(zmin_active=-5, zmax_bounds=-2)
        """
        if datasets_dep is None:
            datasets_dep = [{"elevtn": "topobathy"}]

        self.model.setup_dep(datasets_dep=datasets_dep)
        self.datasets_dep = datasets_dep

        self.model.setup_mask_active(
            mask=mask,
            zmin=zmin_active,
            drop_area=drop_area,
            reset_mask=reset_mask,
        )

        self.model.setup_mask_bounds(
            btype=btype,
            zmax=zmax_bounds,
            reset_bounds=reset_bounds,
        )

    def preserve_crests(
        self,
        lines: Union[LinesLike, Sequence[LinesLike]],
        dem: Union[str, Path],
        exempt_points: Optional[Union[gpd.GeoDataFrame, np.ndarray]] = None,
    ) -> Dict[str, float]:
        """
        Raise the elevation of the cells crossed by linear barriers to their crest.

        Optional step, to be called after :meth:`setup_bathy`; it is not
        applied by default. Narrow barriers (walls, curbs, medians) that are
        one or two DEM pixels wide lose height when the fine DEM is resampled
        to the model grid, particularly on a rotated grid, and the barrier
        stops being continuous. Every model cell crossed by a line takes the
        crest elevation, when that is higher than its current ``dep``; all
        other cells keep their value. The crest of a cell is the maximum DEM
        elevation of the line pixels inside it (or, for cells the line only
        clips, of those in the neighbouring cells). Because every crossed
        cell is raised, no pair of adjacent cells on opposite sides of a
        line is left below the crest, so the barrier stays continuous.

        Parameters
        ----------
        lines : str, Path, GeoDataFrame, or list of them
            Line geometries of the barriers (file paths or GeoDataFrames).
            They are reprojected to the DEM CRS.
        dem : str or Path
            Fine-resolution DEM in which the barriers are represented (file
            path or data catalog name). Usually the same source used in
            :meth:`setup_bathy`.
        exempt_points : GeoDataFrame or array of shape (n, 2), optional
            Points (x, y in the model CRS) whose cells keep their elevation,
            e.g. inlets or drainage capture cells that must stay reachable.

        Returns
        -------
        dict
            ``cells_raised``, ``cells_exempt``, ``mean_rise`` and
            ``max_rise`` (m).

        Raises
        ------
        ValueError
            If the model already has subgrid tables.

        Notes
        -----
        - The active mask and boundaries are not recomputed.
        - For regular grids without subgrid tables. Weir structures
          (``Structures.setup_weirs``) represent barriers without changing
          ``dep``; do not combine both on the same lines.

        Examples
        --------
        >>> bathy.setup_bathy(zmin_active=-4, zmax_bounds=-2)
        >>> bathy.preserve_crests(["walls.shp", "curbs.shp"], "dem_1m.tif")
        """
        if "sbgfile" in self.model.config:
            raise ValueError(
                "preserve_crests changes dep, which SFINCS does not use with subgrid "
                "tables. Represent the barriers with weirs (Structures.setup_weirs)."
            )
        da_dep = self.model.grid["dep"]
        dep = da_dep.values.astype("float32")
        nmax, mmax = dep.shape
        grid_transform = self.model.reggrid.transform

        da_dem = self.model.data_catalog.get_rasterdataset(
            str(dem) if isinstance(dem, Path) else dem, bbox=self.model.bbox, buffer=10
        )
        z = da_dem.raster.mask_nodata().values.astype("float32")
        dem_transform, dem_crs = da_dem.raster.transform, da_dem.raster.crs

        # Line pixels on the DEM grid, then the per-cell maximum of those pixels only
        if isinstance(lines, (str, Path, gpd.GeoDataFrame)):
            lines = [lines]
        geoms = []
        for item in lines:
            gdf = item if isinstance(item, gpd.GeoDataFrame) else gpd.read_file(item)
            geoms += [g for g in gdf.to_crs(self.model.crs).geometry if g is not None]
        if not geoms:
            raise ValueError("No line geometries given.")
        on_line = features.rasterize(
            [(g, 1) for g in gpd.GeoSeries(geoms, crs=self.model.crs).to_crs(dem_crs)],
            out_shape=z.shape, transform=dem_transform, fill=0, dtype="uint8",
        ) > 0
        z_line = np.where(on_line & np.isfinite(z), z, -9999.0).astype("float32")
        crest = np.full((nmax, mmax), np.nan, "float32")
        reproject(
            z_line, crest,
            src_transform=dem_transform, src_crs=dem_crs,
            dst_transform=grid_transform, dst_crs=self.model.crs,
            resampling=Resampling.max, src_nodata=-9999.0, dst_nodata=np.nan,
        )

        # Cells crossed by the lines: rasterised in grid index space (handles the
        # rotation) with all_touched, so every crossed cell is included
        to_index = ~grid_transform
        crossed = features.rasterize(
            [(shp_transform(lambda x, y: to_index * (x, y), g), 1) for g in geoms],
            out_shape=(nmax, mmax), transform=Affine.identity(),
            all_touched=True, fill=0, dtype="uint8",
        ) > 0
        # Cells the line only clips may hold no line pixel: use the neighbours' crest
        crest_near = maximum_filter(np.nan_to_num(crest, nan=-np.inf), size=3, mode="nearest")
        crest = np.where(np.isfinite(crest), crest, crest_near)
        touched = crossed & np.isfinite(crest) & (crest > dep)
        exempt = np.zeros_like(touched)
        if exempt_points is not None:
            if isinstance(exempt_points, gpd.GeoDataFrame):
                pts = exempt_points.to_crs(self.model.crs)
                xy = np.column_stack([pts.geometry.x, pts.geometry.y])
            else:
                xy = np.asarray(exempt_points, dtype=float).reshape(-1, 2)
            m, n = ~grid_transform * (xy[:, 0], xy[:, 1])
            m, n = np.floor(m).astype(int), np.floor(n).astype(int)
            inside = (m >= 0) & (m < mmax) & (n >= 0) & (n < nmax)
            exempt[n[inside], m[inside]] = True

        raise_ = touched & ~exempt
        rise = (crest - dep)[raise_]
        self.model.set_grid(da_dep.copy(data=np.where(raise_, crest, dep)), name="dep")
        self.crests_applied = True

        return {
            "cells_raised": int(raise_.sum()),
            "cells_exempt": int((touched & exempt).sum()),
            "mean_rise": round(float(rise.mean()), 3) if rise.size else 0.0,
            "max_rise": round(float(rise.max()), 3) if rise.size else 0.0,
        }

    def setup_subgrid(
        self,
        nr_subgrid_pixels: Optional[int] = None,
        datasets_dep: Optional[List[Dict[str, Any]]] = None,
        rivers: Optional[Union[str, Path, gpd.GeoDataFrame, List[Dict[str, Any]]]] = None,
        nlevels: int = 10,
        **kwargs,
    ) -> int:
        """
        Build subgrid tables from the fine topobathymetry.

        With subgrid tables, each model cell stores how volume, wet fraction
        and conveyance vary with the water level, computed from the fine
        DEM pixels inside it. A coarse grid then keeps the storage and flow
        paths of the fine topography. Wraps ``SfincsModel.setup_subgrid``.

        Call order: grid → :meth:`setup_bathy` (coarse ``dep`` and masks) →
        roughness (``BottomFriction``) → this method.

        Parameters
        ----------
        nr_subgrid_pixels : int, optional
            Subgrid pixels per cell side; must be even (HydroMT
            requirement). Default: cell size / resolution of the first
            elevation dataset, which keeps the DEM pixels without resampling.
        datasets_dep : list of dict, optional
            Elevation datasets, as in :meth:`setup_bathy`. Default: the ones
            used there.
        rivers : str, Path, GeoDataFrame or list of dict, optional
            River centrelines burnt into the subgrid, with attributes
            ``rivwth`` (width, m) and ``rivdph`` (depth, m) or ``rivbed``
            (bed level, m). A list of dict is passed unchanged as
            ``datasets_riv`` (see ``SfincsModel.setup_subgrid``).
        nlevels : int, optional
            Water levels per table. Default 10.
        **kwargs
            Other ``SfincsModel.setup_subgrid`` arguments (e.g.
            ``nrmax``, ``max_gradient``, ``q_table_option``,
            ``write_dep_tif``).

        Returns
        -------
        int
            The ``nr_subgrid_pixels`` used.

        Raises
        ------
        ValueError
            If :meth:`preserve_crests` was applied, no elevation datasets are
            known, or ``nr_subgrid_pixels`` is not even.

        Notes
        -----
        - Roughness: SFINCS takes it from the tables and ignores
          ``manningfile``. The choice made with ``BottomFriction`` before
          this call is built into the tables; without it, HydroMT defaults
          are used (0.04 land, 0.02 sea) and a warning is issued.
        - Masks: ``zmin_active`` and ``zmax_bounds`` of :meth:`setup_bathy`
          act on the coarse ``dep``. Pass ``reproj_method="average"`` in
          ``datasets_dep`` so that ``dep`` is the cell mean rather than the
          value at the cell centre.
        - ``depfile`` and ``manningfile`` are not used with subgrid;
          ``SfincsCaseBuilder.write`` leaves them out of ``sfincs.inp``.

        Examples
        --------
        >>> bathy.setup_bathy([{"elevtn": "dem_10m", "reproj_method": "average"}],
        ...                   zmin_active=-2, zmax_bounds=0)
        >>> friction.setup_uniform(manning_land=0.04, manning_sea=0.02)
        >>> bathy.setup_subgrid()          # 80 m cells, 10 m DEM -> 8 pixels
        """
        if self.crests_applied:
            raise ValueError(
                "preserve_crests was applied to dep, which SFINCS does not use with "
                "subgrid tables. Rebuild the bathymetry without it and use weirs."
            )
        datasets_dep = datasets_dep if datasets_dep is not None else self.datasets_dep
        if not datasets_dep:
            raise ValueError("No elevation datasets: call setup_bathy first or pass datasets_dep.")

        dx = abs(float(self.model.config["dx"]))
        if nr_subgrid_pixels is None:
            first = datasets_dep[0]["elevtn"]
            dem = self.model.data_catalog.get_rasterdataset(first, bbox=self.model.bbox, buffer=2)
            ratio = dx / abs(float(dem.raster.res[0]))
            nr_subgrid_pixels = max(2, int(round(ratio / 2.0)) * 2)
            if not np.isclose(ratio, nr_subgrid_pixels):
                warnings.warn(
                    f"Cell size / DEM resolution = {ratio:.2f}; using nr_subgrid_pixels = "
                    f"{nr_subgrid_pixels} (the DEM is resampled to {dx / nr_subgrid_pixels:.2f} m).",
                    stacklevel=2,
                )
        nr_subgrid_pixels = int(nr_subgrid_pixels)
        if nr_subgrid_pixels < 2 or nr_subgrid_pixels % 2:
            raise ValueError(
                f"nr_subgrid_pixels must be an even number >= 2 (got {nr_subgrid_pixels}). "
                "Choose a cell size that is an even multiple of the DEM resolution."
            )

        roughness = getattr(self.model, ROUGHNESS_ATTR, None)
        if roughness is None:
            warnings.warn(
                "No roughness set with BottomFriction; the subgrid tables use the HydroMT "
                "defaults (manning_land 0.04, manning_sea 0.02).",
                stacklevel=2,
            )
            roughness = {}

        if rivers is None:
            datasets_riv = []
        elif isinstance(rivers, list):
            datasets_riv = rivers
        else:
            datasets_riv = [{"centerlines": rivers if isinstance(rivers, gpd.GeoDataFrame) else str(rivers)}]

        self.model.setup_subgrid(
            datasets_dep=datasets_dep,
            datasets_riv=datasets_riv,
            nr_subgrid_pixels=nr_subgrid_pixels,
            nlevels=nlevels,
            **roughness,
            **kwargs,
        )
        # roughness now lives in the tables: drop the unused manning map
        if "manning" in self.model.grid:
            self.model._grid = self.model.grid.drop_vars("manning")
        return nr_subgrid_pixels
