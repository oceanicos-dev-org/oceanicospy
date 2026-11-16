import numpy as np
import pytest

hydromt_sfincs = pytest.importorskip("hydromt_sfincs")
from hydromt_sfincs import SfincsModel  # noqa: E402

from oceanicospy.models.sfincspy.preprocess.gridmaker import GridMaker  # noqa: E402


GRID_KWARGS = dict(
    x0=423966,
    y0=1389496,
    dx=15,
    dy=15,
    mmax=12,  # x-direction, deliberately != nmax to catch axis-swap bugs
    nmax=7,   # y-direction
    rotation=38,
    epsg=32617,
)


@pytest.fixture
def model(tmp_path):
    return SfincsModel(root=str(tmp_path / "model"), mode="w+")


class TestSetupGrid:
    def test_stores_axis_specific_grid_info(self, model):
        grid = GridMaker(model)
        info = grid.setup_grid(**GRID_KWARGS)

        assert info["mmax"] == GRID_KWARGS["mmax"]
        assert info["nmax"] == GRID_KWARGS["nmax"]

    def test_writes_expected_grid_shape_to_model(self, model):
        grid = GridMaker(model)
        grid.setup_grid(**GRID_KWARGS)

        # HydroMT's own RegularGrid is the ground truth GridMaker.plot_grid
        # must stay consistent with: mmax cells in x, nmax cells in y.
        assert model.reggrid.mmax == GRID_KWARGS["mmax"]
        assert model.reggrid.nmax == GRID_KWARGS["nmax"]

    def test_warns_on_very_large_grid(self, capsys):
        model_stub = type("Stub", (), {})()
        # Only exercise the warning branch, not a full hydromt build,
        # by calling setup_grid with mocked model.setup_grid as a no-op.
        model_stub.setup_grid = lambda **kwargs: None
        grid = GridMaker(model_stub)
        grid.setup_grid(mmax=2000, nmax=2000, x0=0, y0=0, dx=1, dy=1)
        captured = capsys.readouterr()
        assert "3 million" in captured.out


class TestCellCorners:
    def test_shape_follows_mmax_nmax(self, model):
        grid = GridMaker(model)
        grid.setup_grid(**GRID_KWARGS)
        X, Y = grid.cell_corners()

        assert X.shape == Y.shape == (GRID_KWARGS["nmax"] + 1, GRID_KWARGS["mmax"] + 1)

    def test_cell_centres_match_hydromt(self, model):
        # HydroMT's RegularGrid is the ground truth: the centres of the
        # corner quadrilaterals must match its (rotated) cell centres.
        grid = GridMaker(model)
        grid.setup_grid(**GRID_KWARGS)
        X, Y = grid.cell_corners()

        xc = 0.25 * (X[:-1, :-1] + X[1:, :-1] + X[:-1, 1:] + X[1:, 1:])
        yc = 0.25 * (Y[:-1, :-1] + Y[1:, :-1] + Y[:-1, 1:] + Y[1:, 1:])
        coords = model.reggrid.coordinates

        np.testing.assert_allclose(xc, coords["xc"][1])
        np.testing.assert_allclose(yc, coords["yc"][1])

    def test_raises_without_setup(self, model):
        with pytest.raises(RuntimeError):
            GridMaker(model).cell_corners()
