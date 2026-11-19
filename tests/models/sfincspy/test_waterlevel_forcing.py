import datetime as dt
import os
import shutil
import warnings

import numpy as np
import pandas as pd
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")

from hydromt_sfincs import SfincsModel  # noqa: E402

from oceanicospy.models.sfincspy.initializer import Initializer  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.bathymaker import BathyMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.waterlevel_forcing import WaterLevelForcing  # noqa: E402


GRID_KWARGS = dict(
    x0=423966, y0=1389496, dx=15, dy=15, mmax=75, nmax=65, rotation=38, epsg=32617,
)


@pytest.fixture
def model(tmp_path):
    m = SfincsModel(root=str(tmp_path / "run"), mode="w+")
    GridMaker(m).setup_grid(**GRID_KWARGS)
    m.setup_config(tref="20250618 000000", tstart="20250618 000000", tstop="20250626 000000")
    return m


def _write_raw_uhslc_csv(path, start, hours, base_mm=2270, amplitude_mm=200):
    """Mimic the raw UHSLC fast-delivery file format: no header,
    year,month,day,hour,depth[mm]."""
    times = pd.date_range(start, periods=hours, freq="h")
    depths_mm = base_mm + (amplitude_mm * np.sin(np.arange(hours) * 2 * np.pi / 12.42)).astype(int)
    rows = [
        f"{t.year},{t.month},{t.day},{t.hour},{d}"
        for t, d in zip(times, depths_mm)
    ]
    path.write_text("\n".join(rows) + "\n")


class TestGetWaterlevelFromUHSLC:
    def test_loads_existing_raw_file_without_datum_correction(self, model, tmp_path):
        input_dir = str(tmp_path) + "/"
        _write_raw_uhslc_csv(tmp_path / "h737.csv", start="2025-06-17 19:00", hours=200)

        wl = WaterLevelForcing(model)
        df = wl.get_waterlevel_from_UHSLC(station_id=737, input_dir=input_dir)

        assert "depth[m]" in df.columns
        # Raw values straight from mm/1000 - no offset removed, matching
        # what xbeachpy's get_waterlevel_from_UHSLC returns for the same file.
        assert df["depth[m]"].between(2.0, 2.6).all()


class TestDatumCorrectionPattern:
    def test_caller_datum_correction_on_returned_dataframe(self, model, tmp_path):
        """A station datum step (here -2.0 m up to a cutoff date) is applied
        by the caller on the returned DataFrame; the reader leaves it alone."""
        input_dir = str(tmp_path) + "/"
        _write_raw_uhslc_csv(tmp_path / "h737.csv", start="2018-12-31 10:00", hours=20)

        wl = WaterLevelForcing(model)
        df = wl.get_waterlevel_from_UHSLC(station_id=737, input_dir=input_dir)

        pre_correction = df["depth[m]"].copy()

        correction_mask = (
            (df.index >= dt.datetime(1997, 1, 1, 0)) &
            (df.index <= dt.datetime(2018, 12, 31, 18))
        )
        df.loc[correction_mask, "depth[m]"] -= 2.0

        assert correction_mask.any() and (~correction_mask).any()  # window straddles the cutoff
        assert np.allclose(
            df.loc[correction_mask, "depth[m]"], pre_correction.loc[correction_mask] - 2.0
        )
        assert np.allclose(
            df.loc[~correction_mask, "depth[m]"], pre_correction.loc[~correction_mask]
        )


