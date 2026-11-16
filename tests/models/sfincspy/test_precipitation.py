from pathlib import Path

import numpy as np
import pandas as pd
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")
xr = pytest.importorskip("xarray")

from hydromt_sfincs import SfincsModel  # noqa: E402
from shapely.geometry import Point, box  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.precipitation import Precipitation  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.wind_forcing import WindForcing  # noqa: E402


GRID_KWARGS = dict(x0=1000, y0=1000, dx=3, dy=3, mmax=30, nmax=30, rotation=38, epsg=32617)
TIMES = dict(tref="20240101 000000", tstart="20240101 000000", tstop="20240101 060000")
IDX = pd.date_range("2024-01-01", "2024-01-01 06:00", freq="10min")


@pytest.fixture
def model(tmp_path):
    m = SfincsModel(root=str(tmp_path / "run"), mode="w+")
    GridMaker(m).setup_grid(**GRID_KWARGS)
    m.setup_config(**TIMES)
    return m


def _centres(model):
    t = model.reggrid.transform
    jj, ii = np.meshgrid(np.arange(GRID_KWARGS["nmax"]), np.arange(GRID_KWARGS["mmax"]), indexing="ij")
    x, y = t * (ii + 0.5, jj + 0.5)
    return x.ravel(), y.ravel()


def _sfincs_bilinear(ds, var, x, y, it=0):
    """How SFINCS samples a FEWS meteo grid (sfincs_ncinput.F90 / sfincs_meteo.f90):
    value i sits at x(i) + dx/2, rows flipped, inside when 1 < iy < nrows and 0 < ix < ncols."""
    px, py = ds["x"].values, ds["y"].values
    dx, dy = px[1] - px[0], py[1] - py[0]
    data = ds[var].isel(time=it).values[::-1]
    nrows, ncols = data.shape
    yul = py[0] + (nrows - 1) * dy + 0.5 * dy
    xll = px[0] + 0.5 * dx
    iy = ((yul - y) / dy).astype(int) + 1
    ix = ((x - xll) / dx).astype(int) + 1
    inside = (iy > 1) & (iy < nrows) & (ix > 0) & (ix < ncols)
    out = np.zeros(len(x))
    i0, j0 = iy[inside] - 1, ix[inside] - 1
    dj = (yul - (iy[inside] - 1) * dy - y[inside]) / dy
    di = (x[inside] - (xll + (ix[inside] - 1) * dx)) / dx
    out[inside] = ((1 - dj) * (1 - di) * data[i0, j0] + (1 - dj) * di * data[i0, j0 + 1]
                   + dj * di * data[i0 + 1, j0 + 1] + dj * (1 - di) * data[i0 + 1, j0])
    return out, inside


def _written_grid(model):
    model.write_forcing()
    model.write_config()
    return xr.open_dataset(Path(model.root) / model.config["netamprfile"])


class TestUniform:
    def test_constant(self, model):
        Precipitation(model).uniform(5.0)
        assert "precip" in model.forcing
        assert np.allclose(model.forcing["precip"].values, 5.0)

    def test_series_is_clipped_to_model_period(self, model):
        idx = pd.date_range("2023-12-31 22:00", "2024-01-01 08:00", freq="h")
        Precipitation(model).uniform(pd.Series(np.arange(len(idx), dtype=float), index=idx))
        t = pd.to_datetime(model.forcing["precip"]["time"].values)
        assert t.min() >= pd.Timestamp("2024-01-01") and t.max() <= pd.Timestamp("2024-01-01 06:00")

    def test_series_outside_period_raises(self, model):
        idx = pd.date_range("2020-01-01", periods=3, freq="h")
        with pytest.raises(ValueError):
            Precipitation(model).uniform(pd.Series([1.0, 2.0, 3.0], index=idx))


