from pathlib import Path

import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from hydromt_sfincs import SfincsModel  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import LineString  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.structures import Structures  # noqa: E402


GRID_KWARGS = dict(x0=1000, y0=1000, dx=3, dy=3, mmax=30, nmax=30, rotation=38, epsg=32617)
DEM_ORIGIN = (900, 1200)
WALL_X = 990.5
GROUND, CREST = -1.0, 1.0
# fully inside the model region (local y axis points NW at 38 deg)
WALL_LINE = LineString([(WALL_X, 1020), (WALL_X, 1080)])


@pytest.fixture
def case(tmp_path):
    x0, y1 = DEM_ORIGIN
    z = np.full((200, 200), GROUND, dtype="float32")
    z[:, int(WALL_X - x0)] = CREST
    dem = tmp_path / "dem.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:32617", transform=from_origin(x0, y1, 1, 1), nodata=-9999,
    ) as dst:
        dst.write(z, 1)
    catalog = tmp_path / "data_catalog.yml"
    catalog.write_text(
        "topobathy:\n  data_type: RasterDataset\n  driver: raster\n"
        f"  path: {str(dem).replace(chr(92), '/')}\n  crs: 32617\n  nodata: -9999\n"
    )
    model = SfincsModel(data_libs=[str(catalog)], root=str(tmp_path / "run"), mode="w+")
    GridMaker(model).setup_grid(**GRID_KWARGS)
    BathyMaker(model, str(catalog)).setup_bathy(zmin_active=-4, zmax_bounds=-5)
    return model, dem


def _weir_file(model):
    model.write()
    return (Path(model.root) / "sfincs.weir").read_text()


def _crests(model):
    """Crest elevations (third column) of every point written to sfincs.weir."""
    rows = [r.split() for r in _weir_file(model).splitlines()]
    return np.array([float(r[2]) for r in rows if len(r) == 4])


class TestCrestSources:
    def test_z_column(self, case):
        model, _ = case
        lines = gpd.GeoDataFrame({"z": [0.8]}, geometry=[WALL_LINE], crs=32617)
        Structures(model).setup_weirs(lines)

        assert np.allclose(_crests(model), 0.8)
        assert model.config["weirfile"] == "sfincs.weir"

    def test_3d_lines(self, case):
        model, _ = case
        line = LineString([(WALL_X, 1020, 0.5), (WALL_X, 1080, 0.9)])
        Structures(model).setup_weirs(gpd.GeoDataFrame(geometry=[line], crs=32617))

        assert np.allclose(_crests(model), [0.5, 0.9])

    def test_from_dem_follows_the_crest(self, case):
        model, dem = case
        lines = gpd.GeoDataFrame(geometry=[WALL_LINE], crs=32617)
        Structures(model).setup_weirs(lines, dem=dem)

        z = _crests(model)
        assert len(z) > 2              # densified, not only the two vertices
        assert np.allclose(z, CREST)

    def test_from_dem_buffer_and_dz(self, case):
        model, dem = case
        shifted = gpd.GeoDataFrame(geometry=[LineString([(WALL_X + 2, 1020), (WALL_X + 2, 1080)])], crs=32617)
        s = Structures(model)

        s.setup_weirs(shifted, dem=dem, merge=False)
        assert np.allclose(_crests(model), GROUND)        # wall 2 m away, no buffer

        s.setup_weirs(shifted, dem=dem, buffer=2, dz=0.1, merge=False)
        assert np.allclose(_crests(model), CREST + 0.1)

    def test_missing_crest_raises(self, case):
        model, _ = case
        with pytest.raises(ValueError):
            Structures(model).setup_weirs(gpd.GeoDataFrame(geometry=[WALL_LINE], crs=32617))


class TestCoefficientAndFile:
    def test_default_and_custom_par1(self, case):
        model, _ = case
        lines = gpd.GeoDataFrame({"z": [0.8, 0.8], "par1": [np.nan, 0.9]},
                                 geometry=[WALL_LINE, WALL_LINE.parallel_offset(5)], crs=32617)
        Structures(model).setup_weirs(lines, par1=0.7)

        text = _weir_file(model)
        assert " 0.7" in text and " 0.9" in text

    def test_merge_adds_and_replace_overwrites(self, case):
        model, _ = case
        s = Structures(model)
        one = gpd.GeoDataFrame({"z": [0.8]}, geometry=[WALL_LINE], crs=32617)
        s.setup_weirs(one)
        s.setup_weirs(one)
        assert len(model.geoms["weir"]) == 2
        s.setup_weirs(one, merge=False)
        assert len(model.geoms["weir"]) == 1

    def test_lines_outside_the_region_raise(self, case):
        model, _ = case
        far = gpd.GeoDataFrame({"z": [1.0]}, geometry=[LineString([(5000, 5000), (5100, 5000)])], crs=32617)
        with pytest.raises(ValueError):
            Structures(model).setup_weirs(far)
