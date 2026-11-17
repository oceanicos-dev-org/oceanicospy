from pathlib import Path
from typing import Tuple, Union

import numpy as np
import xarray as xr
from hydromt_sfincs import SfincsModel, utils

from oceanicospy.utils.plots import cell_corners

__all__ = ["SfincsOutputReader"]

#: Fill value SFINCS writes in its NetCDF output (``sfincs_ncoutput.F90``)
FILL_VALUE = -99999.0


class SfincsOutputReader:
    """
    Reader for the NetCDF output of a regular-grid SFINCS run.

    Parameters
    ----------
    root : str or Path
        Run folder with ``sfincs.inp``, the grid files and the output
        (``sfincs_map.nc``, ``sfincs_his.nc``).

    Attributes
    ----------
    model : SfincsModel
        The model read from ``root`` (configuration and grid).

    Notes
    -----
    Map variables are returned on the model grid with dimensions
    ``(time | timemax, y, x)``, the cell-centre coordinates ``xc``/``yc`` and
    the cell area. Fill values are set to NaN.

    Examples
    --------
    >>> reader = SfincsOutputReader("case/run")
    >>> ds = reader.read_map()
    >>> X, Y = reader.cell_corners()
    """

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root)
        self.model = SfincsModel(root=str(self.root), mode="r")
        self.model.read_config()
        self.model.read_grid()

    def read_map(self, filename: str = "sfincs_map.nc") -> xr.Dataset:
        """
        Read the map output (``sfincs_map.nc``).

        Parameters
        ----------
        filename : str, optional
            Name of the map file in ``root``.

        Returns
        -------
        xarray.Dataset
            Cell variables (e.g. ``zb``, ``zs``, ``h``, ``hmax``, ``zsmax``,
            ``vmax``, ``tmax``, ``cumprcp``, ``cuminf``) with a
            ``cell_area`` coordinate (m²).
        """
        ds, _ = utils.read_sfincs_map_results(self.root / filename, ds_like=self.model.grid)
        ds = ds.load()
        for var in ds.data_vars:
            if np.issubdtype(ds[var].dtype, np.floating):
                ds[var] = ds[var].where(np.abs(ds[var]) < abs(FILL_VALUE) - 1)
        t = self.model.reggrid.transform
        area = abs(t.a * t.e - t.b * t.d)
        ds = ds.assign_coords(cell_area=(("y", "x"), np.full(ds.raster.shape, area)))
        return ds

    def read_his(self, filename: str = "sfincs_his.nc") -> xr.Dataset:
        """
        Read the point output (``sfincs_his.nc``).

        Returns
        -------
        xarray.Dataset
            Point series (e.g. ``point_zs``, ``point_h``) with a station
            dimension named after the observation points.
        """
        return utils.read_sfincs_his_results(self.root / filename, crs=self.model.crs).load()

    def cell_corners(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Corner coordinates of the grid cells, for
        :func:`oceanicospy.utils.plots.plot_field`.
        """
        c = self.model.config
        return cell_corners(
            float(c["x0"]), float(c["y0"]), float(c["dx"]), float(c["dy"]),
            nx=int(c["mmax"]), ny=int(c["nmax"]), rotation=float(c.get("rotation", 0.0)),
        )
