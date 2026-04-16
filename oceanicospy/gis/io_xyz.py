"""
io_xyz
======
Low-level I/O utilities for XYZ-format point files.

An XYZ file is a plain-text table whose columns represent X (easting),
Y (northing) and Z (elevation or depth) coordinates, one point per row.
Columns may be separated by spaces, tabs, commas or semicolons, and the
file may or may not carry a header row.

This module is intentionally free of CRS logic. Reprojection and
spatial operations belong in ``crs_tools`` and ``xyz_tile`` respectively.

Public API
----------
XYZFormatSpec
    Dataclass that describes the on-disk layout of an XYZ file.
infer_xyz_format
    Automatically detect the format of an XYZ file from a sample of lines.
read_xyz
    Read an XYZ file into a :class:`pandas.DataFrame`.
write_xyz
    Write a :class:`pandas.DataFrame` to an XYZ file.
load_xyz_as_geodataframe
    Read an XYZ file and return a :class:`geopandas.GeoDataFrame`.
save_xyz_from_geodataframe
    Write a :class:`geopandas.GeoDataFrame` to an XYZ file.

Notes
-----
The private helper ``_normalize_epsg`` is also imported by ``crs_tools``
to ensure consistent CRS string handling across the subpackage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

try:
    import geopandas as gpd
    from shapely.geometry import Point  # noqa: F401 – used implicitly by gpd
    _HAS_GEO = True
except ImportError:
    gpd = None  # type: ignore[assignment]
    _HAS_GEO = False

__all__ = [
    "XYZFormatSpec",
    "infer_xyz_format",
    "read_xyz",
    "write_xyz",
    "load_xyz_as_geodataframe",
    "save_xyz_from_geodataframe",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Delimiters tried during format inference, in evaluation order.
_CANDIDATE_DELIMITERS: List[str] = [",", ";", "\t", "|"]

#: Prefix characters that identify comment lines (skipped during inference).
_COMMENT_PREFIXES: tuple[str, ...] = ("#", "//")


# ---------------------------------------------------------------------------
# XYZFormatSpec
# ---------------------------------------------------------------------------

@dataclass
class XYZFormatSpec:
    """
    Descriptor for the on-disk layout of an XYZ point file.

    All reading and writing functions in this module accept an
    ``XYZFormatSpec`` so that format details are declared once and
    reused consistently across I/O calls.

    Parameters
    ----------
    delimiter : str, optional
        Column separator character.  Use ``" "`` for any whitespace
        (the default), ``","`` for CSV, ``";"`` for semicolon-separated
        files, or ``"\\t"`` for tab-separated files.
    has_header : bool, optional
        ``True`` if the first non-comment line contains column names.
        ``False`` (the default) if the file starts directly with data.
    x_column : str, optional
        Name of the column that stores the X coordinate.
    y_column : str, optional
        Name of the column that stores the Y coordinate.
    z_column : str, optional
        Name of the column that stores the Z value (elevation or depth).
    encoding : str, optional
        File encoding passed to :func:`open` and :func:`pandas.read_csv`.
    """

    delimiter: str = " "
    has_header: bool = False
    x_column: str = "x"
    y_column: str = "y"
    z_column: str = "z"
    encoding: str = "utf-8"

    def column_order(self) -> List[str]:
        """
        Return ``[x_column, y_column, z_column]`` in write order.

        Returns
        -------
        list of str
            The three coordinate column names in the canonical x→y→z order
            used by :func:`write_xyz`.
        """
        return [self.x_column, self.y_column, self.z_column]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_float_token(token: str) -> bool:
    """
    Return ``True`` if *token* can be interpreted as a floating-point number.

    Parameters
    ----------
    token : str
        A single whitespace-stripped token from a line of text.

    Returns
    -------
    bool
    """
    try:
        float(token)
        return True
    except ValueError:
        return False


def _check_geodeps(func_name: str) -> None:
    """
    Raise :exc:`ImportError` when GeoPandas is not available.

    Parameters
    ----------
    func_name : str
        Name of the calling function, used in the error message.

    Raises
    ------
    ImportError
        If ``geopandas`` or ``shapely`` could not be imported at module load.
    """
    if not _HAS_GEO:
        raise ImportError(
            f"{func_name} requires 'geopandas' and 'shapely'. "
            "Install them with:  pip install geopandas shapely"
        )


def _normalize_epsg(crs: Union[str, int]) -> str:
    """
    Normalize a CRS value to a canonical ``"EPSG:XXXX"`` string.

    Accepts integer EPSG codes and string representations in any of the
    forms ``4326``, ``"4326"``, ``"EPSG:4326"`` or ``"epsg:4326"``.
    The returned string is always upper-case and accepted by both
    GeoPandas and pyproj.

    This helper is also imported by ``crs_tools`` so that CRS
    normalization is handled in a single place across the subpackage.

    Parameters
    ----------
    crs : str or int
        EPSG code to normalize.

    Returns
    -------
    str
        Canonical ``"EPSG:XXXX"`` string.

    Raises
    ------
    ValueError
        If *crs* is a string that cannot be interpreted as an EPSG code.
    """
    if isinstance(crs, int):
        return f"EPSG:{crs}"

    cleaned = crs.strip().upper()
    if cleaned.startswith("EPSG:"):
        return cleaned

    try:
        return f"EPSG:{int(cleaned)}"
    except ValueError:
        raise ValueError(
            f"Cannot interpret '{crs}' as an EPSG code. "
            "Expected an integer or a string like '4326' or 'EPSG:4326'."
        )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def infer_xyz_format(
    file_path: Union[str, Path],
    sample_size: int = 50,
) -> XYZFormatSpec:
    """
    Automatically detect the format of an XYZ file from a sample of lines.

    The function reads up to *sample_size* non-empty, non-comment lines
    and attempts to detect:

    * The column delimiter (comma, semicolon, tab, pipe, or whitespace).
    * Whether the first data line is a header or numeric data.
    * Column names when a header row is detected.

    When the detection is inconclusive the function returns the default
    :class:`XYZFormatSpec` (space-delimited, no header, columns ``x/y/z``).

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the XYZ-like text file.
    sample_size : int, optional
        Maximum number of lines to read during detection.  The default
        of 50 is sufficient for typical oceanographic point files.

    Returns
    -------
    XYZFormatSpec
        Detected format specification.

    Notes
    -----
    This function is intentionally conservative.  When in doubt it
    returns safe defaults rather than an incorrect guess.  Pass an
    explicit :class:`XYZFormatSpec` to :func:`read_xyz` whenever the
    file format is known in advance.
    """
    sample_lines: List[str] = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(_COMMENT_PREFIXES):
                continue
            sample_lines.append(stripped)
            if len(sample_lines) >= sample_size:
                break

    if not sample_lines:
        return XYZFormatSpec()

    # --- delimiter detection ------------------------------------------------
    delim_scores: Dict[str, int] = {d: 0 for d in _CANDIDATE_DELIMITERS}
    for line in sample_lines:
        for delim in _CANDIDATE_DELIMITERS:
            delim_scores[delim] += line.count(delim)

    best_delim = max(_CANDIDATE_DELIMITERS, key=lambda d: delim_scores[d])
    delimiter = best_delim if delim_scores[best_delim] > 0 else " "

    # --- header detection ---------------------------------------------------
    first_line = sample_lines[0]
    tokens = first_line.split() if delimiter == " " else first_line.split(delimiter)
    has_header = any(not _is_float_token(tok) for tok in tokens)

    if has_header:
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

    return XYZFormatSpec(delimiter=delimiter, has_header=False)


def read_xyz(
    file_path: Union[str, Path],
    format_spec: Optional[XYZFormatSpec] = None,
    dtype: Optional[Dict[str, type]] = None,
    usecols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Read an XYZ point file into a :class:`pandas.DataFrame`.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the input XYZ file.
    format_spec : XYZFormatSpec, optional
        Layout descriptor.  When ``None``, the format is detected
        automatically via :func:`infer_xyz_format`.
    dtype : dict of {str: type}, optional
        Column-to-dtype mapping forwarded to :func:`pandas.read_csv`.
        Useful to enforce ``float32`` on large files.
    usecols : list of str, optional
        Subset of column names to load.  All other columns are discarded.

    Returns
    -------
    pandas.DataFrame
        DataFrame with at least the ``x``, ``y`` and ``z`` columns
        defined in *format_spec* (or in the detected spec).

    Notes
    -----
    This function performs no CRS handling; it loads raw numeric values.
    To obtain a spatial object use :func:`load_xyz_as_geodataframe`.
    """
    if format_spec is None:
        format_spec = infer_xyz_format(file_path)

    header = 0 if format_spec.has_header else None
    names = None if format_spec.has_header else format_spec.column_order()

    return pd.read_csv(
        file_path,
        sep=format_spec.delimiter,
        header=header,
        names=names,
        dtype=dtype,
        usecols=usecols,
        encoding=format_spec.encoding,
        engine="python",
    )


