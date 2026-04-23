"""
crs_tools
=========
Coordinate reference system (CRS) utilities for point file reprojection.

This module provides tools to load point data from vector files (.shp,
.geojson, .gpkg) or XYZ text files, reproject coordinates to a target
CRS, and export the result as an XYZ file.

CRS normalization is delegated to ``io_xyz._normalize_epsg`` to ensure
consistent behaviour across the subpackage.

Public API
----------
PointFileReprojector
    Load, reproject and export point data from vector or XYZ files.
reproject_xyz_file
    Convenience function to reproject an XYZ file in a single call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import geopandas as gpd

from .io_xyz import (
    XYZFormatSpec,
    _normalize_epsg,
    load_xyz_as_geodataframe,
    save_xyz_from_geodataframe,
)

__all__ = [
    "PointFileReprojector",
    "reproject_xyz_file",
]

#: Vector file extensions handled directly by GeoPandas.
_VECTOR_EXTENSIONS: tuple[str, ...] = (".shp", ".geojson", ".gpkg")


# ---------------------------------------------------------------------------
# PointFileReprojector
# ---------------------------------------------------------------------------

class PointFileReprojector:
    """
    Load point data from a vector or XYZ file, reproject it, and export
    the result as an XYZ plain-text file.

    Supported input formats
    -----------------------
    - Vector files (``.shp``, ``.geojson``, ``.gpkg``): CRS is read from
      file metadata when available.  Pass *source_epsg* only when the
      file lacks a CRS definition.
    - XYZ text files (``.xyz``, ``.txt``): *source_epsg* is required
      because plain-text files carry no CRS metadata.

    Parameters
    ----------
    input_path : str or pathlib.Path
        Path to the input file.
    z_column : str, optional
        Name of the attribute column that holds elevation or depth values.
        For XYZ files this must match the column name in *format_spec*.
    source_epsg : str or int, optional
        CRS of the input data (e.g. ``4326`` or ``"EPSG:4326"``).  Required
        for XYZ files.  For vector files it overrides the file metadata
        only when no CRS is embedded.
    format_spec : XYZFormatSpec, optional
        Layout descriptor used for both reading XYZ input files and writing
        XYZ output files.  When ``None`` a default :class:`~io_xyz.XYZFormatSpec`
        is used.  Ignored for vector input formats.

    Attributes
    ----------
    gdf : geopandas.GeoDataFrame
        Internal GeoDataFrame populated after loading.  Use this attribute
        to inspect or further process the data before exporting.
    """

    def __init__(
        self,
        input_path: Union[str, Path],
        z_column: str = "z",
        source_epsg: Optional[Union[str, int]] = None,
        format_spec: Optional[XYZFormatSpec] = None,
    ) -> None:
        self.input_path = Path(input_path)
        self.z_column = z_column
        self.source_epsg = source_epsg
        self.format_spec = format_spec or XYZFormatSpec()
        self.gdf: gpd.GeoDataFrame = self._load()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def crs(self):
        """
        CRS of the internal GeoDataFrame.

        Returns
        -------
        pyproj.CRS or None
            The current CRS as managed by GeoPandas.
        """
        return self.gdf.crs

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _load(self) -> gpd.GeoDataFrame:
        """
        Load the input file into a GeoDataFrame.

        Returns
        -------
        geopandas.GeoDataFrame

        Raises
        ------
        ValueError
            If the file has no embedded CRS and *source_epsg* was not
            provided, or if *z_column* is absent from a vector file.
        ValueError
            If *source_epsg* is required but was not provided for an
            XYZ file.
        """
        if self.input_path.suffix.lower() in _VECTOR_EXTENSIONS:
            return self._load_vector()
        return self._load_xyz()

    def _load_vector(self) -> gpd.GeoDataFrame:
        """Load a vector file (.shp, .geojson, .gpkg) via GeoPandas."""
        gdf = gpd.read_file(self.input_path)

        if gdf.crs is None:
            if self.source_epsg is None:
                raise ValueError(
                    f"'{self.input_path.name}' has no embedded CRS. "
                    "Provide source_epsg so coordinates can be interpreted correctly."
                )
            gdf = gdf.set_crs(_normalize_epsg(self.source_epsg))

        if self.z_column not in gdf.columns:
            raise ValueError(
                f"Column '{self.z_column}' not found in '{self.input_path.name}'. "
                f"Available columns: {list(gdf.columns)}"
            )

        return gdf

    def _load_xyz(self) -> gpd.GeoDataFrame:
        """Load an XYZ text file via io_xyz."""
        if self.source_epsg is None:
            raise ValueError(
                "source_epsg is required for XYZ text files because they "
                "carry no CRS metadata."
            )

        return load_xyz_as_geodataframe(
            file_path=self.input_path,
            format_spec=self.format_spec,
            crs=self.source_epsg,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def reproject_to_epsg(self, target_epsg: Union[str, int]) -> None:
        """
        Reproject the internal GeoDataFrame to a target CRS in place.

        Parameters
        ----------
        target_epsg : str or int
            Target EPSG code (e.g. ``9377`` or ``"EPSG:9377"``).

        Raises
        ------
        ValueError
            If the internal GeoDataFrame has no CRS defined.
        """
        if self.gdf.crs is None:
            raise ValueError(
                "Source CRS is not defined. "
                "Assign source_epsg before reprojecting."
            )
        self.gdf = self.gdf.to_crs(_normalize_epsg(target_epsg))

    def to_xyz(
        self,
        output_path: Union[str, Path],
        format_spec: Optional[XYZFormatSpec] = None,
        float_format: str = "%.3f",
        include_header: Optional[bool] = None,
    ) -> None:
        """
        Export the current GeoDataFrame to an XYZ plain-text file.

        Parameters
        ----------
        output_path : str or pathlib.Path
            Destination file path.
        format_spec : XYZFormatSpec, optional
            Layout descriptor for the output file.  When ``None`` the
            instance's *format_spec* (set at construction) is reused,
            so input and output share the same layout by default.
        float_format : str, optional
            ``printf``-style format string for floating-point values.
        include_header : bool, optional
            Override whether a header row is written.  When ``None`` the
            value is taken from the effective *format_spec*.

        Raises
        ------
        ValueError
            If *z_column* is not present in the internal GeoDataFrame.
        """
        effective_spec = format_spec or self.format_spec

        save_xyz_from_geodataframe(
            gdf=self.gdf,
            file_path=output_path,
            format_spec=effective_spec,
            z_column=self.z_column,
            float_format=float_format,
            include_header=include_header,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def reproject_xyz_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    source_epsg: Union[str, int],
    target_epsg: Union[str, int],
    z_column: str = "z",
    format_spec: Optional[XYZFormatSpec] = None,
    float_format: str = "%.3f",
    include_header: Optional[bool] = None,
) -> None:
    """
    Reproject an XYZ file from one CRS to another in a single call.

    This is a thin convenience wrapper around :class:`PointFileReprojector`.
    It is equivalent to instantiating the class, calling
    :meth:`~PointFileReprojector.reproject_to_epsg` and then
    :meth:`~PointFileReprojector.to_xyz`.

    Parameters
    ----------
    input_path : str or pathlib.Path
        Path to the input XYZ file.
    output_path : str or pathlib.Path
        Path to the output XYZ file.
    source_epsg : str or int
        CRS of the input file (e.g. ``32617`` or ``"EPSG:32617"``).
    target_epsg : str or int
        Target CRS (e.g. ``9377`` or ``"EPSG:9377"``).
    z_column : str, optional
        Name of the column containing elevation or depth values.
    format_spec : XYZFormatSpec, optional
        Layout descriptor used for both reading and writing.  When
        ``None`` a default :class:`~io_xyz.XYZFormatSpec` is used.
    float_format : str, optional
        ``printf``-style format string for floating-point values.
    include_header : bool, optional
        Override whether a header row is written in the output file.

    Notes
    -----
    Use :class:`PointFileReprojector` directly when you need to inspect
    or modify the data between loading and exporting.
    """
    reprojector = PointFileReprojector(
        input_path=input_path,
        z_column=z_column,
        source_epsg=source_epsg,
        format_spec=format_spec,
    )
    reprojector.reproject_to_epsg(target_epsg)
    reprojector.to_xyz(
        output_path=output_path,
        float_format=float_format,
        include_header=include_header,
    )