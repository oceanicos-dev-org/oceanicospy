import glob
import os

import pandas as pd

from .ctd_base import CTDBase

class CastawayCTD(CTDBase):
    """
    Reader for CastAway CTD per-cast files (YSI/Xylem format).

    Handles per-cast CSV files that contain only a column header row and data
    rows (no embedded metadata block). Cast metadata — device ID, cast time,
    GPS coordinates, calibration dates, etc. — is read automatically from a
    multi-cast summary CSV located in the same directory, by matching the
    current file's stem against the ``File name`` column of the summary.

    Parameters
    ----------
    filepath : str
        Path to the per-cast CastAway CTD ``.csv`` file.

    Notes
    -----
    Expected per-cast file structure:

    - First row is the column header (no ``%`` metadata block).
    - Data columns: Pressure (Decibar), Depth (Meter), Temperature (Celsius),
      Conductivity (MicroSiemens per Centimeter), Specific conductance
      (MicroSiemens per Centimeter), Salinity (Practical Salinity Scale),
      Sound velocity (Meters per Second), Density (Kilograms per Cubic Meter).

    The summary file (auto-detected in the same directory) must have a
    ``File name`` column whose values match per-cast file stems, and cast time
    columns in Excel serial date format (days since 1899-12-30).

    The cleaned DataFrame is indexed by ``depth[m]``, reflecting the vertical
    profile nature of a CTD cast.

    24-Mar-2026 : Origination - Franklin Ayala
    """

    _COLUMN_MAP = {
        'Pressure (Decibar)': 'pressure[dbar]',
        'Depth (Meter)': 'depth[m]',
        'Temperature (Celsius)': 'temperature[C]',
        'Conductivity (MicroSiemens per Centimeter)': 'conductivity[uS/cm]',
        'Specific conductance (MicroSiemens per Centimeter)': 'specific_conductance[uS/cm]',
        'Salinity (Practical Salinity Scale)': 'salinity[PSS]',
        'Sound velocity (Meters per Second)': 'sound_velocity[m/s]',
        'Density (Kilograms per Cubic Meter)': 'density[kg/m3]',
    }

    _EXCEL_ORIGIN = pd.Timestamp('1899-12-30')

    @property
    def cast_time(self) -> pd.Timestamp:
        """
        UTC timestamp of the cast start, read from the summary file.

        Returns
        -------
        pandas.Timestamp
            Cast start time in UTC, or ``NaT`` if no matching row is found
            in the summary file.
        """
        serial = self.metadata.get('Cast time (UTC)')
        if serial is None:
            return pd.NaT
        return self._EXCEL_ORIGIN + pd.to_timedelta(float(serial), unit='D')

    def _parse_metadata(self) -> dict:
        """
        Read cast metadata from a multi-cast summary CSV in the same directory.

        Scans every CSV file in the same directory (excluding ``self.filepath``)
        for one that contains a ``File name`` column, then returns the row
        whose ``File name`` matches the stem of ``self.filepath``.

        Returns
        -------
        dict
            Metadata fields from the matching summary row (e.g., ``'Device'``,
            ``'Cast time (UTC)'``, ``'Start latitude'``,
            ``'Cast duration (Seconds)'``).  Returns an empty dict if no
            matching summary file or row is found.
        """
        directory = os.path.dirname(self.filepath)
        stem = os.path.splitext(os.path.basename(self.filepath))[0]

        for csv_path in glob.glob(os.path.join(directory, '*.csv')):
            if os.path.abspath(csv_path) == os.path.abspath(self.filepath):
                continue
            try:
                header = pd.read_csv(csv_path, nrows=0)
                if 'File name' not in header.columns:
                    continue
                summary = pd.read_csv(csv_path)
                match = summary[summary['File name'] == stem]
                if not match.empty:
                    return match.iloc[0].to_dict()
            except Exception:
                continue

        return {}

    def _load_raw_dataframe(self) -> pd.DataFrame:
        """
        Load the raw data block into a DataFrame, skipping metadata lines if any

        Returns
        -------
        pandas.DataFrame
            Raw DataFrame as read directly from the CSV file, including original
            column names and all data rows.
        """
        return pd.read_csv(self.filepath)

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename columns to ``variable[unit]`` convention and set depth index.

        Parameters
        ----------
        df : pandas.DataFrame
            Raw DataFrame as returned by ``_load_raw_dataframe``.

        Returns
        -------
        pandas.DataFrame
            DataFrame indexed by ``depth[m]`` with standardized column names.
        """
        df = df.rename(columns=self._COLUMN_MAP)
        df = df.set_index('depth[m]')
        return df
