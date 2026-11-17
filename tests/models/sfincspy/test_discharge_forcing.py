from pathlib import Path

import numpy as np
import pandas as pd
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
gpd = pytest.importorskip("geopandas")

from hydromt_sfincs import SfincsModel  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402
from oceanicospy.models.sfincspy.preprocess.discharge_forcing import DischargeForcing  # noqa: E402


GRID_KWARGS = dict(x0=1000, y0=1000, dx=3, dy=3, mmax=30, nmax=30, rotation=38, epsg=32617)
IDX = pd.date_range("2025-06-18", periods=12, freq="h")
P1, P2 = (1000.0, 1030.0), (1010.0, 1040.0)        # inside the rotated grid
OUTSIDE = (2000.0, 2000.0)


@pytest.fixture
def model(tmp_path):
    m = SfincsModel(root=str(tmp_path / "run"), mode="w+")
    GridMaker(m).setup_grid(**GRID_KWARGS)
    m.setup_config(tref="20250618 000000", tstart="20250618 000000", tstop="20250618 110000")
    msk = m.reggrid.empty_mask
    m.set_grid(msk.where(False, 1).astype("uint8"), name="msk")
    return m


def _dis(model):
    # six decimals, as SfincsCaseBuilder.write does (HydroMT default is %7.2f)
    model.write_forcing(data_vars=["discharge"], fmt="%12.6f")
    return np.loadtxt(Path(model.root) / model.config["disfile"])


class TestFromDataframe:
    def test_registers_named_points(self, model):
        df = pd.DataFrame({"A": 1.0, "B": 2.0}, index=IDX)
        ids = DischargeForcing(model).from_dataframe(df, {"A": P1, "B": P2})
        assert ids == {"A": 1, "B": 2}
        assert "dis" in model.forcing

    def test_merge_keeps_earlier_points(self, model):
        dq = DischargeForcing(model)
        dq.from_dataframe(pd.DataFrame({"A": 1.0}, index=IDX), {"A": P1})
        dq.from_dataframe(pd.DataFrame({"B": 2.0}, index=IDX), {"B": P2})
        assert dq.point_ids == {"A": 1, "B": 2}
        np.testing.assert_allclose(_dis(model)[0, 1:], [1.0, 2.0])

    def test_replace(self, model):
        dq = DischargeForcing(model)
        dq.from_dataframe(pd.DataFrame({"A": 1.0}, index=IDX), {"A": P1})
        dq.from_dataframe(pd.DataFrame({"B": 2.0}, index=IDX), {"B": P2}, merge=False)
        assert dq.point_ids == {"B": 1}
        assert _dis(model).shape[1] == 2

    def test_missing_column_raises(self, model):
        with pytest.raises(ValueError):
            DischargeForcing(model).from_dataframe(pd.DataFrame({"A": 1.0}, index=IDX), {"A": P1, "B": P2})

    def test_series_outside_period_raises(self, model):
        idx = pd.date_range("2020-01-01", periods=12, freq="h")
        with pytest.raises(ValueError):
            DischargeForcing(model).from_dataframe(pd.DataFrame({"A": 1.0}, index=idx), {"A": P1})


class TestDistributed:
    def _cells(self):
        return pd.DataFrame({
            "group": ["R1", "R1", "R2"],
            "x": [P1[0], P2[0], P2[0]], "y": [P1[1], P2[1], P2[1]],
            "weight": [0.25, 0.75, 1.0],
        })

    def test_signed_weighted_discharge_per_cell(self, model):
        inflow = pd.DataFrame({"R1": np.linspace(-0.2, 0.4, len(IDX)), "R2": 0.1}, index=IDX)
        added = DischargeForcing(model).distributed(inflow, self._cells())

        assert list(added["name"]) == ["R1_000", "R1_001", "R2_002"]
        q = _dis(model)[:, 1:]
        np.testing.assert_allclose(q[:, 0], -0.25 * inflow["R1"], atol=1e-6)
        np.testing.assert_allclose(q[:, 1], -0.75 * inflow["R1"], atol=1e-6)
        np.testing.assert_allclose(q[:, 2], -0.1, atol=1e-6)
        # surcharge (negative inflow) returns water, capture removes it
        assert (q[0, :2] > 0).all() and (q[-1, :2] < 0).all()

    def test_total_equals_group_discharge(self, model):
        inflow = pd.DataFrame({"R1": 0.4, "R2": 0.1}, index=IDX)
        DischargeForcing(model).distributed(inflow, self._cells(), sign=1.0)
        q = _dis(model)[:, 1:]
        np.testing.assert_allclose(q[:, :2].sum(axis=1), 0.4, atol=1e-6)

    def test_geodataframe_and_custom_columns(self, model):
        cells = self._cells().rename(columns={"group": "inlet", "weight": "w"})
        gdf = gpd.GeoDataFrame(cells.drop(columns=["x", "y"]),
                               geometry=gpd.points_from_xy(cells.x, cells.y), crs=32617)
        inflow = pd.DataFrame({"R1": 0.4, "R2": 0.1}, index=IDX)
        added = DischargeForcing(model).distributed(inflow, gdf, group_col="inlet", weight_col="w")
        assert len(added) == 3

    def test_combined_with_a_single_point(self, model):
        dq = DischargeForcing(model)
        dq.distributed(pd.DataFrame({"R1": 0.4, "R2": 0.1}, index=IDX), self._cells())
        dq.from_dataframe(pd.DataFrame({"outfall": 0.3}, index=IDX), {"outfall": P1})
        assert dq.point_ids["outfall"] == 4
        assert _dis(model).shape[1] == 5

    def test_weights_must_add_up_to_one(self, model):
        cells = self._cells()
        cells.loc[0, "weight"] = 0.5
        with pytest.raises(ValueError):
            DischargeForcing(model).distributed(pd.DataFrame({"R1": 0.4, "R2": 0.1}, index=IDX), cells)

    def test_points_outside_active_cells_raise(self, model):
        cells = self._cells()
        cells.loc[2, ["x", "y"]] = OUTSIDE
        with pytest.raises(ValueError):
            DischargeForcing(model).distributed(pd.DataFrame({"R1": 0.4, "R2": 0.1}, index=IDX), cells)

    def test_missing_group_raises(self, model):
        with pytest.raises(ValueError):
            DischargeForcing(model).distributed(pd.DataFrame({"R1": 0.4}, index=IDX), self._cells())
