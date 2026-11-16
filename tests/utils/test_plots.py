import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from oceanicospy.utils.plots import cell_corners, plot_field, plot_grid  # noqa: E402


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


class TestCellCorners:
    def test_unrotated_grid(self):
        X, Y = cell_corners(100.0, 200.0, 10.0, 5.0, nx=3, ny=2)

        assert X.shape == Y.shape == (3, 4)
        np.testing.assert_allclose(X[0], [100, 110, 120, 130])
        np.testing.assert_allclose(Y[:, 0], [200, 205, 210])

    def test_rotation_is_counter_clockwise(self):
        # At 90 degrees the local x axis points north and local y points west
        X, Y = cell_corners(0.0, 0.0, 10.0, 5.0, nx=1, ny=1, rotation=90)

        np.testing.assert_allclose([X[0, 1], Y[0, 1]], [0, 10], atol=1e-12)
        np.testing.assert_allclose([X[1, 0], Y[1, 0]], [-5, 0], atol=1e-12)

    def test_cell_sizes_are_preserved_under_rotation(self):
        X, Y = cell_corners(0.0, 0.0, 10.0, 5.0, nx=4, ny=3, rotation=38)

        np.testing.assert_allclose(np.hypot(np.diff(X, axis=1), np.diff(Y, axis=1)), 10.0)
        np.testing.assert_allclose(np.hypot(np.diff(X, axis=0), np.diff(Y, axis=0)), 5.0)


class TestPlotGrid:
    def test_returns_axes_and_saves_only_when_asked(self, tmp_path):
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2, rotation=38)

        ax = plot_grid(X, Y)
        assert isinstance(ax, plt.Axes)
        assert list(tmp_path.iterdir()) == []

        out = tmp_path / "sub" / "grid.png"
        plot_grid(X, Y, output_path=out)
        assert out.is_file()

    def test_draws_one_line_per_grid_line(self):
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2)
        ax = plot_grid(X, Y)

        assert len(ax.lines) == (3 + 1) + (2 + 1)

    def test_draws_on_given_axes(self):
        fig, ax = plt.subplots()
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2)

        assert plot_grid(X, Y, ax=ax) is ax

    def test_rejects_mismatched_corners(self):
        with pytest.raises(ValueError):
            plot_grid(np.zeros((3, 4)), np.zeros((3, 3)))


class TestPlotField:
    def test_field_and_grid_share_axes(self, tmp_path):
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2, rotation=38)
        values = np.arange(6.0).reshape(2, 3)
        values[0, 0] = np.nan

        ax = plot_field(X, Y, values, label="z [m]")
        out = tmp_path / "field.png"
        plot_grid(X, Y, ax=ax, output_path=out)

        assert len(ax.collections) == 1
        assert len(ax.figure.axes) == 2  # main axes + colour bar
        assert out.is_file()

    def test_without_colorbar(self):
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2)
        ax = plot_field(X, Y, np.ones((2, 3)), colorbar=False)

        assert len(ax.figure.axes) == 1

    def test_rejects_values_with_wrong_shape(self):
        X, Y = cell_corners(0, 0, 1, 1, nx=3, ny=2)
        with pytest.raises(ValueError):
            plot_field(X, Y, np.ones((3, 4)))
