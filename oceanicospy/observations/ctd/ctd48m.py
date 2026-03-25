import pandas as pd

from .ctd_base import CTDBase


class CTD48M(CTDBase):
    """
    Reader for Sea-Sun Marine Technology CTD48M per-cast files.

    Handles CSV files with a ``%``-prefixed metadata header followed by
    a column header row and per-sample depth-profile data. Metadata fields
    such as device ID, cast time, GPS coordinates, cast duration, sampling
    rate, and calibration dates are parsed automatically from the file header.

    Parameters
    ----------
    filepath : str
        Path to the CTD48M ``.csv`` file.

    Notes
    -----
    Expected file structure:

    - Lines beginning with ``%`` contain metadata as ``% Key,Value`` pairs.
    - An empty ``% `` line acts as a separator before the data block.
    - The first non-``%`` line is the column header row.
    - Data columns: Pressure (Decibar), Depth (Meter), Temperature (Celsius),
      Conductivity (MicroSiemens per Centimeter), Specific conductance
      (MicroSiemens per Centimeter), Salinity (Practical Salinity Scale),
      Sound velocity (Meters per Second), Density (Kilograms per Cubic Meter).

    The cleaned DataFrame is indexed by ``depth[m]``, reflecting the vertical
    profile nature of a CTD cast. Columns follow the ``variable[unit]``
    convention (e.g., ``temperature[C]``, ``salinity[PSS]``).

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

    @property
    def cast_time(self) -> pd.Timestamp:
        """
        UTC timestamp of the cast start, read from file metadata.

        Returns
        -------
        pandas.Timestamp
            Cast start time in UTC, or ``NaT`` if not present in metadata.
        """
        return pd.to_datetime(self.metadata.get('Cast time (UTC)'))

    def _parse_metadata(self) -> dict:
        """
        Parse ``%``-prefixed header lines into a metadata dictionary.

        Reads all lines beginning with ``%`` and extracts key-value pairs
        separated by the first comma. Lines with no comma (e.g., the empty
        separator ``% ``) are skipped.

        Returns
        -------
        dict
            Keys and values extracted from ``% Key,Value`` header lines.
            Example keys: ``'Device'``, ``'Cast time (UTC)'``,
            ``'Start latitude'``, ``'Conductivity calibration date'``.
        """
        metadata = {}
        with open(self.filepath, 'r') as f:
            for line in f:
                if not line.startswith('%'):
                    break
                content = line[1:].strip()
                if ',' in content:
                    key, value = content.split(',', 1)
                    metadata[key.strip()] = value.strip()
        return metadata

    def _load_raw_dataframe(self) -> pd.DataFrame:
        """
        Read the data block (after the ``%`` metadata header) into a DataFrame.

        Counts the number of ``%``-prefixed lines and skips them before
        reading the CSV data block.

        Returns
        -------
        pandas.DataFrame
            Raw per-sample records with original column names as exported
            by the CTD48M instrument.
        """
        with open(self.filepath, 'r') as f:
            header_lines = sum(1 for line in f if line.startswith('%'))
        return pd.read_csv(self.filepath, skiprows=header_lines)

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
