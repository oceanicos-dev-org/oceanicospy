from __future__ import annotations

from typing import Optional, Union

import geopandas as gpd

from .io_xyz import (
    XYZFormatSpec,
    load_xyz_as_geodataframe,
    save_xyz_from_geodataframe,
)


class ShapefileReprojector:
    """
    Utility class to load point data (shapefile or XYZ-like text file),
    reproject coordinates to a target CRS, and optionally export as XYZ.

    This class assumes point-like input data with X, Y and Z information.

    Supported inputs
    ----------------
    - .shp (and other vector formats supported by GeoPandas):
        Point layer; CRS taken from file metadata when available.
    - .txt/.xyz:
        Space- or delimiter-separated table with x, y, z columns,
        parsed through the io_xyz module.

    Typical usage
    -------------
    reprojector = ShapefileReprojector(
        input_path="points.shp",
        z_column="Z",
        source_epsg=None,  # if None, read CRS from file
    )
    reprojector.reproject_to_epsg(3116)
    reprojector.to_xyz("output.xyz")
    """

    def __init__(
        self,
        input_path: str,
        x_column: str = "x",
        y_column: str = "y",
        z_column: str = "z",
        source_epsg: Optional[Union[int, str]] = None,
        xyz_format_spec: Optional[XYZFormatSpec] = None,
    ) -> None:
        """
        Initialize by loading input data into a GeoDataFrame.

        Parameters
        ----------
        input_path : str
            Path to input shapefile (.shp) or text file (.txt/.xyz).
        x_column, y_column, z_column : str
            Column names representing X, Y, Z when reading XYZ files.
            These names are used to build or map the XYZFormatSpec.
        source_epsg : int or str or None
            EPSG code of the source CRS for XYZ files or shapefiles
            without CRS metadata. If None and the file has a CRS,
            the file's CRS is used.
        xyz_format_spec : XYZFormatSpec or None
            Optional format specification to read XYZ files. If None,
            a simple specification based on x_column, y_column and
            z_column will be used.
        """
        self.input_path = input_path
        self.x_column = x_column
        self.y_column = y_column
        self.z_column = z_column
        self.source_epsg = source_epsg
        self.xyz_format_spec = xyz_format_spec
        self.gdf = self._load_input()

    @property
    def crs(self):
        """
        Return the CRS of the internal GeoDataFrame.

        Returns
        -------
        Any
            CRS object managed by GeoPandas (usually pyproj CRS).
        """
        return self.gdf.crs

    def _load_input(self) -> gpd.GeoDataFrame:
        """
        Load input file and return a GeoDataFrame with geometry.

        Returns
        -------
        geopandas.GeoDataFrame
            Point GeoDataFrame with a valid CRS.
        """
        path_lower = self.input_path.lower()

        # Case 1: vector data handled directly by GeoPandas
        if path_lower.endswith(".shp") or path_lower.endswith(".geojson") or path_lower.endswith(".gpkg"):
            gdf = gpd.read_file(self.input_path)

            # If no CRS is present and a source EPSG is provided, assign it
            if gdf.crs is None and self.source_epsg is not None:
                gdf = gdf.set_crs(self._normalize_crs(self.source_epsg))

            # If no CRS is present and no source EPSG was provided, this is a risk
            if gdf.crs is None:
                raise ValueError(
                    "Input vector file has no CRS and no source_epsg was provided. "
                    "Please specify source_epsg so that coordinates can be interpreted correctly."
                )

            # Ensure the requested z_column exists for later XYZ export
            if self.z_column not in gdf.columns:
                raise ValueError(
                    f"Requested z_column '{self.z_column}' not found in the input file."
                )

            return gdf

        # Case 2: assume XYZ-like text file, use io_xyz module
        # Build a simple XYZFormatSpec if none is provided
        if self.xyz_format_spec is None:
            xyz_spec = XYZFormatSpec(
                x_column=self.x_column,
                y_column=self.y_column,
                z_column=self.z_column,
            )
        else:
            xyz_spec = self.xyz_format_spec

        if self.source_epsg is None:
            raise ValueError(
                "source_epsg must be provided for XYZ text files "
                "so that the CRS can be correctly assigned."
            )

        # Load XYZ as GeoDataFrame with assigned CRS (no reprojection yet)
        gdf_xyz = load_xyz_as_geodataframe(
            file_path=self.input_path,
            format_spec=xyz_spec,
            crs=self._normalize_crs(self.source_epsg),
        )

        return gdf_xyz

    @staticmethod
    def _normalize_crs(crs: Union[int, str]) -> Union[int, str]:
        """
        Normalize CRS representation to a form accepted by GeoPandas.

        Parameters
        ----------
        crs : int or str
            EPSG code as integer or full CRS string.

        Returns
        -------
        int or str
            Normalized CRS representation.
        """
        # GeoPandas can handle both "EPSG:XXXX" and integer EPSG codes.
        # Here we keep the value as provided, only converting strings
        # that look like integers into integer EPSG codes.
        if isinstance(crs, str):
            # Try to convert plain numeric strings to int
            stripped = crs.strip().upper().replace("EPSG:", "")
            try:
                epsg_int = int(stripped)
                return epsg_int
            except ValueError:
                # Non-numeric string, return as is (e.g. PROJ4 or WKT)
                return crs
        return crs

    def reproject_to_epsg(self, target_epsg: int) -> None:
        """
        Reproject internal GeoDataFrame to a target EPSG code.

        Parameters
        ----------
        target_epsg : int
            Target EPSG code (e.g. 3116, 32617).
        """
        if self.gdf.crs is None:
            raise ValueError(
                "Source CRS is not defined. It must be set before reprojecting."
            )
        self.gdf = self.gdf.to_crs(epsg=target_epsg)

    def to_xyz(
        self,
        output_path: str,
        format_spec: Optional[XYZFormatSpec] = None,
        float_format: str = "%.3f",
        include_header: Optional[bool] = None,
    ) -> None:
        """
        Export current GeoDataFrame to a simple XYZ text file.

        Parameters
        ----------
        output_path : str
            Path to the output .xyz file.
        format_spec : XYZFormatSpec, optional
            Format specification describing delimiter, header and
            column names. If None, a simple default is created using
            self.x_column, self.y_column and self.z_column.
        float_format : str, optional
            Numeric format for floating-point values (e.g., '%.3f').
        include_header : bool, optional
            Whether to include a header row. If None, it follows
            `format_spec.has_header`.
        """
        # Use provided format specification or build a simple one
        if format_spec is None:
            format_spec = XYZFormatSpec(
                x_column=self.x_column,
                y_column=self.y_column,
                z_column=self.z_column,
            )

        # Ensure z_column exists in the GeoDataFrame before export
        if self.z_column not in self.gdf.columns:
            raise ValueError(
                f"GeoDataFrame does not contain the requested z column: '{self.z_column}'"
            )

        # Delegate XYZ writing to io_xyz helper
        save_xyz_from_geodataframe(
            gdf=self.gdf,
            file_path=output_path,
            format_spec=format_spec,
            z_column=self.z_column,
            float_format=float_format,
            include_header=include_header,
        )


