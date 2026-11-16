from pathlib import Path

import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from hydromt_sfincs import SfincsModel  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import box  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bottom_friction import BottomFriction  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.infiltration import Infiltration  # noqa: E402


GRID_KWARGS = dict(
    x0=423966, y0=1389496, dx=15, dy=15, mmax=75, nmax=65, rotation=38, epsg=32617,
)
S_CN39 = round(1000 / 39 - 10, 3)  # 15.641 inches
X_SPLIT = 424200.0  # class 1 (green) west of it, class 2 (impervious) east


def _write_gradient_raster(path, low=-6.0, high=2.0):
    transform = from_origin(423000, 1391000, 1, 1)
    xx, _ = np.meshgrid(np.arange(3000), np.arange(3000))
    data = (low + (high - low) * (xx / 3000)).astype("float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=3000, width=3000, count=1,
        dtype="float32", crs="EPSG:32617", transform=transform, nodata=-9999,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def built_model(tmp_path):
    """A model with grid + dep + mask ready for Infiltration."""
    src_raster = tmp_path / "topobathy.tif"
    _write_gradient_raster(src_raster)

    catalog_path = tmp_path / "data_catalog.yml"
    catalog_path.write_text(
        "topobathy:\n"
        "  data_type: RasterDataset\n"
        "  driver: raster\n"
        f"  path: {str(src_raster).replace(chr(92), '/')}\n"
        "  crs: 32617\n"
        "  nodata: -9999\n"
    )

    model = SfincsModel(data_libs=[str(catalog_path)], root=str(tmp_path / "run"), mode="w+")
    GridMaker(model).setup_grid(**GRID_KWARGS)
    BathyMaker(model, str(catalog_path)).setup_bathy(zmin_active=-4, zmax_bounds=-2)
    return model


@pytest.fixture
def landcover(tmp_path):
    """Two-class land cover (1 green west, 2 impervious east) and its table."""
    bounds = (423000, 1388000, 425500, 1391000)
    green = gpd.GeoDataFrame(geometry=[box(bounds[0], bounds[1], X_SPLIT, bounds[3])], crs=32617)
    paved = gpd.GeoDataFrame(geometry=[box(X_SPLIT, bounds[1], bounds[2], bounds[3])], crs=32617)
    lc_path = BottomFriction.rasterize_landcover(
        {1: [green], 2: [paved]}, tmp_path / "landcover.tif",
        resolution=5, bounds=bounds, crs="EPSG:32617",
    )
    table = tmp_path / "reclass.csv"
    table.write_text(",N,cn,qinf\n1,0.035,39,29.97\n2,0.015,100,0\n")
    return lc_path, str(table)


def _active(model):
    return model.grid["msk"].values > 0


def _cell_x(model):
    return model.reggrid.coordinates["xc"][1]


def _read_inp(model):
    model.write()
    return (Path(model.root) / "sfincs.inp").read_text()


class TestCurveNumber:
    def test_uniform_cn_gives_expected_retention(self, built_model):
        Infiltration(built_model).setup_cn(39)

        scs = built_model.grid["scs"].values
        assert np.allclose(scs[_active(built_model)], S_CN39)
        assert built_model.config["scsfile"] == "sfincs.scs"
        assert built_model.config["storecumprcp"] == 1

    def test_cn_100_means_no_infiltration(self, built_model):
        Infiltration(built_model).setup_cn(100)

        assert np.allclose(built_model.grid["scs"].values[_active(built_model)], 0.0)

    def test_from_landcover_follows_the_classes(self, built_model, landcover):
        Infiltration(built_model).setup_cn_from_landcover(*landcover)

        scs = built_model.grid["scs"].values
        active, x = _active(built_model), _cell_x(built_model)
        # cells well inside each class (away from the border, where the
        # median resampling may mix both)
        assert np.allclose(scs[active & (x < X_SPLIT - 30)], S_CN39)
        assert np.allclose(scs[active & (x > X_SPLIT + 30)], 0.0)


class TestConstant:
    def test_uniform_rate_uses_scalar_qinf(self, built_model):
        Infiltration(built_model).setup_constant(1.02)

        assert built_model.config["qinf"] == 1.02
        assert "qinffile" not in built_model.config
        assert "qinf" not in built_model.grid

    def test_from_landcover_follows_the_classes(self, built_model, landcover):
        Infiltration(built_model).setup_constant_from_landcover(*landcover)

        qinf = built_model.grid["qinf"].values
        active, x = _active(built_model), _cell_x(built_model)
        assert np.allclose(qinf[active & (x < X_SPLIT - 30)], 29.97)
        assert np.allclose(qinf[active & (x > X_SPLIT + 30)], 0.0)
        assert built_model.config["qinffile"] == "sfincs.qinf"

    def test_missing_column_raises(self, built_model, landcover, tmp_path):
        table = tmp_path / "manning_only.csv"
        table.write_text(",N\n1,0.035\n2,0.015\n")
        with pytest.raises(KeyError):
            Infiltration(built_model).setup_constant_from_landcover(landcover[0], table)


class TestOnlyOneMethod:
    def test_constant_replaces_cn(self, built_model, landcover):
        infiltration = Infiltration(built_model)
        infiltration.setup_cn(39)
        infiltration.setup_constant_from_landcover(*landcover)

        inp = _read_inp(built_model)
        assert "qinffile" in inp
        assert "scsfile" not in inp
        assert not (Path(built_model.root) / "sfincs.scs").exists()

    def test_cn_replaces_constant(self, built_model, landcover):
        infiltration = Infiltration(built_model)
        infiltration.setup_constant_from_landcover(*landcover)
        infiltration.setup_cn(39)

        inp = _read_inp(built_model)
        assert "scsfile" in inp
        assert "storecumprcp" in inp
        assert "qinffile" not in inp
        assert not (Path(built_model.root) / "sfincs.qinf").exists()

    def test_cn_replaces_scalar_rate(self, built_model):
        infiltration = Infiltration(built_model)
        infiltration.setup_constant(1.02)
        infiltration.setup_cn(39)

        assert "qinf" not in built_model.config