def write_xyz(
    df: pd.DataFrame,
    file_path: Union[str, Path],
    format_spec: Optional[XYZFormatSpec] = None,
    float_format: str = "%.3f",
    include_header: Optional[bool] = None,
) -> None:
    """
    Write a :class:`pandas.DataFrame` to an XYZ plain-text file.

    Parameters
    ----------
    df : pandas.DataFrame
        Source data.  Must contain the columns declared in *format_spec*.
    file_path : str or pathlib.Path
        Destination file path.  The file is created or overwritten.
    format_spec : XYZFormatSpec, optional
        Layout descriptor.  Defaults to :class:`XYZFormatSpec` (space-
        delimited, no header, columns ``x/y/z``).
    float_format : str, optional
        ``printf``-style format string applied to all floating-point
        values (e.g. ``"%.3f"`` for three decimal places).
    include_header : bool, optional
        Override whether a header row is written.  When ``None`` (the
        default) the value is taken from ``format_spec.has_header``.

    Raises
    ------
    ValueError
        If any column declared in *format_spec* is absent from *df*.

    Notes
    -----
    This function writes exactly the three coordinate columns in
    ``x → y → z`` order.  Additional columns present in *df* are ignored.
    """
    if format_spec is None:
        format_spec = XYZFormatSpec()

    if include_header is None:
        include_header = format_spec.has_header

    missing = [c for c in format_spec.column_order() if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame is missing the following columns required by "
            f"XYZFormatSpec: {missing}"
        )

    df[format_spec.column_order()].to_csv(
        file_path,
        sep=format_spec.delimiter,
        header=include_header,
        index=False,
        float_format=float_format,
        encoding=format_spec.encoding,
    )


