from typing import Any, Dict, List, Optional

from hydromt_sfincs import SfincsModel


class BathyMaker:
    """
    Topobathymetry and mask setup for SFINCS models.

    Builds the elevation raster (``dep``), optionally merging several
    topobathymetric datasets with the native HydroMT-SFINCS merge rules, and
    defines the active cells (``msk == 1``) and the boundary cells
    (``msk == 2`` or ``3``). The datasets are read from a HydroMT
    ``data_catalog``.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT.
    data_catalog : str
        Path to the ``data_catalog.yml`` file defining the datasets
        (e.g. topography and bathymetry).

    Notes
    -----
    - ``dep`` holds elevations (positive on land, negative at sea).
    - ``msk`` values: 0 inactive, 1 active, 2 water-level boundary,
      3 outflow boundary.
    - The resulting rasters live in ``model.grid`` and can be plotted with
      :func:`oceanicospy.utils.plots.plot_field` together with
      ``GridMaker.cell_corners``.
    """

    def __init__(self, model: SfincsModel, data_catalog: str) -> None:
        self.model = model
        self.data_catalog = data_catalog

    def setup_bathy(
        self,
        datasets_dep: Optional[List[Dict[str, Any]]] = None,
        zmin_active: float = -4,
        zmax_bounds: float = -2,
        btype: str = "waterlevel",
        mask: Optional[str] = None,
        drop_area: float = 0.0,
        reset_mask: bool = True,
        reset_bounds: bool = True,
    ) -> None:
        """
        Set up the topobathymetry and masks of the SFINCS model.

        Runs, in order: elevation raster (``dep``), active cells and
        hydraulic boundary cells.

        Parameters
        ----------
        datasets_dep : list of dict, optional
            Topobathymetric datasets to merge, in the format expected by
            ``SfincsModel.setup_dep``: each entry is a dict with the key
            ``"elevtn"`` (dataset name in the ``data_catalog``) and,
            optionally, merge arguments such as ``zmin``, ``zmax``,
            ``offset``, ``merge_method`` or ``reproj_method`` (see
            :py:func:`hydromt.workflows.merge_multi_dataarrays`). For
            example, to give priority to a fine survey over a coarser
            filler DEM::

                [
                    {"elevtn": "topobathy_fine"},
                    {"elevtn": "topobathy_coarse", "merge_method": "first"},
                ]

            Defaults to a single dataset named ``"topobathy"``.
        zmin_active : float, optional
            Minimum elevation (m) of active cells; cells at or above this
            value are active. Default is -4.
        zmax_bounds : float, optional
            Maximum elevation (m) of the boundary cells. The SFINCS manual
            recommends placing the offshore boundary around the swash zone,
            roughly 2 m deep, hence the default of -2.
        btype : str, optional
            Boundary type, ``"waterlevel"`` (default) or ``"outflow"``.
        mask : str, optional
            Domain polygon (name of a ``GeoDataFrame`` in the
            ``data_catalog`` or path to a vector file). Only cells inside it
            can be active; outside it the model is inactive and its land
            edges are closed. If None, the whole grid rectangle is a
            candidate.
        drop_area : float, optional
            Maximum area (km²) of isolated active regions to discard (e.g.
            small cays or shoals that would otherwise remain as active
            islands with their own boundary). Default is 0.0 (none).
        reset_mask : bool, optional
            If True (default), reset the existing active mask.
        reset_bounds : bool, optional
            If True (default), reset existing boundaries of type ``btype``
            before setting the new ones.

        Returns
        -------
        None

        Notes
        -----
        Every dataset referenced in ``datasets_dep`` must be defined in the
        ``data_catalog`` (see ``Initializer.write_data_catalog``).

        Examples
        --------
        >>> bathy = BathyMaker(model, "data_catalog.yml")
        >>> bathy.setup_bathy(zmin_active=-5, zmax_bounds=-2)
        """
        if datasets_dep is None:
            datasets_dep = [{"elevtn": "topobathy"}]

        self.model.setup_dep(datasets_dep=datasets_dep)

        self.model.setup_mask_active(
            mask=mask,
            zmin=zmin_active,
            drop_area=drop_area,
            reset_mask=reset_mask,
        )

        self.model.setup_mask_bounds(
            btype=btype,
            zmax=zmax_bounds,
            reset_bounds=reset_bounds,
        )