class TestFromDataframe:
    def test_does_not_shift_time_unlike_from_csv(self, model, tmp_path):
        # from_dataframe assumes the caller (mirroring get_waterlevel_from_UHSLC)
        # already delivered local time - it must not re-shift by -5h.
        idx = pd.date_range("2025-06-18", periods=200, freq="h")
        df = pd.DataFrame({"depth[m]": 0.3 + 0.1 * np.sin(np.arange(200) / 5)}, index=idx)

        wl = WaterLevelForcing(model)
        wl.from_dataframe(df, column_name="depth[m]", x_bnd=423820, y_bnd=1389625)

        bzs_path = tmp_path / "run" / "bzs.csv"
        written = pd.read_csv(bzs_path, index_col=0, parse_dates=True)
        # First written timestamp should fall within [tstart, tstop] and match
        # the *un-shifted* input index (no -5h applied).
        assert written.index[0] >= idx[0]
        assert written.index[0].hour in df.index.hour.tolist()

    def test_filters_invalid_sentinel_and_crops_window(self, model, tmp_path):
        idx = pd.date_range("2025-06-17", periods=300, freq="h")
        values = 0.3 + 0.1 * np.sin(np.arange(300) / 5)
        values[5] = -32.767
        df = pd.DataFrame({"depth[m]": values}, index=idx)

        wl = WaterLevelForcing(model)
        wl.from_dataframe(df, column_name="depth[m]", x_bnd=423820, y_bnd=1389625)

        bzs_path = tmp_path / "run" / "bzs.csv"
        written = pd.read_csv(bzs_path, index_col=0, parse_dates=True)

        assert (written["depth[m]"] != -32.767).all()
        tstart = dt.datetime(2025, 6, 18)
        tstop = dt.datetime(2025, 6, 26)
        assert written.index.min() >= tstart
        assert written.index.max() <= tstop

    def test_registers_boundary_in_model_forcing(self, model, tmp_path):
        idx = pd.date_range("2025-06-18", periods=200, freq="h")
        df = pd.DataFrame({"depth[m]": 0.3 + 0.1 * np.sin(np.arange(200) / 5)}, index=idx)

        wl = WaterLevelForcing(model)
        wl.from_dataframe(df, column_name="depth[m]", x_bnd=423820, y_bnd=1389625)

        # HydroMT only writes bzsfile/bndfile into model.config on model.write();
        # immediately after setup_waterlevel_forcing() the "bzs" forcing layer
        # itself is the right thing to check.
        assert "bzs" in model.forcing

        model.write()
        assert model.config.get("bzsfile") is not None
        assert model.config.get("bndfile") is not None


class TestFromCsv:
    def test_shifts_utc_to_local_by_default(self, model, tmp_path):
        idx = pd.date_range("2025-06-18 05:00", periods=200, freq="h")  # UTC
        df = pd.DataFrame({"nivel_mar": 0.3 + 0.1 * np.sin(np.arange(200) / 5)}, index=idx)
        csv_path = tmp_path / "nivel_mar.csv"
        df.to_csv(csv_path)

        wl = WaterLevelForcing(model)
        wl.from_csv(str(csv_path), column_name="nivel_mar", x_bnd=423820, y_bnd=1389625)

        bzs_path = tmp_path / "run" / "bzs.csv"
        written = pd.read_csv(bzs_path, index_col=0, parse_dates=True)
        # 05:00 UTC -> 00:00 local; first local sample should align to tstart.
        assert written.index[0] == dt.datetime(2025, 6, 18, 0, 0)


# ---------------------------------------------------------------------------
# Multi-point boundary
# ---------------------------------------------------------------------------

