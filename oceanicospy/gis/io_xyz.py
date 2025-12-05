from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Union

import pandas as pd

try:
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError:
    gpd = None
    Point = None


@dataclass
class XYZFormatSpec:
    """
    Specification of a simple XYZ file format.

    This class describes how XYZ data is stored on disk so that
    reading and writing functions can be configured in a consistent way.
    """
    delimiter: str = " "
    has_header: bool = False
    x_column: str = "x"
    y_column: str = "y"
    z_column: str = "z"
    encoding: str = "utf-8"

    def column_order(self) -> List[str]:
        """
        Return the expected column order for writing.

        Notes
        -----
        This helper method is mainly intended for write_xyz, which
        usually writes x, y, z in that specific order.
        """
        return [self.x_column, self.y_column, self.z_column]


def _is_float_token(token: str) -> bool:
    """
    Check whether a string token can be interpreted as a float.

    Parameters
    ----------
    token : str
        String token to test.

    Returns
    -------
    bool
        True if token can be cast to float, False otherwise.
    """
    try:
        float(token)
        return True
    except ValueError:
        return False


def infer_xyz_format(
    file_path: str,
    sample_size: int = 50
) -> XYZFormatSpec:
    """
    Infer a basic XYZ file format from a sample of lines.

    Parameters
    ----------
    file_path : str
        Path to the XYZ-like text file.
    sample_size : int, optional
        Maximum number of lines to inspect when guessing the format.

    Returns
    -------
    XYZFormatSpec
        A format specification with guessed delimiter, header usage
        and column names.

    Notes
    -----
    - This function is intentionally simple and conservative.
    - It tries to detect:
      * Delimiter (comma, semicolon, tab or whitespace).
      * Whether the first non-empty line is header or data.
      * Column names if a header row is detected.
    - If the heuristic is inconclusive, defaults are used
      (space delimiter, no header, columns x/y/z).
    """
    lines: List[str] = []

    # Read a limited number of non-empty, non-comment lines
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            lines.append(stripped)
            if len(lines) >= sample_size:
                break

    # If file seems empty or only comments, return defaults
    if not lines:
        return XYZFormatSpec()

    # Detect delimiter among comma, semicolon and tab.
    # If none is clearly present, assume whitespace.
    candidate_delims = [",", ";", "\t"]
    delim_scores = {d: 0 for d in candidate_delims}

    for line in lines:
        for d in candidate_delims:
            delim_scores[d] += line.count(d)

    best_delim = max(candidate_delims, key=lambda d: delim_scores[d])
    if delim_scores[best_delim] == 0:
        # No clear comma/semicolon/tab detected → assume whitespace
        delimiter = " "
    else:
        delimiter = best_delim

    # Use the first non-empty line to detect header
    first_line = lines[0]
    if delimiter == " ":
        tokens = first_line.split()
    else:
        tokens = first_line.split(delimiter)

    # Decide header vs data: if any token is non-numeric, treat as header
    has_header = any(not _is_float_token(tok) for tok in tokens)

    if has_header:
        # Use tokens as column names (at least x, y, z)
        x_col = tokens[0] if len(tokens) > 0 else "x"
        y_col = tokens[1] if len(tokens) > 1 else "y"
        z_col = tokens[2] if len(tokens) > 2 else "z"
        return XYZFormatSpec(
            delimiter=delimiter,
            has_header=True,
            x_column=x_col,
            y_column=y_col,
            z_column=z_col,
        )

    # If we reach this point, assume basic numeric data without header
    return XYZFormatSpec(
        delimiter=delimiter,
        has_header=False,
        x_column="x",
        y_column="y",
        z_column="z",
    )


