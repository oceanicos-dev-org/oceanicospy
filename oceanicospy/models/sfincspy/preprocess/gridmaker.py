from typing import Any, Dict, Tuple

import numpy as np

from hydromt_sfincs import SfincsModel

from oceanicospy.utils.plots import cell_corners


class GridMaker:
    """
    Builder of the regular computational grid of a SFINCS model.

    Delegates the grid construction to HydroMT-SFINCS
    (``SfincsModel.setup_grid``) and keeps the parameters used, so the grid
    geometry can be recovered later (e.g. for plotting).

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.

    Attributes
    ----------
    grid_info : dict
        Grid parameters: ``x0, y0, dx, dy, nmax, mmax, rotation, epsg``.

    Notes
    -----
    - Regular grid (no quadtree). For a coarse grid with the fine
      topography in subgrid tables, see ``BathyMaker.setup_subgrid``.
    - ``x0``/``y0`` are the grid origin (corner of the first cell), not the
      centre of the first cell, following the HydroMT-SFINCS convention.
    - ``mmax`` is the number of cells along the local **x** axis (paired
      with ``dx``) and ``nmax`` the number along the local **y** axis
      (paired with ``dy``).
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model
        self.grid_info: Dict[str, Any] = {}

    def setup_grid(self, **grid_kwargs) -> Dict[str, Any]:
        """
        Set up the SFINCS model grid.

        Parameters
        ----------
        **grid_kwargs : dict
            Grid parameters, passed unchanged to ``SfincsModel.setup_grid``:

            - x0, y0 : float — grid origin (m, projected CRS).
            - dx, dy : float — cell size along x/y (m).
            - mmax : int — number of cells along **x**.
            - nmax : int — number of cells along **y**.
            - rotation : float — counter-clockwise rotation from the x/east
              axis (degrees).
            - epsg : int — EPSG code of the coordinate reference system.

        Returns
        -------
        dict
            Grid parameters (also stored in :attr:`grid_info`).

        Notes
        -----
        HydroMT-SFINCS recommends keeping the number of active cells in the
        order of ~3 million. ``mmax * nmax`` is the total number of cells
        before masking, so a warning is printed if it exceeds that order of
        magnitude; it is not a hard limit.

        Examples
        --------
        >>> grid = GridMaker(model)
        >>> grid.setup_grid(
        ...     x0=423966, y0=1389496,
        ...     dx=15, dy=15,
        ...     mmax=75, nmax=65,
        ...     rotation=38, epsg=32617,
        ... )
        """
        mmax = grid_kwargs.get("mmax")
        nmax = grid_kwargs.get("nmax")
        if mmax is not None and nmax is not None and mmax * nmax > 3_000_000:
            print(
                f"[GridMaker] Warning: mmax*nmax = {mmax * nmax:,} cells. "
                "HydroMT-SFINCS recommends keeping the number of active "
                "cells in the order of ~3 million."
            )

        self.model.setup_grid(**grid_kwargs)

        self.grid_info = {
            "x0": grid_kwargs.get("x0"),
            "y0": grid_kwargs.get("y0"),
            "dx": grid_kwargs.get("dx"),
            "dy": grid_kwargs.get("dy"),
            "nmax": nmax,
            "mmax": mmax,
            "rotation": grid_kwargs.get("rotation"),
            "epsg": grid_kwargs.get("epsg"),
        }
        return self.grid_info

    def cell_corners(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Return the corner coordinates of the grid cells, rotation included.

        Returns
        -------
        X, Y : numpy.ndarray
            Arrays of shape ``(nmax + 1, mmax + 1)`` in the model CRS, ready
            for :func:`oceanicospy.utils.plots.plot_grid` and
            :func:`oceanicospy.utils.plots.plot_field`.

        Raises
        ------
        RuntimeError
            If :meth:`setup_grid` has not been called.

        Examples
        --------
        >>> from oceanicospy.utils.plots import plot_field
        >>> X, Y = grid.cell_corners()
        >>> plot_field(X, Y, model.grid["dep"].values, label="z [m]")
        """
        if not self.grid_info:
            raise RuntimeError("Grid not set up. Call setup_grid() first.")

        info = self.grid_info
        return cell_corners(
            info["x0"], info["y0"], info["dx"], info["dy"],
            nx=info["mmax"], ny=info["nmax"], rotation=info["rotation"] or 0.0,
        )
