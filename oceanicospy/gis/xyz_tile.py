from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from scipy.spatial import cKDTree


@dataclass
class XYZTile:
    """
    Represents a single XYZ tile with point data, CRS metadata,
    spacing estimation and coverage polygon construction.

    This class does NOT perform file I/O directly. Reading/writing must
    be done through oceanicospy.gis.io_xyz. CRS changes must be handled
    through oceanicospy.gis.crs_tools.

    Attributes
    ----------
    path : str
        Original file path (for metadata only).
    points : pandas.DataFrame
        Must contain 'x', 'y', 'z' columns.
    crs : str
        CRS string (e.g., 'EPSG:32617').
    spacing_estimate : float or None
        Approximate point spacing derived from nearest-neighbor analysis.
    priority_rank : int
        Used by XYZMerger to resolve overlapping areas.
    coverage_polygon : geopandas.GeoDataFrame or None
        Footprint polygon in the same CRS.
    """
    path: str
    points: pd.DataFrame
    crs: str
    spacing_estimate: Optional[float] = None
    priority_rank: int = 0
    coverage_polygon: Optional[gpd.GeoDataFrame] = None

    # ----------------------------------------------------------
    # SPACING ESTIMATION (same idea as old _estimate_spacing)
    # ----------------------------------------------------------
    def compute_spacing_estimate(self, sample_size: int = 2000) -> float:
        """
        Estimate a representative XY spacing using the median of
        nearest-neighbor distances.

        Parameters
        ----------
        sample_size : int
            Maximum number of points used to compute statistics.

        Returns
        -------
        float
            Estimated spacing in CRS units (typically meters).
        """
        # If spacing is already computed and finite, reuse it
        if self.spacing_estimate is not None and np.isfinite(self.spacing_estimate):
            return float(self.spacing_estimate)

        n = len(self.points)
        if n <= 1:
            # With <= 1 point, spacing is not meaningful
            self.spacing_estimate = np.inf
            return self.spacing_estimate

        sample = self.points.sample(
            n=min(sample_size, n),
            random_state=42,
            replace=False,
        )
        coords = sample[["x", "y"]].to_numpy()

        tree = cKDTree(coords)
        dists, _ = tree.query(coords, k=2)  # column 1 = nearest neighbor
        spacing_val = float(np.median(dists[:, 1]))

        self.spacing_estimate = spacing_val
        return spacing_val

    # ----------------------------------------------------------
    # COVERAGE POLYGON (fiel a tu XYZFileData.compute_coverage_polygon)
    # ----------------------------------------------------------
    def compute_coverage_polygon(
        self,
        xy_round_decimals: int = 6,
        grid_factor: float = 1.0,
        buffer_factor: float = 0.75,
        closing_factor: float = 1.0,
        simplify_tolerance: float = 0.0,
    ) -> None:
        """
        Fast 'concave-like' envelope via grid snapping + buffered-union
        of unique cells. Operates in the CRS units (meters if UTM).

        This is a faithful port of the old XYZFileData.compute_coverage_polygon
        so that behavior is preserved.

        Parameters
        ----------
        xy_round_decimals : int
            Decimals to round X/Y coordinates before grouping.
        grid_factor : float
            Factor multiplied by spacing to define grid cell size.
        buffer_factor : float
            Factor multiplied by spacing to define buffer size.
        closing_factor : float
            Factor for morphological closing (buffer-in / buffer-out).
        simplify_tolerance : float
            Tolerance for optional polygon simplification.
        """
        df = self.points.copy()
        df["x"] = df["x"].round(xy_round_decimals)
        df["y"] = df["y"].round(xy_round_decimals)

        # Use existing spacing_estimate if valid, otherwise compute it
        spacing = float(self.spacing_estimate) if (
            self.spacing_estimate is not None and np.isfinite(self.spacing_estimate)
        ) else 0.0

        if spacing <= 0.0:
            # Fallback similar to old implementation
            if len(df) >= 2:
                sample = df.sample(n=min(2000, len(df)), random_state=42)
                coords = sample[["x", "y"]].to_numpy()
                tree = cKDTree(coords)
                dists, _ = tree.query(coords, k=2)
                spacing = float(np.median(dists[:, 1]))
            else:
                spacing = 1e-4

        cell = max(1e-12, grid_factor * spacing)
        buf_r = max(1e-12, buffer_factor * spacing)
        close_r = buf_r * closing_factor if closing_factor > 0 else 0.0

        # Edge cases: 0 or 1 point
        if len(df) == 0:
            self.coverage_polygon = gpd.GeoDataFrame({"geometry": []}, crs=self.crs)
            return

        if len(df) == 1:
            p = Point(
                float(df["x"].iloc[0]),
                float(df["y"].iloc[0]),
            ).buffer(
                max(1e-12, 0.5 * buffer_factor * max(spacing, 1e-4))
            )
            self.coverage_polygon = gpd.GeoDataFrame({"geometry": [p]}, crs=self.crs)
            return

        # Compute snapped grid indices
        gx = np.floor(df["x"].to_numpy() / cell).astype(np.int64)
        gy = np.floor(df["y"].to_numpy() / cell).astype(np.int64)

        # Unique grid cells
        uniq, _ = np.unique(
            np.stack([gx, gy], axis=1),
            axis=0,
            return_index=True,
        )

        # Cell centroids
        cx = (uniq[:, 0].astype(float) + 0.5) * cell
        cy = (uniq[:, 1].astype(float) + 0.5) * cell

        # Buffer each centroid and unary_union (exactly as before)
        geoms = [Point(xy).buffer(buf_r) for xy in zip(cx, cy)]
        merged = unary_union(geoms)

        # Optional morphological closing
        if closing_factor > 0.0:
            merged = merged.buffer(close_r).buffer(-close_r)

        poly = merged
        # Optional simplification
        if simplify_tolerance and simplify_tolerance > 0.0:
            poly = poly.simplify(simplify_tolerance, preserve_topology=True)

        self.coverage_polygon = gpd.GeoDataFrame({"geometry": [poly]}, crs=self.crs)
