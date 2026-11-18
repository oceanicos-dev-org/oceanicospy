from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize as rio_rasterize
from rasterio.transform import from_origin

from hydromt_sfincs import SfincsModel

#: Model attribute where the roughness choice is kept for subgrid tables
ROUGHNESS_ATTR = "_oceanicospy_roughness"


class BottomFriction:
    """
    Manning roughness for SFINCS models.

    Two levels, both through ``SfincsModel.setup_manning_roughness``:

    - :meth:`setup_uniform`: one value on land and one at sea, split by a
      reference elevation (written as ``manningfile``).
    - :meth:`setup_from_landcover`: spatially varying roughness from a
      categorical land-cover raster and a reclassification table
      (class -> Manning n). Cells without land cover get the land or sea
      value according to their elevation, as in :meth:`setup_uniform`.

    With subgrid tables (``BathyMaker.setup_subgrid``) SFINCS takes the
    roughness from the tables, not from ``manningfile``. Each method also
    records its choice in the model, and ``setup_subgrid`` uses it to build
    the tables; call this class **before** ``setup_subgrid``. Models without
    subgrid are not affected.

    :meth:`rasterize_landcover` and :meth:`write_reclass_table` build those
    two inputs from polygons. The same land-cover raster can be reused for
    infiltration (``Infiltration.setup_cn_from_landcover``).

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    def setup_uniform(
        self,
        manning_land: float = 0.04,
        manning_sea: float = 0.02,
        rgh_lev_land: float = 0.0,
    ) -> None:
        """
        Set a uniform roughness, different on land and at sea.

        Parameters
        ----------
        manning_land : float, optional
            Manning n for cells with elevation >= ``rgh_lev_land``.
        manning_sea : float, optional
            Manning n for cells with elevation < ``rgh_lev_land``.
        rgh_lev_land : float, optional
            Elevation (m, same datum as ``dep``) separating land and sea.
            Default 0.0.

        Raises
        ------
        ValueError
            If the model already has subgrid tables.
        """
        self._check_no_subgrid()
        self.model.setup_manning_roughness(
            manning_land=manning_land,
            manning_sea=manning_sea,
            rgh_lev_land=rgh_lev_land,
        )
        self._record(datasets_rgh=[], manning_land=manning_land,
                     manning_sea=manning_sea, rgh_lev_land=rgh_lev_land)

    def setup_from_landcover(
        self,
        lulc_path: Union[str, Path],
        reclass_table: Union[str, Path],
        manning_land: float = 0.035,
        manning_sea: float = 0.02,
        rgh_lev_land: float = 0.0,
    ) -> None:
        """
        Set a spatially varying roughness from a categorical land-cover raster.

        Parameters
        ----------
        lulc_path : str or Path
            Land-cover raster (one integer class per cell, e.g. from
            :meth:`rasterize_landcover`). A file path is accepted directly;
            it does not need to be in the data catalog.
        reclass_table : str or Path
            CSV with the class -> Manning n mapping (e.g. from
            :meth:`write_reclass_table`).
        manning_land, manning_sea : float, optional
            Fallback values for cells without land cover (nodata in
            ``lulc_path``), split by ``rgh_lev_land``.
        rgh_lev_land : float, optional
            Reference elevation (m) for the land/sea fallback.

        Notes
        -----
        HydroMT resamples the land cover to the model grid with linear
        interpolation, so cells on the border between two classes can get an
        intermediate Manning value.

        Raises
        ------
        ValueError
            If the model already has subgrid tables.
        """
        self._check_no_subgrid()
        datasets_rgh = [{"lulc": str(lulc_path), "reclass_table": str(reclass_table)}]
        self.model.setup_manning_roughness(
            datasets_rgh=datasets_rgh,
            manning_land=manning_land,
            manning_sea=manning_sea,
            rgh_lev_land=rgh_lev_land,
        )
        self._record(datasets_rgh=datasets_rgh, manning_land=manning_land,
                     manning_sea=manning_sea, rgh_lev_land=rgh_lev_land)

    def _check_no_subgrid(self) -> None:
        if "sbgfile" in self.model.config:
            raise ValueError(
                "The model already has subgrid tables, which hold the roughness. "
                "Set the roughness before BathyMaker.setup_subgrid and build the "
                "subgrid again."
            )

    def _record(self, **roughness) -> None:
        setattr(self.model, ROUGHNESS_ATTR, roughness)

    @staticmethod
    def rasterize_landcover(
        class_polygons: Dict[int, List[gpd.GeoDataFrame]],
        out_path: Union[str, Path],
        resolution: float,
        bounds: tuple,
        crs,
        nodata: int = 0,
        dtype: str = "uint8",
    ) -> str:
        """
        Burn polygon layers into a categorical land-cover raster, for
        :meth:`setup_from_landcover` (and ``Infiltration``).

        Classes are burned in the order of ``class_polygons``: a later class
        overwrites an earlier one where they overlap. For example, a whole
        catchment can be burned as "pervious" and then its impervious part
        on top, without computing the geometric difference.

        Parameters
        ----------
        class_polygons : dict of {int: list of GeoDataFrame}
            Class id (integer > 0; 0 is reserved for ``nodata``) to the
            GeoDataFrames with its polygons. Each GeoDataFrame is reprojected
            to ``crs`` if needed.
        out_path : str or Path
            Output GeoTIFF.
        resolution : float
            Cell size (m) of the output raster.
        bounds : tuple of (xmin, ymin, xmax, ymax)
            Extent of the output raster, in ``crs``.
        crs : CRS-like
            Output CRS (e.g. ``32617`` or ``"EPSG:32617"``).
        nodata : int, optional
            Value of cells without a class (default 0).
        dtype : str, optional
            Output data type (default ``"uint8"``).

        Returns
        -------
        str
            Path of the written GeoTIFF.
        """
        xmin, ymin, xmax, ymax = bounds
        width = int(np.ceil((xmax - xmin) / resolution))
        height = int(np.ceil((ymax - ymin) / resolution))
        transform = from_origin(xmin, ymax, resolution, resolution)

        out_array = np.full((height, width), nodata, dtype=dtype)

        for class_id, gdfs in class_polygons.items():
            shapes = []
            for gdf in gdfs:
                if gdf.crs is not None and str(gdf.crs) != str(crs):
                    gdf = gdf.to_crs(crs)
                shapes.extend((geom, class_id) for geom in gdf.geometry if geom is not None)

            if not shapes:
                continue

            rio_rasterize(
                shapes,
                out_shape=(height, width),
                transform=transform,
                fill=nodata,
                out=out_array,
                dtype=dtype,
            )

        out_path = Path(out_path)
        with rasterio.open(
            out_path, "w", driver="GTiff",
            height=height, width=width, count=1,
            dtype=dtype, crs=crs, transform=transform, nodata=nodata,
        ) as dst:
            dst.write(out_array, 1)

        return str(out_path)

    @staticmethod
    def write_reclass_table(
        mapping: Dict[int, float],
        out_path: Union[str, Path],
    ) -> str:
        """
        Write a class -> Manning n reclassification table in the format
        HydroMT-SFINCS expects (CSV with the class id as index and an ``N``
        column).

        Parameters
        ----------
        mapping : dict of {int: float}
            Class id to Manning n.
        out_path : str or Path
            Output CSV.

        Returns
        -------
        str
            Path of the written CSV.
        """
        out_path = Path(out_path)
        lines = [",N"] + [f"{class_id},{n}" for class_id, n in mapping.items()]
        out_path.write_text("\n".join(lines) + "\n")
        return str(out_path)
