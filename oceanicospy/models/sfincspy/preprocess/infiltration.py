from pathlib import Path
from typing import Optional, Union

import pandas as pd
import xarray as xr

from hydromt_sfincs import SfincsModel, workflows

__all__ = ["Infiltration"]


class Infiltration:
    """
    Infiltration setup for SFINCS models.

    Two mutually exclusive methods are supported; configuring one removes
    the other from the model:

    - **Curve Number** (``scsfile``): SCS-CN losses, stored as the
      potential maximum retention ``S = 1000 / CN - 10`` (inches). In
      SFINCS it only acts on the rainfall that falls on each cell.
      ``storecumprcp = 1`` is set, since SFINCS needs the cumulative
      rainfall to evaluate it.
    - **Constant rate** (``qinffile`` or scalar ``qinf``): a fixed
      infiltration capacity in mm/h (e.g. the saturated hydraulic
      conductivity). In SFINCS it acts on rainfall and on ponded water
      while the cell is wet.

    Both can be given as a uniform value, a raster, or a categorical
    land-cover raster plus a reclassification table. The land-cover raster
    and table can be built from polygons with
    :meth:`BottomFriction.rasterize_landcover`, so a single land-cover map
    serves both roughness and infiltration.

    Parameters
    ----------
    model : SfincsModel
        SFINCS model instance initialised with HydroMT. The grid and the
        active mask must already be set (see ``BathyMaker.setup_bathy``).

    Notes
    -----
    Cells without a value (raster nodata, or a land-cover class missing
    from the table) get no infiltration: CN 100 (``S = 0``) or a rate of
    0 mm/h.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    # --------------------------------------------------
    # Curve Number
    # --------------------------------------------------
    def setup_cn(
        self,
        cn: Union[float, str, Path, xr.DataArray],
        antecedent_moisture: Optional[str] = None,
    ) -> None:
        """
        Set up Curve Number infiltration from a uniform value or a raster.

        Parameters
        ----------
        cn : float, str, Path or xarray.DataArray
            Uniform Curve Number, or a gridded Curve Number dataset (data
            catalog name, file path or DataArray) passed to
            ``SfincsModel.setup_cn_infiltration``.
        antecedent_moisture : {'dry', 'avg', 'wet'}, optional
            Antecedent runoff condition, only for datasets with layers
            ``cn_dry``, ``cn_avg`` and ``cn_wet``. None (default) reads a
            single ``cn`` layer.

        Examples
        --------
        >>> infiltration = Infiltration(model)
        >>> infiltration.setup_cn(39)
        """
        self._remove_constant()
        if isinstance(cn, (int, float)):
            # HydroMT only reads CN from a dataset; a uniform value is
            # converted on the model grid with its own CN -> S workflow.
            msk = self.model.grid["msk"]
            da_cn = xr.full_like(msk, float(cn), dtype="float32")
            da_scs = workflows.cn_to_s(da_cn, msk > 0).round(3)
            self.model.set_grid(da_scs, name="scs")
            self.model.set_config("scsfile", "sfincs.scs")
        else:
            self.model.setup_cn_infiltration(cn=cn, antecedent_moisture=antecedent_moisture)
        self.model.set_config("storecumprcp", 1)

    def setup_cn_from_landcover(
        self,
        landcover: Union[str, Path],
        reclass_table: Union[str, Path],
        column: str = "cn",
    ) -> None:
        """
        Set up Curve Number infiltration from a land-cover raster.

        Parameters
        ----------
        landcover : str or Path
            Categorical land-cover raster (one integer class per cell), as a
            file path or data catalog name.
        reclass_table : str or Path
            CSV with the class id as first column (index) and the Curve
            Number in ``column``. It may hold other columns (e.g. Manning
            ``N`` or ``qinf``).
        column : str, optional
            Column of ``reclass_table`` with the Curve Number. Default is
            ``"cn"``.

        Examples
        --------
        >>> infiltration.setup_cn_from_landcover("landcover.tif", "reclass.csv")
        """
        da_cn = self._reclassify(landcover, reclass_table, column)
        self.setup_cn(da_cn)

    # --------------------------------------------------
    # Constant rate
    # --------------------------------------------------
    def setup_constant(self, qinf: Union[float, str, Path, xr.DataArray]) -> None:
        """
        Set up a constant infiltration rate from a uniform value or a raster.

        Parameters
        ----------
        qinf : float, str, Path or xarray.DataArray
            Uniform rate in mm/h (written as the scalar ``qinf`` of
            ``sfincs.inp``), or a gridded rate in mm/h (data catalog name,
            file path or DataArray) passed to
            ``SfincsModel.setup_constant_infiltration``.

        Notes
        -----
        The rate applies to every wet active cell, sea cells included. In
        coastal domains a uniform value therefore also removes water from
        the sea; use a raster or :meth:`setup_constant_from_landcover` with
        0 mm/h outside the pervious areas.

        Examples
        --------
        >>> infiltration = Infiltration(model)
        >>> infiltration.setup_constant(1.02)
        """
        self._remove_cn()
        if isinstance(qinf, (int, float)):
            self._drop_grid("qinf")
            self.model.config.pop("qinffile", None)
            self.model.set_config("qinf", float(qinf))
        else:
            self.model.setup_constant_infiltration(qinf=qinf)

    def setup_constant_from_landcover(
        self,
        landcover: Union[str, Path],
        reclass_table: Union[str, Path],
        column: str = "qinf",
    ) -> None:
        """
        Set up a constant infiltration rate from a land-cover raster.

        Parameters
        ----------
        landcover : str or Path
            Categorical land-cover raster (one integer class per cell), as a
            file path or data catalog name.
        reclass_table : str or Path
            CSV with the class id as first column (index) and the rate in
            mm/h in ``column``. It may hold other columns.
        column : str, optional
            Column of ``reclass_table`` with the rate. Default is
            ``"qinf"``.

        Examples
        --------
        >>> infiltration.setup_constant_from_landcover("landcover.tif", "reclass.csv")
        """
        da_qinf = self._reclassify(landcover, reclass_table, column).fillna(0.0)
        self.setup_constant(da_qinf)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _reclassify(
        self,
        landcover: Union[str, Path],
        reclass_table: Union[str, Path],
        column: str,
    ) -> xr.DataArray:
        table = pd.read_csv(reclass_table, index_col=0)
        if column not in table.columns:
            raise KeyError(f"Column '{column}' not found in {reclass_table}.")
        da_lc = self.model.data_catalog.get_rasterdataset(
            str(landcover), bbox=self.model.bbox, buffer=10
        )
        # float values, so unmatched classes can be NaN (a CN column may be read as int)
        da = da_lc.raster.reclassify(table[[column]].astype("float32"))[column]
        return da.raster.mask_nodata()

    def _drop_grid(self, name: str) -> None:
        # HydroMT writes every map present in the grid and re-adds its
        # "<name>file" key, so removing the config key alone is not enough.
        if name in self.model.grid:
            self.model._grid = self.model.grid.drop_vars(name)

    def _remove_cn(self) -> None:
        self._drop_grid("scs")
        self.model.config.pop("scsfile", None)

    def _remove_constant(self) -> None:
        self._drop_grid("qinf")
        self.model.config.pop("qinffile", None)
        self.model.config.pop("qinf", None)