class TestFromZones:
    def test_every_cell_reads_its_own_zone(self, model):
        x, y = _centres(model)
        zone = gpd.GeoDataFrame(geometry=[box(990, 1020, 1030, 1060)], crs=32617)
        Precipitation(model).from_zones(pd.Series(12.0, index=IDX), zone)

        # the grid only covers the zone; SFINCS reads 0 outside it
        val, _ = _sfincs_bilinear(_written_grid(model), "Precipitation", x, y)
        in_zone = (x > 990) & (x < 1030) & (y > 1020) & (y < 1060)
        assert in_zone.any()
        np.testing.assert_allclose(val, np.where(in_zone, 12.0, 0.0), atol=1e-5)

    def test_one_series_per_zone(self, model):
        x, y = _centres(model)
        zones = gpd.GeoDataFrame({"gauge": ["A", "B"]},
                                 geometry=[box(960, 1000, 1000, 1100), box(1000, 1000, 1080, 1100)], crs=32617)
        rates = pd.DataFrame({"A": 4.0, "B": 9.0}, index=IDX)
        Precipitation(model).from_zones(rates, zones, zone_col="gauge")

        val, _ = _sfincs_bilinear(_written_grid(model), "Precipitation", x, y)
        rows = (y > 1000) & (y < 1100)
        expected = np.where(rows & (x > 960) & (x < 1000), 4.0,
                            np.where(rows & (x >= 1000) & (x < 1080), 9.0, 0.0))
        np.testing.assert_allclose(val, expected, atol=1e-5)

    def test_zone_without_cells_raises(self, model):
        far = gpd.GeoDataFrame(geometry=[box(5000, 5000, 5100, 5100)], crs=32617)
        with pytest.raises(ValueError):
            Precipitation(model).from_zones(pd.Series(1.0, index=IDX), far)

    def test_missing_zone_column_raises(self, model):
        zones = gpd.GeoDataFrame({"gauge": ["A", "C"]}, geometry=[box(960, 1000, 1000, 1100)] * 2, crs=32617)
        with pytest.raises(ValueError):
            Precipitation(model).from_zones(pd.DataFrame({"A": 1.0}, index=IDX), zones, zone_col="gauge")

    def test_time_options(self, model):
        zone = gpd.GeoDataFrame(geometry=[box(990, 1020, 1030, 1060)], crs=32617)
        Precipitation(model).from_zones(pd.Series(1.0, index=IDX), zone, time_interpolation="linear")
        assert model.config["amprblock"] == 0          # keyword read by SFINCS (not ampr_block)
        assert model.config["dtwnd"] == 600.0           # lowered to the 10 min step


class TestFromGrid:
    def test_values_land_where_sfincs_reads_them(self, model):
        # north-up 5 m grid with a field linear in x and y: bilinear reading is exact
        xs = np.arange(900, 1120, 5.0) + 2.5
        ys = np.arange(1150, 960, -5.0) - 2.5
        X, Y = np.meshgrid(xs, ys)
        field = 0.1 * (X - 900) + 0.05 * (Y - 950)
        da = xr.DataArray(np.repeat(field[None], len(IDX), axis=0), dims=("time", "y", "x"),
                          coords={"time": IDX, "y": ys, "x": xs}, name="precip")
        da.raster.set_crs(32617)

        Precipitation(model).from_grid(da, cumulative=False)
        x, y = _centres(model)
        val, inside = _sfincs_bilinear(_written_grid(model), "Precipitation", x, y)
        expected = 0.1 * (x - 900) + 0.05 * (y - 950)
        assert inside.all()
        np.testing.assert_allclose(val, expected, rtol=1e-4)

    def test_aggregate_gives_uniform_series(self, model):
        xs = np.arange(900, 1120, 5.0) + 2.5
        ys = np.arange(1150, 960, -5.0) - 2.5
        da = xr.DataArray(np.full((len(IDX), len(ys), len(xs)), 3.0), dims=("time", "y", "x"),
                          coords={"time": IDX, "y": ys, "x": xs}, name="precip")
        da.raster.set_crs(32617)
        Precipitation(model).from_grid(da, cumulative=False, aggregate=True)
        assert "precip" in model.forcing and "precip_2d" not in model.forcing
        assert np.allclose(model.forcing["precip"].values, 3.0)


class TestExclusiveAndOptions:
    def test_uniform_replaces_grid_and_back(self, model):
        p = Precipitation(model)
        zone = gpd.GeoDataFrame(geometry=[box(990, 1020, 1030, 1060)], crs=32617)
        p.from_zones(pd.Series(1.0, index=IDX), zone)
        p.uniform(2.0)
        assert "precip_2d" not in model.forcing and "netamprfile" not in model.config
        p.from_zones(pd.Series(1.0, index=IDX), zone)
        assert "precip" not in model.forcing and "precipfile" not in model.config

    def test_spiderweb(self, model, tmp_path):
        spw = tmp_path / "storm.spw"
        spw.write_text("dummy")
        p = Precipitation(model)
        out = p.from_spiderweb(spw, use_precip=False, merge_frac=0.7)
        assert Path(out).is_file()
        assert model.config["spwfile"] == "storm.spw"
        assert model.config["usespwprecip"] == 0 and model.config["spwmergefrac"] == 0.7

        nc = tmp_path / "storm.nc"
        nc.write_text("dummy")
        p.from_spiderweb(nc)
        assert model.config["netspwfile"] == "storm.nc" and "spwfile" not in model.config

    def test_factor(self, model):
        Precipitation(model).set_factor(1.2)
        assert model.config["factor_prcp"] == 1.2


class TestUniformWind:
    def test_series_written_as_speed_and_direction(self, model):
        speed = pd.Series(np.linspace(2, 8, len(IDX)), index=IDX)
        WindForcing(model).uniform(speed, 45.0)
        model.write_forcing()
        rows = np.loadtxt(Path(model.root) / model.config["wndfile"])
        assert rows.shape[1] == 3
        np.testing.assert_allclose(rows[:, 1], speed.values, atol=0.01)  # written with 2 decimals
        assert np.allclose(rows[:, 2], 45.0)

    def test_constant(self, model):
        WindForcing(model).uniform(10.0, 90.0)
        assert "wnd" in model.forcing
