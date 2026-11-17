from pathlib import Path

import numpy as np
import pandas as pd
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")
xr = pytest.importorskip("xarray")

from hydromt_sfincs import SfincsModel  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402
from oceanicospy.models.sfincspy.postprocess import (  # noqa: E402
    SfincsOutputReader, compound_effect, difference, flooded_area, hazard,
    sink_shortfall, water_volume, wet_duration, zone_mask,
)

GRID = dict(x0=1000, y0=1000, dx=2, dy=2, mmax=20, nmax=10, rotation=30, epsg=32617)
TIMES = pd.date_range("2024-01-01", periods=3, freq="h")


def _write_dem(path):
    with rasterio.open(path, "w", driver="GTiff", height=120, width=120, count=1, dtype="float32",
                       crs="EPSG:32617", transform=from_origin(960, 1080, 1, 1), nodata=-9999) as dst:
        dst.write(np.ones((120, 120), "float32"), 1)


def _write_map(root, model, hmax_left=0.2, hmax_right=0.0, vmax=1.0):
    """sfincs_map.nc with the SFINCS layout: (n, m) cells, time and timemax."""
    nmax, mmax = GRID["nmax"], GRID["mmax"]
    t = model.reggrid.transform
    jj, ii = np.meshgrid(np.arange(nmax), np.arange(mmax), indexing="ij")
    xc, yc = t * (ii + 0.5, jj + 0.5)
    cj, ci = np.meshgrid(np.arange(nmax + 1), np.arange(mmax + 1), indexing="ij")
    cx, cy = t * (ci, cj)
    left = ii < mmax // 2
    hmax = np.where(left, hmax_left, hmax_right).astype("float32")
    h = np.stack([hmax * f for f in (0.0, 1.0, 0.5)]).astype("float32")
    hmax_w = hmax.copy()
    hmax_w[0, -1] = -99999.0                                   # fill value in one cell
    ds = xr.Dataset(
        {
            "zb": (("n", "m"), np.ones((nmax, mmax), "float32")),
            "h": (("time", "n", "m"), h),
            "zs": (("time", "n", "m"), h + 1.0),
            "hmax": (("timemax", "n", "m"), hmax_w[None]),
            "zsmax": (("timemax", "n", "m"), (hmax + 1.0)[None]),
            "vmax": (("timemax", "n", "m"), np.full((1, nmax, mmax), vmax, "float32")),
            "tmax": (("timemax", "n", "m"), np.where(left, 5400.0, 0.0)[None].astype("float32")),
            "x": (("n", "m"), xc), "y": (("n", "m"), yc),
            "corner_x": (("corner_n", "corner_m"), cx), "corner_y": (("corner_n", "corner_m"), cy),
        },
        coords={"time": TIMES, "timemax": TIMES[-1:]},
    )
    ds.to_netcdf(Path(root) / "sfincs_map.nc")


@pytest.fixture
def run(tmp_path):
    dem = tmp_path / "dem.tif"
    _write_dem(dem)
    cat = tmp_path / "cat.yml"
    cat.write_text("topobathy:\n  data_type: RasterDataset\n  driver: raster\n"
                   f"  path: {str(dem).replace(chr(92), '/')}\n  crs: 32617\n  nodata: -9999\n")
    root = tmp_path / "run"
    m = SfincsModel(data_libs=[str(cat)], root=str(root), mode="w+")
    GridMaker(m).setup_grid(**GRID)
    BathyMaker(m, str(cat)).setup_bathy(zmin_active=-4, zmax_bounds=-5)
    m.setup_config(tref="20240101 000000", tstart="20240101 000000", tstop="20240101 020000")
    m.write()
    _write_map(root, m)
    return root, m


def _ds(root):
    return SfincsOutputReader(root).read_map()


class TestReader:
    def test_map_on_model_grid_with_area_and_fill_values(self, run):
        root, _ = run
        ds = _ds(root)
        assert ds["hmax"].dims == ("timemax", "y", "x")
        assert np.allclose(ds["cell_area"], GRID["dx"] * GRID["dy"])
        assert np.isnan(ds["hmax"].values[0, 0, -1])            # fill value masked

    def test_corners_match_cell_centres(self, run):
        root, _ = run
        reader = SfincsOutputReader(root)
        ds = reader.read_map()
        X, Y = reader.cell_corners()
        xc = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
        np.testing.assert_allclose(xc, ds["xc"].values)


