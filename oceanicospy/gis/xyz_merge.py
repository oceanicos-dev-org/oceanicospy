import os
import glob
import math
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
import geopandas as gpd
from scipy.spatial import cKDTree


@dataclass
class XYZFileData:
    """
    Container for one XYZ tile: path, points, spacing estimate, and priority rank.
    """
    path: str
    points: pd.DataFrame
    spacing_estimate: float
    priority_rank: int
    crs: str = "EPSG:32617"  # <-- NEW: default to UTM17N for your case
    coverage_polygon: Optional[gpd.GeoDataFrame] = None

    def compute_coverage_polygon(
        self,
        xy_round_decimals: int = 6,
        grid_factor: float = 1.0,
        buffer_factor: float = 0.75,
        closing_factor: float = 1.0,
        simplify_tolerance: float = 0.0
    ) -> None:
        """
        Fast 'concave-like' envelope via grid snapping + buffered-union of unique cells.
        Operates in the CRS units of self.crs (meters if UTM).
        """
        df = self.points.copy()
        df["x"] = df["x"].round(xy_round_decimals)
        df["y"] = df["y"].round(xy_round_decimals)

        spacing = float(self.spacing_estimate) if np.isfinite(self.spacing_estimate) else 0.0
        if spacing <= 0.0:
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

        if len(df) == 0:
            self.coverage_polygon = gpd.GeoDataFrame({"geometry": []}, crs=self.crs)  # <-- CHANGED
            return
        if len(df) == 1:
            p = Point(float(df["x"].iloc[0]), float(df["y"].iloc[0])).buffer(max(1e-12, 0.5 * buffer_factor * max(spacing, 1e-4)))
            self.coverage_polygon = gpd.GeoDataFrame({"geometry": [p]}, crs=self.crs)  # <-- CHANGED
            return

        gx = np.floor((df["x"].to_numpy() / cell)).astype(np.int64)
        gy = np.floor((df["y"].to_numpy() / cell)).astype(np.int64)
        uniq, idx = np.unique(np.stack([gx, gy], axis=1), axis=0, return_index=True)

        cx = (uniq[:, 0].astype(float) + 0.5) * cell
        cy = (uniq[:, 1].astype(float) + 0.5) * cell

        geoms = [Point(xy).buffer(buf_r) for xy in zip(cx, cy)]
        merged = unary_union(geoms)

        if closing_factor > 0.0:
            merged = merged.buffer(close_r).buffer(-close_r)

        poly = merged
        if simplify_tolerance and simplify_tolerance > 0.0:
            poly = poly.simplify(simplify_tolerance, preserve_topology=True)

        self.coverage_polygon = gpd.GeoDataFrame({"geometry": [poly]}, crs=self.crs)