def reproject_xyz_file(
    input_path: str,
    output_path: str,
    source_epsg: Union[int, str],
    target_epsg: Union[int, str],
    z_column: str = "z",
    xyz_format_spec: Optional[XYZFormatSpec] = None,
    float_format: str = "%.3f",
    include_header: Optional[bool] = None,
) -> None:
    """
    Convenience function to reproject an XYZ file from one CRS to another.

    Parameters
    ----------
    input_path : str
        Path to the input XYZ file.
    output_path : str
        Path to the output XYZ file.
    source_epsg : int or str
        EPSG code of the source CRS (e.g. 4326, "EPSG:4326").
    target_epsg : int or str
        EPSG code of the target CRS (e.g. 3116, "EPSG:3116").
    z_column : str, optional
        Name of the column containing elevation/depth values.
    xyz_format_spec : XYZFormatSpec, optional
        Format specification for reading/writing the XYZ file.
        If None, a default XYZFormatSpec is used.
    float_format : str, optional
        Numeric format for floating-point values in the output file.
    include_header : bool, optional
        Whether to include a header row in the output file. If None,
        it follows `xyz_format_spec.has_header`.

    Notes
    -----
    - This function is useful when you just want to transform an
      XYZ file between CRSs without manually handling GeoDataFrames.
    """
    # Normalize CRS representation
    def _normalize(crs_val: Union[int, str]) -> Union[int, str]:
        if isinstance(crs_val, str):
            stripped = crs_val.strip().upper().replace("EPSG:", "")
            try:
                epsg_int = int(stripped)
                return epsg_int
            except ValueError:
                return crs_val
        return crs_val

    src_crs = _normalize(source_epsg)
    tgt_crs = _normalize(target_epsg)

    # Use provided format spec or a default one
    if xyz_format_spec is None:
        xyz_format_spec = XYZFormatSpec(z_column=z_column)

    # Load XYZ as GeoDataFrame, assigning the source CRS
    gdf = load_xyz_as_geodataframe(
        file_path=input_path,
        format_spec=xyz_format_spec,
        crs=src_crs,
    )

    # Reproject to target CRS
    gdf_reprojected = gdf.to_crs(tgt_crs)

    # Save back to XYZ using the same format specification
    save_xyz_from_geodataframe(
        gdf=gdf_reprojected,
        file_path=output_path,
        format_spec=xyz_format_spec,
        z_column=z_column,
        float_format=float_format,
        include_header=include_header,
    )