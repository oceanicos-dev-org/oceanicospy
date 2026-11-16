from hydromt_sfincs import SfincsModel

from .gridmaker import GridMaker
from .bathymaker import BathyMaker
from .bottom_friction import BottomFriction
from .waterlevel_forcing import WaterLevelForcing
from .waves_forcing import WavesForcing
from .wind_forcing import WindForcing
from .meteo_forcing import UniformMetForcingClassic
from .discharge_forcing import DischargeForcing


class SfincsCaseBuilder:
    """
    Entry point to build a SFINCS case.

    Creates one ``SfincsModel`` and exposes each preprocessing module bound
    to it (``grid``, ``bathy``, ``friction``, ``waterlevel``, ``waves``,
    ``wind``, ``meteo``, ``discharge``). The case script calls them
    explicitly and in order, so every input of a run stays traceable; there
    is no single method that builds the whole case from a dictionary.

    Parameters
    ----------
    root : str
        Folder where the SFINCS model is written (usually the case ``run/``
        folder created by :class:`~oceanicospy.models.sfincspy.Initializer`).
    data_catalog : str, optional
        Path to the case ``data_catalog.yml`` (see
        :meth:`~oceanicospy.models.sfincspy.Initializer.write_data_catalog`).
    mode : str, optional
        HydroMT model mode.

    Attributes
    ----------
    model : SfincsModel
        Model shared by all the modules below.
    grid : GridMaker
    bathy : BathyMaker
    friction : BottomFriction
    waterlevel : WaterLevelForcing
    waves : WavesForcing
    wind : WindForcing
    meteo : UniformMetForcingClassic
    discharge : DischargeForcing

    Examples
    --------
    >>> builder = SfincsCaseBuilder(root="case/run", data_catalog="case/input/data_catalog.yml")
    >>> builder.setup_time(tref="20250618 000000", tstart="20250618 000000", tstop="20250626 230000")
    >>> builder.grid.setup_grid(x0=x0, y0=y0, dx=1, dy=1, mmax=mmax, nmax=nmax, rotation=38, epsg=32617)
    >>> builder.bathy.setup_bathy(zmin_active=-4, zmax_bounds=-2)
    >>> builder.friction.setup_uniform(manning_land=0.04, manning_sea=0.02)
    >>> builder.waterlevel.from_dataframe(df_tide, column_name="depth[m]", x_bnd=x_bnd, y_bnd=y_bnd)
    >>> builder.waves.from_xbeach(nc_path="xbeach_output.nc", point_index=0)
    >>> builder.wind.from_era5_nc(nc_path=local_era5_nc)
    >>> builder.meteo.from_dataframe(df_rain, precip_col="rain[mm]")
    >>> builder.write()
    """

    def __init__(
        self,
        root: str,
        data_catalog: str = "data_catalog.yml",
        mode: str = "w+",
    ) -> None:
        self.root = root
        self.data_catalog = data_catalog

        self.model = SfincsModel(
            data_libs=[data_catalog],
            root=root,
            mode=mode,
        )

        self.grid = GridMaker(self.model)
        self.bathy = BathyMaker(self.model, data_catalog)
        self.friction = BottomFriction(self.model)
        self.waterlevel = WaterLevelForcing(self.model)
        self.waves = WavesForcing(self.model)
        self.wind = WindForcing(self.model)
        self.meteo = UniformMetForcingClassic(self.model)
        self.discharge = DischargeForcing(self.model)

    def setup_time(self, tref: str, tstart: str, tstop: str) -> None:
        """
        Set the model reference, start and stop times.

        Call it before any forcing: they all read ``tref``, ``tstart`` and
        ``tstop`` from ``model.config``.

        Parameters
        ----------
        tref, tstart, tstop : str
            Times as ``"YYYYMMDD HHMMSS"``.
        """
        self.model.setup_config(tref=tref, tstart=tstart, tstop=tstop)

    def write(self) -> None:
        """
        Write all SFINCS input files to ``root``.

        Notes
        -----
        ``sfincs.dis`` is rewritten with six decimals. HydroMT-SFINCS writes
        it with ``%7.2f`` by default (0.01 m3/s resolution), which rounds
        small discharges to zero and loses volume at small sources and sinks.
        """
        self.model.write()
        # forcing["dis"] holds the series; "discharge" is the group name
        # write_forcing expects in data_vars
        if "dis" in self.model.forcing:
            self.model.write_forcing(data_vars=["discharge"], fmt="%12.6f")
        self.model.write_config()
