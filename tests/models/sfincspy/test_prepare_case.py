from pathlib import Path

import numpy as np
import pandas as pd
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
rasterio = pytest.importorskip("rasterio")
xr = pytest.importorskip("xarray")

from rasterio.transform import from_origin  # noqa: E402

from oceanicospy.models.sfincspy.initializer import Initializer  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.prepare_case import SfincsCaseBuilder  # noqa: E402


GRID_KWARGS = dict(x0=1000, y0=1000, dx=5, dy=5, mmax=40, nmax=30, rotation=30, epsg=32617)
TIME_KWARGS = dict(tref="20240101 000000", tstart="20240101 000000", tstop="20240102 000000")


def _write_topobathy(path):
    """North-up 1 m raster sloping from -6 m (west) to +3 m (east)."""
    xx, _ = np.meshgrid(np.arange(400), np.arange(400))
    z = (-6.0 + 9.0 * xx / 400).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", height=400, width=400, count=1, dtype="float32",
                       crs="EPSG:32617", transform=from_origin(850, 1250, 1, 1), nodata=-9999) as dst:
        dst.write(z, 1)


def _write_xbeach_nc(path, hours=30):
    t = np.arange(hours) * 3600.0
    zs = (0.5 + 0.2 * np.sin(np.arange(hours))).reshape(hours, 1, 1)
    xr.Dataset(
        {"zs": (("globaltime", "ny", "nx"), zs)},
        coords={"globaltime": t, "globalx": (("ny", "nx"), [[0.0]]), "pointx": ("points", [0.0])},
    ).to_netcdf(path)


@pytest.fixture
def builder(tmp_path):
    init = Initializer(str(tmp_path / "case"))
    init.create_folders()
    _write_topobathy(Path(init.dict_folders["input"]) / "topobathy.tif")
    catalog = init.write_data_catalog({
        "topobathy": {"data_type": "RasterDataset", "driver": "raster",
                      "path": "topobathy.tif", "crs": 32617, "nodata": -9999},
    })
    b = SfincsCaseBuilder(root=init.dict_folders["run"], data_catalog=catalog)
    b.setup_time(**TIME_KWARGS)
    b.grid.setup_grid(**GRID_KWARGS)
    b.bathy.setup_bathy(zmin_active=-4, zmax_bounds=-2)
    return b, init


class TestSfincsCaseBuilderEndToEnd:
    def test_builds_a_complete_case(self, builder, tmp_path):
        """Initializer -> grid -> bathymetry -> friction -> forcings -> write()
        produces a sfincs.inp with every step registered and its files on disk."""
        b, init = builder
        b.friction.setup_uniform(manning_land=0.04, manning_sea=0.02)

        idx = pd.date_range("2024-01-01", periods=30, freq="h")
        tide = pd.DataFrame({"depth[m]": 0.5 + 0.15 * np.sin(np.arange(30) / 6)}, index=idx)
        b.waterlevel.from_dataframe(tide, column_name="depth[m]", x_bnd=1005, y_bnd=1010)

        nc = Path(init.dict_folders["input"]) / "xb.nc"
        _write_xbeach_nc(nc)
        b.waves.from_xbeach(str(nc), point_index=0)
        b.precipitation.uniform(pd.Series(np.linspace(0, 5, 30), index=idx))

        b.write()
        run_dir = Path(init.dict_folders["run"])
        inp = (run_dir / "sfincs.inp").read_text()
        for key in ["depfile", "mskfile", "manningfile", "bzsfile", "bndfile", "bzifile", "precipfile"]:
            assert key in inp, f"missing '{key}' in sfincs.inp"
        config = b.model.config
        for key in ["depfile", "mskfile", "bzsfile", "bzifile", "precipfile"]:
            assert (run_dir / config[key]).is_file(), f"{config[key]} not written"

    def test_manning_choices_are_traceable(self, builder):
        """Every decision (here: Manning values) is explicit in the script and
        ends up in the model, not chosen silently by a helper."""
        b, init = builder
        b.friction.setup_uniform(manning_land=0.0777, manning_sea=0.0222)

        dep = b.model.grid["dep"].values
        man = b.model.grid["manning"].values
        assert np.allclose(man[dep >= 0], 0.0777)
        assert np.allclose(man[dep < 0], 0.0222)

        b.write()
        assert (Path(init.dict_folders["run"]) / "sfincs.man").is_file()