class TestMetrics:
    def test_area_and_volume(self, run):
        root, _ = run
        ds = _ds(root)
        cells_left = GRID["nmax"] * GRID["mmax"] // 2
        assert flooded_area(ds, 0.1) == pytest.approx(cells_left * 4.0)
        vol = water_volume(ds)
        assert vol.iloc[1] == pytest.approx(cells_left * 4.0 * 0.2, rel=1e-5)
        assert water_volume(ds, min_depth=0.15).iloc[2] == 0.0  # 0.1 m film left out

    def test_zone_mask_limits_metrics(self, run):
        root, m = run
        ds = _ds(root)
        t = m.reggrid.transform
        zone = Polygon([t * (0, 0), t * (5, 0), t * (5, 10), t * (0, 10)])   # columns 0-4
        mask = zone_mask(ds, zone)
        assert int(mask.sum()) == 5 * GRID["nmax"]
        assert flooded_area(ds, 0.1, mask) == pytest.approx(5 * GRID["nmax"] * 4.0)

    def test_wet_duration_in_hours(self, run):
        root, _ = run
        dur = wet_duration(_ds(root))
        assert float(dur.max()) == pytest.approx(1.5)

    def test_hazard_classes(self, run):
        root, _ = run
        out = hazard(_ds(root), bounds=[0.1, 0.5], labels=["low", "medium", "high"], min_depth=0.05)
        assert out["hazard_class"].attrs["labels"] == ["low", "medium", "high"]
        assert np.nanmax(out["hv"]) == pytest.approx(0.2)
        assert set(np.unique(out["hazard_class"].values[~np.isnan(out["hazard_class"].values)])) == {1.0}

    def test_hazard_requires_vmax(self, run):
        root, _ = run
        with pytest.raises(KeyError):
            hazard(_ds(root).drop_vars("vmax"), bounds=[0.5])

    def test_compound_effect_and_driver(self, run):
        root, m = run
        ds = _ds(root)
        coastal = ds.copy(); coastal["hmax"] = ds["hmax"] * 0.5      # 0.1 m on the left
        pluvial = ds.copy(); pluvial["hmax"] = ds["hmax"] * 0.25     # 0.05 m
        out = compound_effect(coastal, pluvial, ds, wet=0.05, tolerance=0.05)
        left = ~np.isnan(out["driver"].values)
        assert np.allclose(out["effect"].values[left], 0.1)
        assert set(np.unique(out["driver"].values[left])) == {2.0}   # compound
        out2 = compound_effect(coastal, pluvial, ds, wet=0.05, tolerance=0.2)
        assert set(np.unique(out2["driver"].values[left])) == {0.0}  # coastal dominates

    def test_difference(self, run):
        root, _ = run
        a = _ds(root); b = a.copy(); b["hmax"] = a["hmax"] + 0.1
        assert np.allclose(difference(a, b).values[~np.isnan(a["hmax"].values[0])], 0.1)


class TestSinkShortfall:
    def test_demand_on_dry_cell_is_counted(self):
        t = pd.date_range("2024-01-01", periods=5, freq="min")
        his = xr.Dataset(
            {"point_h": (("time", "stations"), np.array([[0.1, 0.0]] * 3 + [[0.0, 0.0]] * 2))},
            coords={"time": t, "station_name": ("stations", ["c1", "c2"])},
        )
        q = pd.DataFrame({"s1": -0.01, "s2": -0.02}, index=t)
        out = sink_shortfall(his, q, stations={"s1": "c1", "s2": "c2"}, groups={"s1": "R1", "s2": "R1"})
        assert out.loc["s1", "demanded_m3"] == pytest.approx(0.01 * 60 * 5)
        assert out.loc["s1", "ratio"] == pytest.approx(2 / 5)       # dry in the last 2 of 5 minutes
        assert out.loc["s2", "ratio"] == pytest.approx(1.0)         # always dry
        assert out.loc["group:R1", "not_extracted_m3"] == pytest.approx(0.01 * 120 + 0.02 * 300)

    def test_sources_are_not_demand(self):
        t = pd.date_range("2024-01-01", periods=3, freq="min")
        his = xr.Dataset({"point_h": (("time", "stations"), np.zeros((3, 1)))},
                         coords={"time": t, "station_name": ("stations", ["c1"])})
        out = sink_shortfall(his, pd.DataFrame({"s1": 0.5}, index=t), stations={"s1": "c1"})
        assert out.loc["s1", "demanded_m3"] == 0.0 and np.isnan(out.loc["s1", "ratio"])


class TestDownscale:
    def test_depth_on_fine_dem(self, run, tmp_path):
        from oceanicospy.models.sfincspy.postprocess import downscale
        root, _ = run
        out = tmp_path / "flood.tif"
        da = downscale(SfincsOutputReader(root), tmp_path / "dem.tif", hmin=0.05, output=out)
        vals = da.values[np.isfinite(da.values)]
        assert vals.size > 0 and np.allclose(vals, 0.2, atol=1e-5)   # zsmax 1.2 over a DEM at 1.0
        assert out.is_file()
