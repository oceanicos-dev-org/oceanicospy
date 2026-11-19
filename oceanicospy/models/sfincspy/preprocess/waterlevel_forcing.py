import os
import warnings
from typing import Dict, Hashable, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from hydromt_sfincs import SfincsModel, utils as hydromt_utils

from .... import utils as oceanicospy_utils
from ....utils.waterlevel import download_uhslc_waterlevel, load_uhslc_waterlevel
from ....analysis.harmonic_tides import tide_harmonic_decomposition


# Buffer (m) HydroMT uses to clip boundary points to the boundary cells.
BOUNDARY_BUFFER = 5e3
# Warn when a point is farther than this many cells from the boundary cells.
FAR_POINT_CELLS = 10
# Warn when more than this fraction of the times is dropped.
DROPPED_ROWS_WARNING = 0.05


class WaterLevelForcing:
    """
    Water-level boundary forcing (``bzsfile``) for SFINCS.

    Follows ``xbeachpy.preprocess.WaterLevelForcing``: the class gets or
    reads the data and writes them in the format SFINCS needs. **No datum
    correction is applied**; any station-specific correction is applied in
    the case script, on the DataFrame returned by
    :meth:`get_waterlevel_from_UHSLC`, before :meth:`from_dataframe`.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.

    Attributes
    ----------
    point_ids : dict
        ``{column: number}`` of the boundary points of the last call, in the
        order of ``bndfile`` and the ``bzsfile`` columns.

    Notes
    -----
    One or more boundary points (``bndfile``) can be given. SFINCS sets
    the level at each water-level boundary cell (``msk == 2``) from the two
    nearest points, weighted by inverse distance; with a single point,
    every boundary cell gets its series.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model
        self.point_ids: Dict[Hashable, int] = {}

    def get_waterlevel_from_UHSLC(
        self,
        station_id,
        input_dir: str,
        override: bool = False,
    ) -> pd.DataFrame:
        """
        Get raw UHSLC sea-level data, downloading only when needed.

        Uses the shared downloader (``oceanicospy.utils.waterlevel``), so the
        raw file (``h<station_id>.csv``) and the returned DataFrame are the
        same as in ``xbeachpy`` for the same station.

        Parameters
        ----------
        station_id : str or int
            UHSLC station code.
        input_dir : str
            Case ``input/`` folder, where ``h<station_id>.csv`` is saved or
            looked for.
        override : bool, optional
            Download again even if the file exists.

        Returns
        -------
        pandas.DataFrame
            Raw series with a local-time index and a ``depth[m]`` column,
            without datum correction.
        """
        filepath = f"{input_dir}h{station_id}.csv"
        file_exists = oceanicospy_utils.verify_file(filepath)

        if not file_exists or override:
            tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
            tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])
            return download_uhslc_waterlevel(station_id, tstart, tstop, filepath)

        print("\t UHSLC water level data already exists, skipping download")
        return load_uhslc_waterlevel(station_id, filepath)

    def to_astronomical_tide(
        self,
        df: pd.DataFrame,
        column_name: str,
        lat: float,
        method: str = "ols",
        out_column: str = "tide[m]",
        min_plausible_value: Optional[float] = -10.0,
    ) -> pd.DataFrame:
        """
        Reconstruct the astronomical tide of a sea-level series by harmonic
        analysis (UTide), removing the meteorological residual.

        Useful for runs that must exclude the coastal surge of the event,
        e.g. a rainfall-only run in a compound-flooding experiment, where
        the observed total level would bring in the storm surge of that
        date.

        The fit uses the **whole** series in ``df``, which should be the
        long multi-year record, not only the event window, to get robust
        constituents. Apply any datum correction to ``df`` before calling
        this method: an uncorrected datum jump would bias the fit.

        Parameters
        ----------
        df : pandas.DataFrame
            Sea-level series with a datetime index, datum-corrected.
        column_name : str
            Sea-level column in ``df``.
        lat : float
            Station latitude (degrees), required by UTide.
        method : str, optional
            UTide regression method (see
            :func:`oceanicospy.analysis.harmonic_tides.tide_harmonic_decomposition`).
            Default ``"ols"``.
        out_column : str, optional
            Name of the output column. Default ``"tide[m]"``.
        min_plausible_value : float or None, optional
            Values at or below this level (m) are discarded before the fit.
            It removes missing-data sentinels (UHSLC uses e.g. ``-32.767``)
            even after a datum shift, which would otherwise make UTide
            diverge. ``None`` disables the filter.

        Returns
        -------
        pandas.DataFrame
            Datetime index and the reconstructed tide in ``out_column``,
            ready for :meth:`from_dataframe`.

        Raises
        ------
        ValueError
            If ``column_name`` is not in ``df``, or no values are left after
            removing missing values.
        """
        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in df.")

        valid = df[column_name].dropna()
        if min_plausible_value is not None:
            valid = valid[valid > min_plausible_value]
        if valid.empty:
            raise ValueError("No values left after removing missing values.")

        serie_table, _ = tide_harmonic_decomposition(
            data=valid, time=valid.index, lat=lat, method=method, conf_int="none",
        )
        return (
            serie_table.set_index("time")[["tide"]]
            .rename(columns={"tide": out_column})
        )

    def _resolve_locations(
        self,
        column_name: Optional[str],
        x_bnd: Optional[float],
        y_bnd: Optional[float],
        locations: Optional[Mapping[Hashable, Tuple[float, float]]],
    ) -> Dict[Hashable, Tuple[float, float]]:
        """Return the boundary points as ``{column: (x, y)}``, in order."""
        single = (column_name, x_bnd, y_bnd)
        if locations is None:
            if any(value is None for value in single):
                raise ValueError(
                    "Give either column_name with x_bnd and y_bnd, or locations."
                )
            locations = {column_name: (x_bnd, y_bnd)}
        elif any(value is not None for value in single):
            raise ValueError(
                "Give either column_name with x_bnd and y_bnd, or locations, not both."
            )

        if not isinstance(locations, Mapping) or len(locations) == 0:
            raise ValueError("locations must be a non-empty dict {column: (x, y)}.")

        points = {}
        for name, xy in locations.items():
            try:
                x, y = (float(value) for value in xy)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Location '{name}' must be an (x, y) pair of numbers."
                ) from None
            if not (np.isfinite(x) and np.isfinite(y)):
                raise ValueError(f"Location '{name}' has non-finite coordinates.")
            points[name] = (x, y)

        coords = list(points.values())
        duplicated = [name for name, xy in points.items() if coords.count(xy) > 1]
        if duplicated:
            raise ValueError(f"Locations with the same coordinates: {duplicated}.")

        return points

    def _prepare_series(
        self,
        df: pd.DataFrame,
        names: List[Hashable],
        invalid_value: Optional[float],
    ) -> pd.DataFrame:
        """Select, clip to the model window and filter the boundary series."""
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("The water-level data must have a datetime index.")

        missing = [name for name in names if name not in df.columns]
        if missing:
            raise ValueError(f"Columns not found in the water-level data: {missing}.")

        try:
            df = df[names].apply(pd.to_numeric)
        except (TypeError, ValueError):
            raise ValueError("The water-level columns must be numeric.") from None

        df = df.sort_index()
        if df.index.has_duplicates:
            raise ValueError("The water-level data have repeated times.")
        df.index.name = "time"

        tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
        tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])
        df = df.loc[tstart:tstop]
        if df.empty:
            raise RuntimeError("The water-level data do not overlap tstart-tstop.")

        # A row is kept only if every point is valid, so all points share
        # the same times in the bzs file.
        invalid = df.isna().any(axis=1)
        if invalid_value is not None:
            invalid |= pd.Series(
                np.isclose(df.to_numpy(dtype=float), invalid_value).any(axis=1),
                index=df.index,
            )

        n_rows = len(df)
        df = df[~invalid]
        if df.empty:
            raise RuntimeError("The water-level series is empty after filtering.")

        dropped = int(invalid.sum())
        if dropped / n_rows > DROPPED_ROWS_WARNING:
            warnings.warn(
                f"{dropped} of {n_rows} water-level times ({dropped / n_rows:.0%}) "
                "were dropped for missing or invalid values; SFINCS interpolates "
                "linearly over the gaps.",
                stacklevel=4,
            )

        return df

    def _check_distances(self, points: Dict[Hashable, Tuple[float, float]]) -> None:
        """Check that HydroMT will keep every point and warn on far points.

        HydroMT clips the points to the water-level boundary cells
        (``msk == 2``) plus a buffer and drops the rest without notice; the
        missing columns are then filled with zeros.
        """
        mask = self.model.mask
        has_boundary = mask is not None and bool(np.any(mask == 2))
        if has_boundary:
            region = mask.where(mask == 2, 0).raster.vectorize()
        else:
            region = self.model.region
            warnings.warn(
                "The model has no water-level boundary cells (msk == 2); "
                "SFINCS will not apply this boundary.",
                stacklevel=4,
            )

        geoms = region.to_crs(self.model.crs).geometry
        target = geoms.union_all() if hasattr(geoms, "union_all") else geoms.unary_union

        cell_size = max(
            abs(float(self.model.config.get("dx", 0))),
            abs(float(self.model.config.get("dy", 0))),
        )

        far = []
        for name, (x, y) in points.items():
            distance = Point(x, y).distance(target)
            if distance > BOUNDARY_BUFFER:
                raise ValueError(
                    f"Boundary point '{name}' is {distance:.0f} m from the "
                    f"water-level boundary cells (limit {BOUNDARY_BUFFER:.0f} m); "
                    "HydroMT would drop it."
                )
            if has_boundary and cell_size > 0 and distance > FAR_POINT_CELLS * cell_size:
                far.append(f"'{name}' ({distance:.0f} m)")

        if far:
            warnings.warn(
                f"Boundary points more than {FAR_POINT_CELLS} cells from the "
                f"water-level boundary cells: {', '.join(far)}.",
                stacklevel=4,
            )

    def _finalize(
        self,
        df: pd.DataFrame,
        column_name: Optional[str],
        x_bnd: Optional[float],
        y_bnd: Optional[float],
        locations: Optional[Mapping[Hashable, Tuple[float, float]]],
        out_filename: str,
        invalid_value: Optional[float],
    ) -> str:
        # Validate everything before writing anything.
        points = self._resolve_locations(column_name, x_bnd, y_bnd, locations)
        names = list(points)
        df = self._prepare_series(df, names, invalid_value)
        self._check_distances(points)

        point_ids = {name: i for i, name in enumerate(names, start=1)}

        out_path = os.path.join(self.model.root, out_filename)
        df.to_csv(out_path)

        # HydroMT needs integer point numbers as columns and index.
        timeseries = df.rename(columns=point_ids)
        xs, ys = zip(*points.values())
        bnd = gpd.GeoDataFrame(
            index=list(point_ids.values()),
            geometry=gpd.points_from_xy(xs, ys),
            crs=self.model.crs,
        )

        # merge=False: each call replaces the whole boundary.
        self.model.setup_waterlevel_forcing(
            timeseries=timeseries, locations=bnd, buffer=BOUNDARY_BUFFER, merge=False,
        )
        self.point_ids = point_ids

        return out_path

    def from_dataframe(
        self,
        df: pd.DataFrame,
        column_name: Optional[str] = None,
        x_bnd: Optional[float] = None,
        y_bnd: Optional[float] = None,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
        locations: Optional[Mapping[Hashable, Tuple[float, float]]] = None,
    ) -> str:
        """
        Set the water-level boundary from a prepared DataFrame.

        The series must be in local time (the model times) and already
        datum-corrected. This is the method to use after
        :meth:`get_waterlevel_from_UHSLC` or :meth:`to_astronomical_tide`.

        Give either one point (``column_name``, ``x_bnd``, ``y_bnd``) or
        several points (``locations``). Each call replaces the whole
        boundary; to combine sources, join their series in one DataFrame
        first.

        Parameters
        ----------
        df : pandas.DataFrame
            Datetime index and one sea-level column (m) per boundary point.
            Extra columns are ignored.
        column_name : str, optional
            Sea-level column for a single boundary point.
        x_bnd, y_bnd : float, optional
            Single boundary point in the model CRS.
        out_filename : str, optional
            Copy of the clipped series written in the model folder
            (default ``"bzs.csv"``), with one column per point named as in
            ``df``.
        invalid_value : float or None, optional
            Value marking invalid data (default the UHSLC sentinel
            ``-32.767``). ``None`` disables the filter.
        locations : dict, optional
            ``{column: (x, y)}`` in the model CRS, one entry per boundary
            point. Points are numbered 1, 2, ... in dict order; the mapping
            is kept in :attr:`point_ids`.

        Returns
        -------
        str
            Path of the written copy.

        Raises
        ------
        ValueError
            If both or neither point specifications are given, a column is
            missing or not numeric, coordinates are invalid or repeated, the
            index has repeated times, or a point is farther than 5 km from
            the water-level boundary cells (HydroMT would drop it).
        TypeError
            If the index is not a datetime index.
        RuntimeError
            If no data are left within ``tstart``-``tstop`` after filtering.

        Warns
        -----
        UserWarning
            If more than 5 % of the times are dropped, a point is more than
            10 cells from the boundary cells, or the model has no boundary
            cells (``msk == 2``).

        Notes
        -----
        A time is dropped for all points when any point is missing or
        invalid, so every point shares the same times.

        Examples
        --------
        Three points along the boundary, with the wave setup scaled by the
        local wave height at each point:

        >>> locations = {
        ...     "west": (302500.0, 1986160.0),
        ...     "centre": (310500.0, 1986500.0),
        ...     "east": (316000.0, 1986880.0),
        ... }
        >>> df_bnd = pd.DataFrame(
        ...     {name: tide_surge + slr + gamma * hs[name] * shape for name in locations},
        ...     index=time,
        ... )
        >>> builder.waterlevel.from_dataframe(df_bnd, locations=locations)
        >>> builder.waterlevel.point_ids
        {'west': 1, 'centre': 2, 'east': 3}
        """
        return self._finalize(
            df, column_name, x_bnd, y_bnd, locations, out_filename, invalid_value,
        )

    def from_csv(
        self,
        csv_path: str,
        column_name: Optional[str] = None,
        x_bnd: Optional[float] = None,
        y_bnd: Optional[float] = None,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
        utc_offset_hours: float = -5,
        locations: Optional[Mapping[Hashable, Tuple[float, float]]] = None,
    ) -> str:
        """
        Set the water-level boundary from a CSV file in UTC.

        The time index is shifted by ``utc_offset_hours`` to local time, the
        convention used by the other forcings (e.g.
        :meth:`WindForcing.get_winds_from_ERA5`). Points are given as in
        :meth:`from_dataframe`.

        Parameters
        ----------
        csv_path : str
            CSV with a datetime index in the first column and one sea-level
            column per boundary point.
        column_name : str, optional
            Sea-level column for a single boundary point.
        x_bnd, y_bnd : float, optional
            Single boundary point in the model CRS.
        out_filename : str, optional
            Copy of the clipped series written in the model folder.
        invalid_value : float or None, optional
            Value marking invalid data.
        utc_offset_hours : float, optional
            Offset of local time from UTC, in hours (default -5). Use 0 if
            the file is already in local time.
        locations : dict, optional
            ``{column: (x, y)}`` in the model CRS, one entry per boundary
            point.

        Returns
        -------
        str
            Path of the written copy.
        """
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.index = df.index + pd.Timedelta(hours=utc_offset_hours)

        return self._finalize(
            df, column_name, x_bnd, y_bnd, locations, out_filename, invalid_value,
        )
