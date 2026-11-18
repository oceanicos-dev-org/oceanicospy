from pathlib import Path

import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import LineString  # noqa: E402

from oceanicospy.models.sfincspy.initializer import Initializer  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.prepare_case import SfincsCaseBuilder  # noqa: E402

DEM_RES = 10.0
TIMES = dict(tref="20240101 000000", tstart="20240101 000000", tstop="20240101 060000")


def _write_dem(path):
    """10 m DEM, 3 x 3 km, sloping from -5 m (west) to +5 m (east)."""
    z = np.add.outer(np.zeros(300), np.linspace(-5, 5, 300)).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", height=300, width=300, count=1, dtype="float32",
                       crs="EPSG:32618", transform=from_origin(0, 3000, DEM_RES, DEM_RES),
                       nodata=-9999) as dst:
        dst.write(z, 1)


def _builder(tmp_path, dx=80.0):
    init = Initializer(str(tmp_path / "case"))
    init.create_folders()
    _write_dem(Path(init.dict_folders["input"]) / "dem.tif")
    catalog = init.write_data_catalog({
        "dem": {"data_type": "RasterDataset", "driver": "raster",
                "path": "dem.tif", "crs": 32618, "nodata": -9999},
    })
    b = SfincsCaseBuilder(root=init.dict_folders["run"], data_catalog=catalog)
    b.setup_time(**TIMES)
    n = int(2960 // dx)
    b.grid.setup_grid(x0=0, y0=0, dx=dx, dy=dx, mmax=n, nmax=n, rotation=0, epsg=32618)
    b.bathy.setup_bathy([{"elevtn": "dem", "reproj_method": "average"}], zmin_active=-2, zmax_bounds=0)
    return b, Path(init.dict_folders["run"])


class TestBuildAndWrite:
    def test_writes_tables_and_a_truthful_inp(self, tmp_path):
        b, run = _builder(tmp_path)
        b.friction.setup_uniform(manning_land=0.04, manning_sea=0.02)
        assert b.bathy.setup_subgrid() == 8                     # 80 m / 10 m

        b.write()
        inp = (run / "sfincs.inp").read_text()
        assert (run / "sfincs_subgrid.nc").is_file()
        assert "sbgfile" in inp
        assert "depfile" not in inp and "manningfile" not in inp
        assert not (run / "sfincs.dep").exists()

    def test_without_subgrid_nothing_changes(self, tmp_path):
        b, run = _builder(tmp_path)
        b.friction.setup_uniform(manning_land=0.04, manning_sea=0.02)
        b.write()
        inp = (run / "sfincs.inp").read_text()
        assert "depfile" in inp and "manningfile" in inp and "sbgfile" not in inp
        assert (run / "sfincs.man").is_file()


class TestSubgridPixels:
    def test_odd_value_raises(self, tmp_path):
        b, _ = _builder(tmp_path)
        b.friction.setup_uniform()
        with pytest.raises(ValueError, match="even"):
            b.bathy.setup_subgrid(nr_subgrid_pixels=9)

    def test_non_integer_ratio_warns_and_uses_an_even_value(self, tmp_path):
        b, _ = _builder(tmp_path, dx=90.0)                        # 90 / 10 = 9, odd
        b.friction.setup_uniform()
        with pytest.warns(UserWarning, match="resampled"):
            n = b.bathy.setup_subgrid()
        assert n % 2 == 0


class TestRoughness:
    def _nrep_max(self, tmp_path, manning_land):
        b, _ = _builder(tmp_path)
        b.friction.setup_uniform(manning_land=manning_land, manning_sea=0.02)
        b.bathy.setup_subgrid()
        assert "manning" not in b.model.grid                     # map not used with subgrid
        return float(np.nanmax(b.model.subgrid["u_nrep"].values))

    def test_friction_choice_goes_into_the_tables(self, tmp_path):
        rough = self._nrep_max(tmp_path / "a", 0.08)
        smooth = self._nrep_max(tmp_path / "b", 0.03)
        assert rough > 1.5 * smooth

    def test_friction_after_subgrid_raises(self, tmp_path):
        b, _ = _builder(tmp_path)
        b.friction.setup_uniform()
        b.bathy.setup_subgrid()
        with pytest.raises(ValueError, match="subgrid"):
            b.friction.setup_uniform(manning_land=0.05)

    def test_missing_friction_warns(self, tmp_path):
        b, _ = _builder(tmp_path)
        with pytest.warns(UserWarning, match="defaults"):
            b.bathy.setup_subgrid()


class TestCompatibility:
    def test_crests_then_subgrid_raises(self, tmp_path):
        b, run = _builder(tmp_path)
        wall = gpd.GeoDataFrame(geometry=[LineString([(1500, 100), (1500, 2800)])], crs=32618)
        b.bathy.preserve_crests(wall, Path(run).parent / "input" / "dem.tif")
        b.friction.setup_uniform()
        with pytest.raises(ValueError, match="preserve_crests"):
            b.bathy.setup_subgrid()

    def test_subgrid_then_crests_raises(self, tmp_path):
        b, run = _builder(tmp_path)
        b.friction.setup_uniform()
        b.bathy.setup_subgrid()
        wall = gpd.GeoDataFrame(geometry=[LineString([(1500, 100), (1500, 2800)])], crs=32618)
        with pytest.raises(ValueError, match="weirs"):
            b.bathy.preserve_crests(wall, Path(run).parent / "input" / "dem.tif")

    def test_weirs_with_subgrid(self, tmp_path):
        b, run = _builder(tmp_path)
        b.friction.setup_uniform()
        b.bathy.setup_subgrid()
        line = gpd.GeoDataFrame({"z": [3.0]}, geometry=[LineString([(1800, 200), (1800, 2700)])], crs=32618)
        b.structures.setup_weirs(line)
        b.write()
        assert "weirfile" in (run / "sfincs.inp").read_text()

    def test_river_burnt_into_subgrid(self, tmp_path):
        river = gpd.GeoDataFrame({"rivwth": [30.0], "rivdph": [3.0]},
                                 geometry=[LineString([(2500, 100), (2500, 2800)])], crs=32618)
        b0, _ = _builder(tmp_path / "plain")
        b0.friction.setup_uniform()
        b0.bathy.setup_subgrid()
        b1, _ = _builder(tmp_path / "river")
        b1.friction.setup_uniform()
        b1.bathy.setup_subgrid(rivers=river)
        col = int(2500 // 80)                                    # cells along the river
        z0 = b0.model.subgrid["z_zmin"].values[:, col]
        z1 = b1.model.subgrid["z_zmin"].values[:, col]
        assert np.nanmean(z1) < np.nanmean(z0) - 1.0