def load_xyz_as_geodataframe(
    file_path: Union[str, Path],
    format_spec: Optional[XYZFormatSpec] = None,
    crs: Optional[Union[str, int]] = None,
) -> "gpd.GeoDataFrame":
    """
    Read an XYZ file and return a :class:`geopandas.GeoDataFrame`.

    The X and Y columns are used to build :class:`shapely.geometry.Point`
    geometries.  The Z column is retained as a regular attribute column.
    No reprojection is performed; *crs* is assigned as metadata only.

    Parameters
    ----------
    file_path : str or pathlib.Path
        Path to the input XYZ file.
    format_spec : XYZFormatSpec, optional
        Layout descriptor.  When ``None``, the format is detected
        automatically.
    crs : str or int, optional
        CRS to assign to the GeoDataFrame, e.g. ``"EPSG:4326"`` or
        ``4326``.  Both string and integer EPSG codes are accepted.
        When ``None`` the GeoDataFrame is created without a CRS.

    Returns
    -------
    geopandas.GeoDataFrame
        Point GeoDataFrame with the geometry column built from X and Y.

    Raises
    ------
    ImportError
        If ``geopandas`` or ``shapely`` are not installed.

    Notes
    -----
    To reproject the data after loading, use
    :meth:`geopandas.GeoDataFrame.to_crs` or the helpers in
    ``crs_tools``.
    """
    _check_geodeps("load_xyz_as_geodataframe")

    if format_spec is None:
        format_spec = infer_xyz_format(file_path)

    df = read_xyz(file_path, format_spec=format_spec)

    crs_value = _normalize_epsg(crs) if crs is not None else None

    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[format_spec.x_column], df[format_spec.y_column]),
        crs=crs_value,
    )


def save_xyz_from_geodataframe(
    gdf: "gpd.GeoDataFrame",
    file_path: Union[str, Path],
    format_spec: Optional[XYZFormatSpec] = None,
    z_column: str = "z",
    float_format: str = "%.3f",
    include_header: Optional[bool] = None,
) -> None:
    """
    Write a :class:`geopandas.GeoDataFrame` to an XYZ plain-text file.

    Coordinates are extracted from the ``geometry`` column (X and Y) and
    from *z_column* (Z).  This function is the symmetric counterpart of
    :func:`load_xyz_as_geodataframe`.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Source GeoDataFrame.  Must contain Point geometries and the
        column named *z_column*.
    file_path : str or pathlib.Path
        Destination file path.  The file is created or overwritten.
    format_spec : XYZFormatSpec, optional
        Layout descriptor.  Defaults to :class:`XYZFormatSpec` (space-
        delimited, no header, columns ``x/y/z``).
    z_column : str, optional
        Name of the attribute column that holds elevation or depth values.
    float_format : str, optional
        ``printf``-style format string for floating-point values.
    include_header : bool, optional
        Override whether a header row is written.  When ``None`` the
        value is taken from ``format_spec.has_header``.

    Raises
    ------
    ImportError
        If ``geopandas`` or ``shapely`` are not installed.
    ValueError
        If *z_column* is not present in *gdf*.
    """
    _check_geodeps("save_xyz_from_geodataframe")

    if format_spec is None:
        format_spec = XYZFormatSpec()

    if z_column not in gdf.columns:
        raise ValueError(
            f"Column '{z_column}' not found in GeoDataFrame. "
            f"Available columns: {list(gdf.columns)}"
        )

    df = pd.DataFrame({
        format_spec.x_column: gdf.geometry.x,
        format_spec.y_column: gdf.geometry.y,
        format_spec.z_column: gdf[z_column].to_numpy(),
    })

    write_xyz(
        df,
        file_path,
        format_spec=format_spec,
        float_format=float_format,
        include_header=include_header,
    )