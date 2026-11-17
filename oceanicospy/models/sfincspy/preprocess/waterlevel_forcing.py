import os
from typing import Optional

import pandas as pd
import geopandas as gpd
from hydromt_sfincs import SfincsModel, utils as hydromt_utils

from .... import utils as oceanicospy_utils
from ....utils.waterlevel import download_uhslc_waterlevel, load_uhslc_waterlevel
from ....analysis.harmonic_tides import tide_harmonic_decomposition


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

    Notes
    -----
    A single boundary point (``bndfile``) is created at the given
    coordinates; SFINCS applies its series to every water-level boundary
    cell (``msk == 2``).
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

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

    def _finalize(
        self,
        df: pd.DataFrame,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str,
        invalid_value: Optional[float],
    ) -> str:
        tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
        tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])

        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in the water-level data.")

        df = df[[column_name]].copy()
        df.columns = ["1"]  # boundary point number expected by SFINCS
        df.index.name = "time"

        df = df.loc[tstart:tstop]
        df = df.dropna()

        if invalid_value is not None:
            df = df[df["1"] != invalid_value]

        if df.empty:
            raise RuntimeError("The water-level series is empty after filtering.")

        out_path = os.path.join(self.model.root, out_filename)
        df.to_csv(out_path)

        pnts = gpd.points_from_xy([x_bnd], [y_bnd])
        bnd = gpd.GeoDataFrame(index=[1], geometry=pnts, crs=self.model.crs)

        self.model.setup_waterlevel_forcing(timeseries=df, locations=bnd)

        return out_path

    def from_dataframe(
        self,
        df: pd.DataFrame,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
    ) -> str:
        """
        Set the water-level boundary from a prepared DataFrame.

        The series must be in local time (the model times) and already
        datum-corrected. This is the method to use after
        :meth:`get_waterlevel_from_UHSLC` or :meth:`to_astronomical_tide`.

        Parameters
        ----------
        df : pandas.DataFrame
            Datetime index and a sea-level column (m).
        column_name : str
            Sea-level column.
        x_bnd, y_bnd : float
            Boundary point in the model CRS.
        out_filename : str, optional
            Copy of the clipped series written in the model folder
            (default ``"bzs.csv"``).
        invalid_value : float or None, optional
            Value marking invalid data (default the UHSLC sentinel
            ``-32.767``). ``None`` disables the filter.

        Returns
        -------
        str
            Path of the written copy.
        """
        return self._finalize(df, column_name, x_bnd, y_bnd, out_filename, invalid_value)

    def from_csv(
        self,
        csv_path: str,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
        utc_offset_hours: float = -5,
    ) -> str:
        """
        Set the water-level boundary from a CSV file in UTC.

        The time index is shifted by ``utc_offset_hours`` to local time, the
        convention used by the other forcings (e.g.
        :meth:`WindForcing.get_winds_from_ERA5`).

        Parameters
        ----------
        csv_path : str
            CSV with a datetime index in the first column.
        column_name : str
            Sea-level column.
        x_bnd, y_bnd : float
            Boundary point in the model CRS.
        out_filename : str, optional
            Copy of the clipped series written in the model folder.
        invalid_value : float or None, optional
            Value marking invalid data.
        utc_offset_hours : float, optional
            Offset of local time from UTC, in hours (default -5). Use 0 if
            the file is already in local time.

        Returns
        -------
        str
            Path of the written copy.
        """
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.index = df.index + pd.Timedelta(hours=utc_offset_hours)

        return self._finalize(df, column_name, x_bnd, y_bnd, out_filename, invalid_value)
