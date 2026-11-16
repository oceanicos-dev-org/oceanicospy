import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from hydromt_sfincs import SfincsModel  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import LineString, Point  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402


# 3 m cells on a 38 deg grid over a 1 m DEM: a 1-pixel wall is diluted
GRID_KWARGS = dict(x0=1000, y0=1000, dx=3, dy=3, mmax=30, nmax=30, rotation=38, epsg=32617)
DEM_ORIGIN = (900, 1200)        # upper-left corner of the 1 m DEM
WALL_X = 990.5                  # centre of the wall pixel column
GROUND, CREST = -1.0, 1.0


def _write_wall_dem(path):
    x0, y1 = DEM_ORIGIN
    z = np.full((200, 200), GROUND, dtype="float32")
    z[:, int(WALL_X - x0)] = CREST
    with rasterio.open(
        path, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:32617", transform=from_origin(x0, y1, 1, 1), nodata=-9999,
    ) as dst:
        dst.write(z, 1)


@pytest.fixture
def case(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_wall_dem(dem)
    catalog = tmp_path / "data_catalog.yml"
    catalog.write_text(
        "topobathy:\n  data_type: RasterDataset\n  driver: raster\n"
        f"  path: {str(dem).replace(chr(92), '/')}\n  crs: 32617\n  nodata: -9999\n"
    )
    model = SfincsModel(data_libs=[str(catalog)], root=str(tmp_path / "run"), mode="w+")
    GridMaker(model).setup_grid(**GRID_KWARGS)
    bathy = BathyMaker(model, str(catalog))
    bathy.setup_bathy(zmin_active=-4, zmax_bounds=-5)
    wall = gpd.GeoDataFrame(geometry=[LineString([(WALL_X, 1000), (WALL_X, 1199)])], crs=32617)
    return model, bathy, dem, wall


def _leaks(model, dep):
    """Face-adjacent cell pairs on opposite sides of the wall that are both below the crest."""
    t = model.reggrid.transform
    nmax, mmax = dep.shape
    jj, ii = np.meshgrid(np.arange(nmax), np.arange(mmax), indexing="ij")
    xc, _ = t * (ii + 0.5, jj + 0.5)
    low = dep < CREST - 1e-6
    side = np.sign(xc - WALL_X)
    n = 0
    for a, b in [((slice(None), slice(0, -1)), (slice(None), slice(1, None))),
                 ((slice(0, -1), slice(None)), (slice(1, None), slice(None)))]:
        n += int(((side[a] != side[b]) & low[a] & low[b]).sum())
    return n


def test_grid_transform_matches_dep_layout(case):
    model, *_ = case
    assert model.grid.raster.transform.almost_equals(model.reggrid.transform)


def test_wall_leaks_without_the_step(case):
    model, *_ = case
    assert _leaks(model, model.grid["dep"].values) > 0


def test_wall_is_continuous_after_the_step(case):
    model, bathy, dem, wall = case
    before = model.grid["dep"].values.copy()

    stats = bathy.preserve_crests(wall, dem)
    after = model.grid["dep"].values
    raised = after > before

    assert stats["cells_raised"] == int(raised.sum()) > 0
    assert np.allclose(after[raised], CREST)
    assert _leaks(model, after) == 0
    np.testing.assert_array_equal(after[~raised], before[~raised])


def test_cells_far_from_the_wall_are_unchanged(case):
    model, bathy, dem, wall = case
    t = model.reggrid.transform
    before = model.grid["dep"].values.copy()
    bathy.preserve_crests(wall, dem)

    nmax, mmax = before.shape
    jj, ii = np.meshgrid(np.arange(nmax), np.arange(mmax), indexing="ij")
    xc, _ = t * (ii + 0.5, jj + 0.5)
    far = np.abs(xc - WALL_X) > 2 * GRID_KWARGS["dx"]
    np.testing.assert_array_equal(model.grid["dep"].values[far], before[far])


def test_exempt_points_keep_their_elevation(case):
    model, bathy, dem, wall = case
    before = model.grid["dep"].values.copy()
    t = model.reggrid.transform

    # pick one cell that would be raised and exempt it through its centre point
    m_copy = model.grid["dep"].copy()
    stats_all = bathy.preserve_crests(wall, dem)
    n, m = np.argwhere(model.grid["dep"].values > before)[0]
    model.set_grid(m_copy, name="dep")
    xc, yc = t * (m + 0.5, n + 0.5)

    pts = gpd.GeoDataFrame(geometry=[Point(xc, yc)], crs=32617)
    stats = bathy.preserve_crests(wall, dem, exempt_points=pts)

    assert stats["cells_exempt"] == 1
    assert stats["cells_raised"] == stats_all["cells_raised"] - 1
    assert model.grid["dep"].values[n, m] == before[n, m]
