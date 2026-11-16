import shutil

import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
rasterio = pytest.importorskip("rasterio")

from hydromt_sfincs import SfincsModel  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

from oceanicospy.models.sfincspy.initializer import Initializer  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402


GRID_KWARGS = dict(
    x0=423966, y0=1389496, dx=15, dy=15, mmax=75, nmax=65, rotation=38, epsg=32617,
)


def _write_gradient_raster(path, low=-6.0, high=2.0):
    """North-up 3000x3000 m, 1 m/px raster covering the rotated test grid,
    with an elevation gradient from `low` (west) to `high` (east) so it
    straddles both zmin_active and zmax_bounds thresholds used below."""
    transform = from_origin(423000, 1391000, 1, 1)
    xx, _ = np.meshgrid(np.arange(3000), np.arange(3000))
    data = (low + (high - low) * (xx / 3000)).astype("float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=3000, width=3000, count=1,
        dtype="float32", crs="EPSG:32617", transform=transform, nodata=-9999,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def built_case(tmp_path):
    """A case with grid + a single 'topobathy' dataset registered through
    Initializer.write_data_catalog, ready for BathyMaker.setup_bathy()."""
    src_raster = tmp_path / "source_topobathy.tif"
    _write_gradient_raster(src_raster)

    case_root = tmp_path / "CasoTest"
    init = Initializer(str(case_root))
    init.create_folders()
    shutil.copy(src_raster, init.dict_folders["input"] + "topobathy.tif")

    catalog_path = init.write_data_catalog(
        {
            "topobathy": {
                "data_type": "RasterDataset",
                "driver": "raster",
                "path": "topobathy.tif",
                "crs": 32617,
                "nodata": -9999,
            }
        }
    )

    model = SfincsModel(data_libs=[catalog_path], root=init.dict_folders["run"], mode="w+")
    GridMaker(model).setup_grid(**GRID_KWARGS)

    return model, catalog_path, init


class TestSetupBathy:
    def test_default_single_dataset_matches_previous_behaviour(self, built_case):
        model, catalog_path, _ = built_case
        bathy = BathyMaker(model, catalog_path)
        bathy.setup_bathy(zmin_active=-4, zmax_bounds=-2)

        assert "dep" in model.grid.data_vars
        assert not np.isnan(model.grid["dep"].values).all()

    def test_active_and_boundary_cells_follow_thresholds(self, built_case):
        model, catalog_path, _ = built_case
        bathy = BathyMaker(model, catalog_path)
        bathy.setup_bathy(zmin_active=-4, zmax_bounds=-2)

        msk = model.grid["msk"].values
        dep = model.grid["dep"].values

        # msk==1 (active) cells must have elevation >= zmin_active
        active = msk == 1
        assert active.any()
        assert np.nanmin(dep[active]) >= -4

        # msk==2 (waterlevel boundary) cells must have elevation <= zmax_bounds
        boundary = msk == 2
        assert boundary.any()
        assert np.nanmax(dep[boundary]) <= -2

    def test_dep_can_be_plotted_on_grid_corners(self, built_case, tmp_path):
        model, catalog_path, _ = built_case
        BathyMaker(model, catalog_path).setup_bathy(zmin_active=-4, zmax_bounds=-2)

        matplotlib = pytest.importorskip("matplotlib")
        matplotlib.use("Agg")
        from oceanicospy.utils.plots import plot_field

        grid = GridMaker(model)
        grid.grid_info = dict(GRID_KWARGS)
        X, Y = grid.cell_corners()

        # dep lives in memory (model.grid); no model.write() is needed to plot it
        out = tmp_path / "dep.png"
        plot_field(X, Y, model.grid["dep"].values, output_path=out)
        assert out.is_file()