def read_xyz(
    file_path: str,
    format_spec: Optional[XYZFormatSpec] = None,
    dtype: Optional[dict] = None,
    usecols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Read XYZ-like point data from a text file into a DataFrame.

    Parameters
    ----------
    file_path : str
        Path to the input XYZ file.
    format_spec : XYZFormatSpec, optional
        Format specification describing delimiter, header and column
        names. If None, `infer_xyz_format` will be called first.
    dtype : dict, optional
        Optional mapping of column names to expected dtypes to pass
        to `pandas.read_csv`.
    usecols : list of str, optional
        Optional subset of columns to load.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing at least the x, y, z columns as defined
        in the format specification.

    Notes
    -----
    - This function is the main entry point for loading XYZ files
      within the gis subpackage.
    - Higher-level classes (e.g. `XYZTile`) can wrap this function.
    - No CRS handling is performed here; it is only raw numerical data.
    """
    # If no format specification is provided, infer it from the file
    if format_spec is None:
        format_spec = infer_xyz_format(file_path)

    # Configure header and column names according to the format spec
    if format_spec.has_header:
        header = 0
        names = None
    else:
        header = None
        names = format_spec.column_order()

    # Use pandas.read_csv for flexible parsing
    df = pd.read_csv(
        file_path,
        sep=format_spec.delimiter,
        header=header,
        names=names,
        dtype=dtype,
        usecols=usecols,
        encoding=format_spec.encoding,
        engine="python",
    )

    return df


def write_xyz(
    df: pd.DataFrame,
    file_path: str,
    format_spec: Optional[XYZFormatSpec] = None,
    float_format: str = "%.3f",
    include_header: Optional[bool] = None
) -> None:
    """
    Write a DataFrame with x, y, z columns to an XYZ text file.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame containing coordinate and elevation/depth
        columns.
    file_path : str
        Output file path where the XYZ text file will be written.
    format_spec : XYZFormatSpec, optional
        Format specification describing delimiter, header and column
        names. If None, a default `XYZFormatSpec` is used.
    float_format : str, optional
        Numeric format for floating-point values (e.g., '%.3f').
    include_header : bool, optional
        Whether to include column names as a header line. If None,
        the value is derived from `format_spec.has_header`.

    Notes
    -----
    - This function assumes that df already contains the columns
      specified in `format_spec.x_column`, `format_spec.y_column`,
      and `format_spec.z_column`.
    - It does not perform CRS or unit conversions; it simply writes
      numeric values to disk.
    """
    # Use provided format specification or create a default one
    if format_spec is None:
        format_spec = XYZFormatSpec()

    # Decide whether to include header based on the format spec
    if include_header is None:
        include_header = format_spec.has_header

    # Ensure required columns exist in the DataFrame
    missing_cols = [
        col for col in format_spec.column_order() if col not in df.columns
    ]
    if missing_cols:
        raise ValueError(
            f"Missing required columns in DataFrame for XYZ writing: {missing_cols}"
        )

    # Select columns in the specified order
    out_df = df[format_spec.column_order()]

    # Write to disk using pandas.to_csv
    out_df.to_csv(
        file_path,
        sep=format_spec.delimiter,
        header=include_header,
        index=False,
        float_format=float_format,
        encoding=format_spec.encoding,
    )


def load_xyz_as_geodataframe(
    file_path: str,
    format_spec: Optional[XYZFormatSpec] = None,
    crs: Optional[Union[str, int]] = None
) -> "gpd.GeoDataFrame":
    """
    Load an XYZ file into a GeoDataFrame with Point geometries.

    Parameters
    ----------
    file_path : str
        Path to the input XYZ file.
    format_spec : XYZFormatSpec, optional
        Format specification used by `read_xyz`. If None, the format
        is inferred.
    crs : str or int, optional
        Coordinate reference system to assign to the GeoDataFrame
        (e.g., 'EPSG:3116' or 3116). This does not reproject data;
        it only sets the CRS metadata.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with geometry column (Point) created from x, y.

    Raises
    ------
    ImportError
        If `geopandas` or `shapely` are not available.

    Notes
    -----
    - This function is a light wrapper around `read_xyz` plus
      `GeoDataFrame` construction.
    - Reprojection should be done outside this module (e.g. using
      functions from `crs.py`).
    """
    if gpd is None or Point is None:
        raise ImportError(
            "geopandas and shapely are required to use load_xyz_as_geodataframe."
        )

    # Ensure we have a format specification for the XYZ file
    if format_spec is None:
        format_spec = infer_xyz_format(file_path)

    # Load raw data as DataFrame
    df = read_xyz(file_path, format_spec=format_spec)

    # Build geometry from x and y columns
    geometry = gpd.points_from_xy(
        df[format_spec.x_column],
        df[format_spec.y_column],
    )

    # Normalize CRS input: allow int EPSG or string
    crs_meta = crs
    if isinstance(crs, int):
        crs_meta = f"EPSG:{crs}"

    # Create GeoDataFrame with assigned CRS (no reprojection)
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=crs_meta)

    return gdf


def save_xyz_from_geodataframe(
    gdf: "gpd.GeoDataFrame",
    file_path: str,
    format_spec: Optional[XYZFormatSpec] = None,
    z_column: str = "z",
    float_format: str = "%.3f",
    include_header: Optional[bool] = None
) -> None:
    """
    Save a GeoDataFrame with Point geometries to an XYZ file.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame containing point geometries and a scalar z column.
    file_path : str
        Output file path where the XYZ text file will be written.
    format_spec : XYZFormatSpec, optional
        Format specification describing delimiter, header and column
        names. If None, a default `XYZFormatSpec` is used.
    z_column : str, optional
        Name of the column containing elevation/depth values.
    float_format : str, optional
        Numeric format for floating-point values.
    include_header : bool, optional
        Whether to include a header row. If None, it will follow
        `format_spec.has_header`.

    Notes
    -----
    - This function is symmetric to `load_xyz_as_geodataframe`, but
      it writes data back to an XYZ-style file.
    - It assumes planar coordinates (x, y) are stored in the geometry.
    """
    if gpd is None or Point is None:
        raise ImportError(
            "geopandas and shapely are required to use save_xyz_from_geodataframe."
        )

    if format_spec is None:
        format_spec = XYZFormatSpec()

    # Ensure the z column exists
    if z_column not in gdf.columns:
        raise ValueError(
            f"GeoDataFrame does not contain the requested z column: '{z_column}'"
        )

    # Build a plain DataFrame with x, y, z from geometry and attribute
    df = pd.DataFrame({
        format_spec.x_column: gdf.geometry.x,
        format_spec.y_column: gdf.geometry.y,
        format_spec.z_column: gdf[z_column].values,
    })

    # Delegate actual writing to write_xyz
    write_xyz(
        df=df,
        file_path=file_path,
        format_spec=format_spec,
        float_format=float_format,
        include_header=include_header,
    )
