"""
Plotting of structured model grids and gridded fields.

The functions in this module are independent of any particular model. They
work on 2D arrays with the coordinates of the cell corners, so the same
calls serve regular, rotated and curvilinear grids (SFINCS, SWAN, XBeach,
...). For regular grids, :func:`cell_corners` builds those arrays from the
usual origin/spacing/rotation description.

Every plotting function draws on an existing ``matplotlib`` axes when one is
given (or creates a new figure otherwise), returns the axes, and saves the
figure only when ``output_path`` is provided.
"""

from pathlib import Path
from typing import Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np


def cell_corners(
    x0: float,
    y0: float,
    dx: float,
    dy: float,
    nx: int,
    ny: int,
    rotation: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the corner coordinates of a regular, optionally rotated, grid.

    Parameters
    ----------
    x0, y0 : float
        Coordinates of the grid origin (corner of the first cell).
    dx, dy : float
        Cell size along the local x and y axes of the grid.
    nx, ny : int
        Number of cells along the local x and y axes.
    rotation : float, optional
        Counter-clockwise rotation of the local x axis with respect to the
        east (x) axis, in degrees. Default is 0.

    Returns
    -------
    X, Y : numpy.ndarray
        Arrays of shape ``(ny + 1, nx + 1)`` with the corner coordinates.
        ``X[j, i]`` and ``Y[j, i]`` give the corner ``i`` steps along the
        local x axis and ``j`` steps along the local y axis from the origin.

    Notes
    -----
    This origin/rotation convention is shared by SFINCS
    (``x0, y0, rotation``), SWAN (``xpc, ypc, alpc``) and XBeach
    (``xori, yori, alfa``).

    Examples
    --------
    >>> X, Y = cell_corners(0, 0, 10, 10, nx=3, ny=2, rotation=30)
    >>> X.shape
    (3, 4)
    """
    theta = np.deg2rad(rotation)
    i, j = np.meshgrid(np.arange(nx + 1) * dx, np.arange(ny + 1) * dy)
    X = x0 + i * np.cos(theta) - j * np.sin(theta)
    Y = y0 + i * np.sin(theta) + j * np.cos(theta)
    return X, Y


def plot_grid(
    X: np.ndarray,
    Y: np.ndarray,
    ax: Optional[plt.Axes] = None,
    line_width: float = 0.3,
    color: str = "k",
    output_path: Optional[Union[str, Path]] = None,
    dpi: int = 300,
) -> plt.Axes:
    """
    Draw the cell edges of a structured grid.

    Parameters
    ----------
    X, Y : numpy.ndarray
        Corner coordinates, both of shape ``(ny + 1, nx + 1)``
        (see :func:`cell_corners`).
    ax : matplotlib.axes.Axes, optional
        Axes to draw on. A new figure is created if None.
    line_width : float, optional
        Width of the grid lines. Default is 0.3.
    color : str, optional
        Colour of the grid lines. Default is ``"k"``.
    output_path : str or pathlib.Path, optional
        If given, the figure is saved to this path (parent folders are
        created).
    dpi : int, optional
        Resolution used when saving. Default is 300.

    Returns
    -------
    matplotlib.axes.Axes
        The axes with the grid drawn.

    Examples
    --------
    >>> X, Y = cell_corners(0, 0, 10, 10, nx=20, ny=15, rotation=38)
    >>> ax = plot_grid(X, Y, output_path="figures/grid.png")
    """
    X, Y = _check_corners(X, Y)
    ax = _get_axes(ax)

    # Rows and columns of the corner arrays are the grid lines
    ax.plot(X.T, Y.T, color=color, lw=line_width)
    ax.plot(X, Y, color=color, lw=line_width)
    _format_axes(ax)

    _save(ax, output_path, dpi)
    return ax


def plot_field(
    X: np.ndarray,
    Y: np.ndarray,
    values: np.ndarray,
    ax: Optional[plt.Axes] = None,
    cmap: Optional[str] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    colorbar: bool = True,
    label: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    dpi: int = 300,
) -> plt.Axes:
    """
    Draw a cell-based field on a structured grid.

    Parameters
    ----------
    X, Y : numpy.ndarray
        Corner coordinates, both of shape ``(ny + 1, nx + 1)``
        (see :func:`cell_corners`).
    values : numpy.ndarray
        Cell values of shape ``(ny, nx)``. NaN or masked cells are left
        blank.
    ax : matplotlib.axes.Axes, optional
        Axes to draw on. A new figure is created if None.
    cmap : str, optional
        Matplotlib colormap name.
    vmin, vmax : float, optional
        Limits of the colour scale.
    colorbar : bool, optional
        If True (default), add a colour bar.
    label : str, optional
        Colour bar label.
    output_path : str or pathlib.Path, optional
        If given, the figure is saved to this path (parent folders are
        created).
    dpi : int, optional
        Resolution used when saving. Default is 300.

    Returns
    -------
    matplotlib.axes.Axes
        The axes with the field drawn.

    Raises
    ------
    ValueError
        If ``values`` does not have one element less than the corner
        arrays along each axis.

    Examples
    --------
    >>> X, Y = cell_corners(0, 0, 10, 10, nx=20, ny=15, rotation=38)
    >>> ax = plot_field(X, Y, depth, cmap="terrain", label="z [m]")
    >>> plot_grid(X, Y, ax=ax, output_path="figures/depth_grid.png")
    """
    X, Y = _check_corners(X, Y)
    values = np.ma.masked_invalid(np.asarray(values, dtype=float))
    if values.shape != (X.shape[0] - 1, X.shape[1] - 1):
        raise ValueError(
            f"values has shape {values.shape}; expected "
            f"{(X.shape[0] - 1, X.shape[1] - 1)} for corners of shape {X.shape}."
        )
    ax = _get_axes(ax)

    mesh = ax.pcolormesh(X, Y, values, cmap=cmap, vmin=vmin, vmax=vmax, shading="flat")
    if colorbar:
        ax.figure.colorbar(mesh, ax=ax, shrink=0.8, label=label)
    _format_axes(ax)

    _save(ax, output_path, dpi)
    return ax


def _check_corners(X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    if X.ndim != 2 or X.shape != Y.shape:
        raise ValueError(
            f"X and Y must be 2D arrays of the same shape; got {X.shape} and {Y.shape}."
        )
    return X, Y


def _get_axes(ax: Optional[plt.Axes]) -> plt.Axes:
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 6))
    return ax


def _format_axes(ax: plt.Axes) -> None:
    ax.set_aspect("equal")
    if not ax.get_xlabel():
        ax.set_xlabel("x [m]")
    if not ax.get_ylabel():
        ax.set_ylabel("y [m]")


def _save(ax: plt.Axes, output_path: Optional[Union[str, Path]], dpi: int) -> None:
    if output_path is None:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ax.figure.savefig(output_path, dpi=dpi, bbox_inches="tight")
