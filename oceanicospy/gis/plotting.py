from typing import Optional, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, Normalize
from matplotlib.ticker import MaxNLocator

try:
    import cmocean
    DEFAULT_CMAP = cmocean.cm.topo_r
except ImportError:  # Fallback if cmocean is not installed
    DEFAULT_CMAP = plt.get_cmap("terrain")

from .io_xyz import read_xyz
from .xyz_tile import XYZTile


class XYZPointPlotter:
    """
    Utility class to plot XYZ point clouds with a scientific colormap.

    This class uses oceanicospy.gis.io_xyz to read XYZ files and can
    also work directly with an XYZTile instance.
    """

    def __init__(self, default_cmap=DEFAULT_CMAP):
        """
        Initialize the plotter with a default colormap.

        Parameters
        ----------
        default_cmap : matplotlib.colors.Colormap, optional
            Colormap used when no custom colormap is provided.
        """
        self.default_cmap = default_cmap

    def _load_points(self, source: Union[str, XYZTile]):
        """
        Load XYZ points from a file path or an XYZTile.

        Parameters
        ----------
        source : str or XYZTile
            Path to XYZ file or an existing XYZTile instance.

        Returns
        -------
        pandas.DataFrame
            DataFrame with at least columns 'x', 'y', 'z'.

        Raises
        ------
        ValueError
            If required columns are missing.
        """
        if isinstance(source, XYZTile):
            df = source.points.copy()
        else:
            df = read_xyz(str(source))

        required_cols = ["x", "y", "z"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"XYZ data is missing required columns: {missing}"
            )

        return df

    def plot_xyz_points(
        self,
        source: Union[str, XYZTile],
        cmap_range: Optional[Tuple[float, float]] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
        title: str = "XYZ points",
        cmap=None,
        ax: Optional[plt.Axes] = None,
        point_size: float = 2.0,
        alpha: float = 0.7,
    ):
        """
        Plot XYZ point cloud data using a colormap.

        Parameters
        ----------
        source : str or XYZTile
            Path to XYZ file or an XYZTile instance.
        cmap_range : tuple(float, float), optional
            Color scale range (vmin, vmax). If None, values are taken
            from the data.
        xlim : tuple(float, float), optional
            X-axis limits (xmin, xmax).
        ylim : tuple(float, float), optional
            Y-axis limits (ymin, ymax).
        title : str, optional
            Title of the plot.
        cmap : matplotlib.colors.Colormap, optional
            Custom colormap to use. If None, the default colormap is used.
        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on. If None, a new figure and axes are created.
        point_size : float, optional
            Marker size for the scatter plot.
        alpha : float, optional
            Transparency of the points.

        Returns
        -------
        fig : matplotlib.figure.Figure
            Figure object containing the plot.
        ax : matplotlib.axes.Axes
            Axes object with the scatter.
        """
        # Load data
        df = self._load_points(source)

        # Build global mask for filters
        mask = np.ones(len(df), dtype=bool)

        # Apply x limits
        if xlim is not None:
            xmin, xmax = xlim
            mask &= (df["x"] >= xmin) & (df["x"] <= xmax)

        # Apply y limits
        if ylim is not None:
            ymin, ymax = ylim
            mask &= (df["y"] >= ymin) & (df["y"] <= ymax)

        # Apply z range for colormap
        if cmap_range is not None:
            vmin, vmax = cmap_range
            mask &= (df["z"] >= vmin) & (df["z"] <= vmax)
        else:
            vmin = float(df["z"].min())
            vmax = float(df["z"].max())

        df_filtered = df[mask]

        if df_filtered.empty:
            raise ValueError(
                "No data to plot with the given filter parameters."
            )

        # Decide normalization: centered at 0 only if data crosses zero
        z_values = df_filtered["z"].to_numpy()
        if (vmin < 0.0) and (vmax > 0.0):
            norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax)

        # Select colormap
        if cmap is None:
            cmap = self.default_cmap

        # Create axes if not provided
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 5))
        else:
            fig = ax.figure

        # Scatter plot
        scatter = ax.scatter(
            df_filtered["x"],
            df_filtered["y"],
            c=z_values,
            s=point_size,
            cmap=cmap,
            norm=norm,
            edgecolors="none",
            alpha=alpha,
        )

        # Colorbar
        cbar = fig.colorbar(scatter, ax=ax)
        cbar.set_label("Z value")

        # Axes formatting
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        ax.set_title(title, fontsize=12, pad=20)
        ax.set_aspect("equal", adjustable="box")

        if xlim is not None:
            ax.set_xlim(xlim)
        if ylim is not None:
            ax.set_ylim(ylim)

        ax.ticklabel_format(style="sci", axis="both", scilimits=(-3, 3))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=3))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))

        fig.tight_layout()

        return fig, ax