class XYZMerger:
    """
    Merge multiple XYZ tiles honoring user/manual priority or automatic priority
    (by point-spacing, finer spacing = higher priority). Overlaps are resolved
    by removing lower-priority points that fall within higher-priority coverage polygons.
    """

    def __init__(
        self,
        input_dir: str,
        bathy_positive: bool = True,
        manual_priority: Optional[List[str]] = None,
        xy_round_decimals: int = 3,
        sample_size_spacing: int = 5000,
        crs_epsg: str = "EPSG:32617" ):

        self.input_dir = input_dir
        self.bathy_positive_z = bathy_positive
        self.manual_priority = manual_priority
        self.xy_round_decimals = xy_round_decimals
        self.sample_size_spacing = sample_size_spacing
        self.crs = crs_epsg  # <-- NEW
        self._file_list: List[str] = []
        self._tiles: List[XYZFileData] = []
        self._merged_df: Optional[pd.DataFrame] = None

    def run_merge(self, output_xyz_path: str) -> None:
        """
        Orchestrates the full workflow: discover, load, prioritize, merge, export.
        """
        self._discover_tiles()
        self._load_all_tiles()
        self._assign_priorities_to_tiles()
        self._merge_tiles_respecting_priority_with_polygons()
        self._export_merged_xyz(output_xyz_path)

    def _discover_tiles(self) -> None:
        """
        Populate the internal file list with all .xyz files in input_dir.
        """
        pattern = os.path.join(self.input_dir, "*.xyz")
        self._file_list = sorted(glob.glob(pattern))
        if not self._file_list:
            raise FileNotFoundError(f"No XYZ files found in directory: {self.input_dir}")

    def _load_all_tiles(self) -> None:
        """
        Load all XYZ files into memory, estimate spacing, and compute coverage polygons.
        """
        tiles_raw: List[Tuple[str, pd.DataFrame]] = []
        for path in self._file_list:
            df_tile = self._load_single_xyz(path)
            tiles_raw.append((path, df_tile))

        self._tiles = []
        for path, df in tiles_raw:
            spacing_val = self._estimate_spacing(df)
            tile = XYZFileData(
                path=path,
                points=df,
                spacing_estimate=spacing_val,
                priority_rank=-1,
                crs=self.crs 
            )
            tile.compute_coverage_polygon(self.xy_round_decimals)
            self._tiles.append(tile)

    def _load_single_xyz(self, filepath: str) -> pd.DataFrame:
        """
        Load a single XYZ file into a DataFrame with columns ['x', 'y', 'z'].
        If bathy_positive_z is False, invert the sign of 'z'.
        """
        raw = np.loadtxt(filepath, dtype=float)
        if raw.ndim != 2 or raw.shape[1] < 3:
            raise ValueError(f"File {filepath} does not look like 'x y z' columns.")
        df = pd.DataFrame(raw[:, :3], columns=["x", "y", "z"])

        # Enforce Z sign convention if requested
        if not self.bathy_positive_z:
            df["z"] = -df["z"]

        return df

    def _estimate_spacing(self, df: pd.DataFrame) -> float:
        """
        Estimate a representative XY spacing using the median of the nearest-neighbor distances.
        """
        if len(df) <= 1:
            return math.inf

        sample = df.sample(n=min(self.sample_size_spacing, len(df)), random_state=42, replace=False)
        coords = sample[["x", "y"]].to_numpy()

        tree = cKDTree(coords)
        dists, _ = tree.query(coords, k=2)  # k=2 so column 1 is the nearest neighbor (excluding the point itself)

        return float(np.median(dists[:, 1]))

    def _assign_priorities_to_tiles(self) -> None:
        """
        Assign priority_rank to each tile. Rank 0 = highest priority.
        If manual_priority is provided, use its order first; remaining are ordered by spacing (finer first).
        """
        path_to_tile: Dict[str, Tuple[float, XYZFileData]] = {t.path: (t.spacing_estimate, t) for t in self._tiles}
        rank_map: Dict[str, int] = {}

        # Manual priority by explicit path or filename
        if self.manual_priority and len(self.manual_priority) > 0:
            for manual_idx, user_ref in enumerate(self.manual_priority):
                for tile_path in path_to_tile.keys():
                    if (
                        os.path.abspath(tile_path) == os.path.abspath(user_ref)
                        or os.path.basename(tile_path) == os.path.basename(user_ref)
                    ):
                        rank_map[tile_path] = manual_idx

            # Remaining tiles sorted by spacing (finer first)
            next_rank = len(rank_map)
            remaining: List[Tuple[str, float]] = [(p, data[0]) for p, data in path_to_tile.items() if p not in rank_map]
            remaining.sort(key=lambda t: t[1])

            for (p, _) in remaining:
                rank_map[p] = next_rank
                next_rank += 1
        else:
            # Automatic: sort by spacing (finer first)
            auto_sorted = sorted(path_to_tile.items(), key=lambda kv: kv[1][0])
            for auto_idx, (tile_path, _) in enumerate(auto_sorted):
                rank_map[tile_path] = auto_idx

        # Apply and sort tiles by priority
        for tile in self._tiles:
            tile.priority_rank = rank_map[tile.path]

        self._tiles.sort(key=lambda t: t.priority_rank)

    def _filter_points_with_priority(
        self,
        candidate_points: np.ndarray,
        accepted_points: np.ndarray,
        search_radius: float
    ) -> np.ndarray:
        """
        Keep only the candidate points that are not within search_radius of any already-accepted point.
        This is a KDTree-based XY distance filter.
        """
        if accepted_points.size == 0:
            return candidate_points

        tree = cKDTree(accepted_points[:, :2])  # build tree in XY
        dists, _ = tree.query(candidate_points[:, :2], k=1)
        mask_keep = dists > search_radius
        return candidate_points[mask_keep]

    def _merge_tiles_respecting_priority_with_polygons(self) -> None:
        """
        Merge tiles by removing points from lower-priority tiles that fall within any higher-priority coverage polygon.
        The final merged DataFrame is stored in self._merged_df.
        """
        # Ensure tiles are ordered by ascending priority_rank
        self._tiles.sort(key=lambda t: t.priority_rank)

        # Prepare GeoDataFrames for points and polygons
        tile_points_gdf_list: List[gpd.GeoDataFrame] = []
        tile_polygons_list: List[gpd.GeoDataFrame] = []

        for tile in self._tiles:
            gdf_points = gpd.GeoDataFrame(
                tile.points.copy(),
                geometry=gpd.points_from_xy(tile.points["x"], tile.points["y"]),
                crs=self.crs 
            )
            tile_points_gdf_list.append(gdf_points)
            tile_polygons_list.append(tile.coverage_polygon)  # already in self.crs

        trimmed_points_list: List[pd.DataFrame] = []

        for i, _ in enumerate(self._tiles):
            if i == 0:
                trimmed_points_list.append(tile_points_gdf_list[i][["x", "y", "z"]].copy())
                continue

            higher_priority_polys = pd.concat([tile_polygons_list[j] for j in range(i)], ignore_index=True)

            if higher_priority_polys.empty:
                trimmed_points_list.append(tile_points_gdf_list[i][["x", "y", "z"]].copy())
                continue

            gdf_points_i = tile_points_gdf_list[i]

            # Spatial join: mark points that fall within any higher-priority polygon
            joined = gpd.sjoin(
                gdf_points_i,
                higher_priority_polys,
                how="left",
                predicate="within"
            )

            # Keep only points not within higher-priority coverage
            keep_mask = joined["index_right"].isna()
            kept_points = joined.loc[keep_mask, ["x", "y", "z"]].copy()
            trimmed_points_list.append(kept_points)

        merged_df = pd.concat(trimmed_points_list, ignore_index=True)
        merged_df = merged_df.sort_values(by=["y", "x"]).reset_index(drop=True)
        self._merged_df = merged_df

    def _export_merged_xyz(self, output_xyz_path: str) -> None:
        """
        Save the merged XYZ data to disk with fixed numeric formatting.
        """
        if self._merged_df is None:
            raise RuntimeError("No merged data found. Run the merge pipeline before exporting.")
        np.savetxt(output_xyz_path, self._merged_df[["x", "y", "z"]].to_numpy(), fmt="%.6f")
        print(f"Merged XYZ exported to: {output_xyz_path}")



