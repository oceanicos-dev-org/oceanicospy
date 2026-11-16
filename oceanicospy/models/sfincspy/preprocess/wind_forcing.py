import os
from pathlib import Path

import xarray as xr
import rioxarray  # noqa: F401  (registers the .rio accessor)
from rasterio.enums import Resampling
from pyproj import CRS
from hydromt_sfincs import SfincsModel, utils as hydromt_utils

from .... import utils as oceanicospy_utils
from ....utils.wind import download_era5_winds


class WindForcing:
    """
    Spatially varying wind forcing for SFINCS from ERA5.

    ERA5 is downloaded with the shared downloader (``oceanicospy.utils.wind``)
    and shifted to local time, as in ``xbeachpy.preprocess.WindForcing``, so
    the forcing is aligned with ``tstart``/``tstop``.

    Parameters
    ----------
    model : SfincsModel
        HydroMT-SFINCS model the forcing is added to.

    Notes
    -----
    :meth:`from_era5_nc` registers the wind field in ``model.forcing`` as
    ``wind10_u``/``wind10_v``; the file is written by ``model.write()``,
    which maps them to the variables SFINCS reads from the
    ``netamuamvfile`` (``eastward_wind``/``northward_wind``) and encodes the
    time as minutes since ``tref``.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    def get_winds_from_ERA5(
        self,
        wind_info: dict,
        input_dir: str,
        utc_offset_hours: float = -5,
        filename: str = "winds_era5.nc",
        override: bool = False,
    ) -> str:
        """
        Download ERA5 winds for the model period and shift them to local time.

        Parameters
        ----------
        wind_info : dict
            Download window with keys ``lon_ll_corner_wind``,
            ``lat_ll_corner_wind``, ``nx_wind``, ``ny_wind``, ``dx_wind`` and
            ``dy_wind`` (same keys as in ``xbeachpy``).
        input_dir : str
            Folder where the raw (UTC) and local-time NetCDF files are saved.
        utc_offset_hours : float, optional
            Offset of local time from UTC, in hours.
        filename : str, optional
            Name of the raw (UTC) file.
        override : bool, optional
            Download again even if the raw file already exists.

        Returns
        -------
        str
            Path of the local-time file (``<filename stem>_localtime.nc``),
            ready for :meth:`from_era5_nc`.
        """
        tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
        tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])

        filepath = Path(f"{input_dir}{filename}")
        localtime_path = filepath.with_name(filepath.stem + "_localtime" + filepath.suffix)

        if not oceanicospy_utils.verify_file(str(filepath)) or override:
            download_era5_winds(
                wind_info, tstart, tstop, utc_offset_hours,
                str(filepath), format_localtime=True,
            )
            print("\t ERA5 wind data downloaded and shifted to local time")
        else:
            print("\t ERA5 wind data already exists, skipping download")

        return str(localtime_path)

    def from_era5_nc(
        self,
        nc_path: str,
        u_var: str = "u10",
        v_var: str = "v10",
        out_filename: str = "wind_era5.nc",
        buffer_cells: int = 2,
    ) -> str:
        """
        Add a 2D wind forcing (``netamuamvfile``) from an ERA5 NetCDF file in
        local time.

        The winds are reprojected to the model CRS and kept on that regular
        grid, clipped to the rectangle around the model domain plus
        ``buffer_cells`` cells on each side. SFINCS interpolates this grid
        bilinearly at every cell centre, so it works for rotated and
        non-rotated model grids alike.

        Parameters
        ----------
        nc_path : str
            ERA5 NetCDF file in local time (see :meth:`get_winds_from_ERA5`).
        u_var, v_var : str, optional
            Names of the eastward and northward 10 m wind variables.
        out_filename : str, optional
            Name of the ``netamuamvfile`` written by ``model.write()``.
        buffer_cells : int, optional
            Wind-grid cells kept around the model domain.

        Returns
        -------
        str
            Path the file will have once ``model.write()`` is called; this
            method only registers the forcing.

        Raises
        ------
        KeyError
            If ``u_var`` or ``v_var`` is not in the dataset.
        ValueError
            If the wind grid does not cover the model domain plus
            ``buffer_cells``.

        Notes
        -----
        SFINCS reads the ``netamuamvfile`` as a rectilinear grid with
        increasing ``x`` and ``y`` and places value ``i`` at
        ``x[i] + dx / 2`` (``sfincs_meteo.f90``). The coordinates are written
        accordingly: increasing, in metres of the model CRS, and shifted half
        a cell.

        Examples
        --------
        >>> wind = WindForcing(model)
        >>> local_nc = wind.get_winds_from_ERA5(wind_info, input_dir="input/")
        >>> wind.from_era5_nc(local_nc)
        """
        tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
        tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])

        ds = xr.open_dataset(nc_path)
        if "valid_time" in ds.dims:
            ds = ds.rename({"valid_time": "time"})
        if u_var not in ds or v_var not in ds:
            raise KeyError(f"Variables '{u_var}' and/or '{v_var}' not found in {nc_path}")

        ds = ds[[u_var, v_var]].sel(time=slice(tstart, tstop))
        for dim in ["expver", "number"]:
            if dim in ds.dims:
                ds = ds.isel({dim: 0}).drop_vars(dim)
            if dim in ds.coords:
                ds = ds.drop_vars(dim)
        if "longitude" in ds.coords and float(ds.longitude.max()) > 180:
            ds = ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180).sortby("longitude")

        # regular grid in the model CRS, clipped around the domain
        epsg_model = int(self.model.config["epsg"])
        ds_utm = ds.rio.write_crs("EPSG:4326", inplace=False).rio.reproject(
            CRS.from_epsg(epsg_model), resampling=Resampling.bilinear,
        )
        ds_utm = ds_utm.sortby("x").sortby("y")
        dx = float(ds_utm["x"].values[1] - ds_utm["x"].values[0])
        dy = float(ds_utm["y"].values[1] - ds_utm["y"].values[0])
        xmin, ymin, xmax, ymax = self.model.region.to_crs(epsg_model).total_bounds
        ds_utm = ds_utm.sel(
            x=slice(xmin - buffer_cells * dx, xmax + buffer_cells * dx),
            y=slice(ymin - buffer_cells * dy, ymax + buffer_cells * dy),
        )
        if ds_utm.sizes["x"] < 2 or ds_utm.sizes["y"] < 2:
            raise ValueError("The wind grid does not cover the model domain with at least 2x2 points")
        if bool(ds_utm[u_var].isnull().any()) or bool(ds_utm[v_var].isnull().any()):
            raise ValueError(
                f"NaN winds around the model domain: {nc_path} does not cover the "
                f"domain plus {buffer_cells} buffer cells"
            )

        # HydroMT-SFINCS names, and the SFINCS coordinate convention
        ds_utm = ds_utm.rename({u_var: "wind10_u", v_var: "wind10_v"})
        ds_utm = ds_utm.assign_coords(
            x=("x", ds_utm["x"].values - dx / 2.0),
            y=("y", ds_utm["y"].values - dy / 2.0),
        )
        ds_utm["x"].attrs["units"] = "m"
        ds_utm["y"].attrs["units"] = "m"
        ds_utm = ds_utm.transpose("time", "y", "x")
        for var in ["wind10_u", "wind10_v"]:
            ds_utm[var] = ds_utm[var].astype("float32")
            ds_utm[var].attrs["units"] = "m s-1"

        # set the file name before write_forcing() picks a default one
        self.model.set_config("netamuamvfile", out_filename)
        self.model.set_forcing(ds_utm, split_dataset=True)
        return os.path.join(self.model.root, out_filename)