def _write_gradient_raster(path, low=-6.0, high=2.0):
    """North-up raster covering the test grid, deep to the west, so the
    western cells become water-level boundary cells (msk == 2)."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    transform = from_origin(423000, 1391000, 1, 1)
    xx, _ = np.meshgrid(np.arange(3000), np.arange(3000))
    data = (low + (high - low) * (xx / 3000)).astype("float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=3000, width=3000, count=1,
        dtype="float32", crs="EPSG:32617", transform=transform, nodata=-9999,
    ) as dst:
        dst.write(data, 1)


@pytest.fixture
def bnd_model(tmp_path):
    """Grid + bathymetry with water-level boundary cells (msk == 2)."""
    src = tmp_path / "source_topobathy.tif"
    _write_gradient_raster(src)

    init = Initializer(str(tmp_path / "CaseBnd"))
    init.create_folders()
    shutil.copy(src, init.dict_folders["input"] + "topobathy.tif")
    catalog = init.write_data_catalog(
        {
            "topobathy": {
                "data_type": "RasterDataset", "driver": "raster",
                "path": "topobathy.tif", "crs": 32617, "nodata": -9999,
            }
        }
    )
    m = SfincsModel(data_libs=[catalog], root=init.dict_folders["run"], mode="w+")
    GridMaker(m).setup_grid(**GRID_KWARGS)
    BathyMaker(m, catalog).setup_bathy(zmin_active=-4, zmax_bounds=-2)
    m.setup_config(tref="20250618 000000", tstart="20250618 000000", tstop="20250619 000000")
    return m


def _boundary_points(model, n=3):
    """n cell centres spread along the msk == 2 cells."""
    msk = model.mask.values
    xc = model.grid.raster.xcoords.values
    yc = model.grid.raster.ycoords.values
    cells = np.argwhere(msk == 2)
    picks = np.linspace(0, len(cells) - 1, n).astype(int)
    return [(float(xc[i, j]), float(yc[i, j])) for i, j in cells[picks]]


def _series(names, offsets, hours=25, start="2025-06-18"):
    idx = pd.date_range(start, periods=hours, freq="h")
    base = 0.1 * np.sin(np.arange(hours) / 3)
    return pd.DataFrame({n: o + base for n, o in zip(names, offsets)}, index=idx)


def _read_bnd(model):
    return np.loadtxt(f"{model.root}/sfincs.bnd", ndmin=2)


def _read_bzs(model):
    return np.loadtxt(f"{model.root}/sfincs.bzs", ndmin=2)


NAMES = ["west", "centre", "east"]
OFFSETS = [0.1, 0.2, 0.3]


class TestMultiPoint:
    def test_single_point_call_unchanged(self, bnd_model):
        (x, y), = _boundary_points(bnd_model, 1)
        df = _series(["depth[m]"], [0.2])

        wl = WaterLevelForcing(bnd_model)
        wl.from_dataframe(df, column_name="depth[m]", x_bnd=x, y_bnd=y)
        bnd_model.write()

        bnd = _read_bnd(bnd_model)
        bzs = _read_bzs(bnd_model)
        assert bnd.shape == (1, 2)
        assert np.allclose(bnd[0], [x, y], atol=0.01)
        assert bzs.shape == (25, 2)
        assert np.allclose(bzs[:, 1], df["depth[m]"].values, atol=5e-3)  # HydroMT writes bzs with 2 decimals
        assert wl.point_ids == {"depth[m]": 1}

    def test_three_points_in_order(self, bnd_model):
        pts = _boundary_points(bnd_model, 3)
        locations = dict(zip(NAMES, pts))
        df = _series(NAMES, OFFSETS)

        wl = WaterLevelForcing(bnd_model)
        out = wl.from_dataframe(df, locations=locations)
        bnd_model.write()

        bnd = _read_bnd(bnd_model)
        bzs = _read_bzs(bnd_model)
        assert np.allclose(bnd, np.array(pts), atol=0.01)
        assert bzs.shape == (25, 4)
        for k, name in enumerate(NAMES, start=1):
            assert np.allclose(bzs[:, k], df[name].values, atol=5e-3)  # HydroMT writes bzs with 2 decimals
        assert wl.point_ids == {"west": 1, "centre": 2, "east": 3}

        written = pd.read_csv(out, index_col=0, parse_dates=True)
        assert list(written.columns) == NAMES

    def test_extra_columns_ignored(self, bnd_model):
        pts = _boundary_points(bnd_model, 2)
        df = _series(["a", "b", "unused"], [0.1, 0.2, 9.0])

        WaterLevelForcing(bnd_model).from_dataframe(df, locations=dict(zip(["a", "b"], pts)))
        bnd_model.write()

        assert _read_bzs(bnd_model).shape == (25, 3)

    def test_each_call_replaces_boundary(self, bnd_model):
        pts = _boundary_points(bnd_model, 3)
        wl = WaterLevelForcing(bnd_model)
        wl.from_dataframe(_series(NAMES, OFFSETS), locations=dict(zip(NAMES, pts)))

        df_one = _series(["tide"], [0.5])
        wl.from_dataframe(df_one, column_name="tide", x_bnd=pts[0][0], y_bnd=pts[0][1])
        bnd_model.write()

        assert _read_bnd(bnd_model).shape == (1, 2)
        bzs = _read_bzs(bnd_model)
        assert bzs.shape == (25, 2)
        assert np.allclose(bzs[:, 1], df_one["tide"].values, atol=5e-3)  # HydroMT writes bzs with 2 decimals
        assert wl.point_ids == {"tide": 1}

    def test_from_csv_with_locations(self, bnd_model, tmp_path):
        pts = _boundary_points(bnd_model, 2)
        df = _series(["a", "b"], [0.1, 0.2], start="2025-06-18 05:00")  # UTC
        csv_path = tmp_path / "bnd_utc.csv"
        df.to_csv(csv_path)

        wl = WaterLevelForcing(bnd_model)
        out = wl.from_csv(str(csv_path), locations=dict(zip(["a", "b"], pts)))

        written = pd.read_csv(out, index_col=0, parse_dates=True)
        assert written.index[0] == dt.datetime(2025, 6, 18, 0, 0)
        assert list(written.columns) == ["a", "b"]
        assert wl.point_ids == {"a": 1, "b": 2}

    def test_invalid_value_drops_time_for_all_points(self, bnd_model):
        pts = _boundary_points(bnd_model, 2)
        df = _series(["a", "b"], [0.1, 0.2])
        df.iloc[3, 1] = -32.767

        out = WaterLevelForcing(bnd_model).from_dataframe(df, locations=dict(zip(["a", "b"], pts)))
        written = pd.read_csv(out, index_col=0, parse_dates=True)

        assert len(written) == 24
        assert df.index[3] not in written.index

    def test_warns_when_many_times_dropped(self, bnd_model):
        pts = _boundary_points(bnd_model, 2)
        df = _series(["a", "b"], [0.1, 0.2])
        df.iloc[0:5, 0] = np.nan  # 20 % of the times

        with pytest.warns(UserWarning, match="dropped"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations=dict(zip(["a", "b"], pts)))

    def test_no_warning_in_normal_case(self, bnd_model):
        pts = _boundary_points(bnd_model, 3)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(NAMES, OFFSETS), locations=dict(zip(NAMES, pts)),
            )
        ours = [w for w in caught if "boundary" in str(w.message) or "dropped" in str(w.message)]
        assert ours == []

    def test_warns_for_point_far_from_boundary(self, bnd_model):
        (x, y), = _boundary_points(bnd_model, 1)
        far = (x - 1000.0, y)  # ~1 km, more than 10 cells of 15 m, less than 5 km

        with pytest.warns(UserWarning, match="more than 10 cells"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a"], [0.1]), locations={"a": far},
            )


class TestMultiPointErrors:
    def test_point_beyond_buffer_raises_and_writes_nothing(self, bnd_model):
        pts = _boundary_points(bnd_model, 2)
        locations = {"a": pts[0], "b": (pts[1][0] - 20000.0, pts[1][1])}

        with pytest.raises(ValueError, match="'b'.*HydroMT would drop it"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a", "b"], [0.1, 0.2]), locations=locations,
            )
        assert not os.path.exists(os.path.join(bnd_model.root, "bzs.csv"))
        assert "bzs" not in bnd_model.forcing

    def test_both_specifications_raise(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        with pytest.raises(ValueError, match="not both"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a"], [0.1]), column_name="a", x_bnd=1.0, y_bnd=2.0,
                locations={"a": pts[0]},
            )

    def test_missing_specification_raises(self, bnd_model):
        with pytest.raises(ValueError, match="either"):
            WaterLevelForcing(bnd_model).from_dataframe(_series(["a"], [0.1]), column_name="a")

    def test_missing_column_raises(self, bnd_model):
        pts = _boundary_points(bnd_model, 2)
        with pytest.raises(ValueError, match="not found.*'b'"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a"], [0.1]), locations=dict(zip(["a", "b"], pts)),
            )

    def test_repeated_coordinates_raise(self, bnd_model):
        (p,) = _boundary_points(bnd_model, 1)
        with pytest.raises(ValueError, match="same coordinates"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a", "b"], [0.1, 0.2]), locations={"a": p, "b": p},
            )

    @pytest.mark.parametrize("bad", [(1.0,), (1.0, 2.0, 3.0), ("x", 2.0), (np.nan, 2.0), 5.0])
    def test_bad_coordinates_raise(self, bnd_model, bad):
        with pytest.raises(ValueError, match="Location 'a'"):
            WaterLevelForcing(bnd_model).from_dataframe(
                _series(["a"], [0.1]), locations={"a": bad},
            )

    def test_empty_locations_raise(self, bnd_model):
        with pytest.raises(ValueError, match="non-empty"):
            WaterLevelForcing(bnd_model).from_dataframe(_series(["a"], [0.1]), locations={})

    def test_non_datetime_index_raises(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        df = _series(["a"], [0.1]).reset_index(drop=True)
        with pytest.raises(TypeError, match="datetime index"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations={"a": pts[0]})

    def test_repeated_times_raise(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        df = _series(["a"], [0.1])
        df = pd.concat([df, df.iloc[[2]]])
        with pytest.raises(ValueError, match="repeated times"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations={"a": pts[0]})

    def test_non_numeric_column_raises(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        df = _series(["a"], [0.1]).astype(object)
        df.iloc[0, 0] = "n/a"
        with pytest.raises(ValueError, match="numeric"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations={"a": pts[0]})

    def test_no_overlap_with_model_window_raises(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        df = _series(["a"], [0.1], start="2024-01-01")
        with pytest.raises(RuntimeError, match="tstart-tstop"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations={"a": pts[0]})

    def test_all_rows_invalid_raises(self, bnd_model):
        pts = _boundary_points(bnd_model, 1)
        df = _series(["a"], [0.1])
        df["a"] = -32.767
        with pytest.raises(RuntimeError, match="empty after filtering"):
            WaterLevelForcing(bnd_model).from_dataframe(df, locations={"a": pts[0]})
