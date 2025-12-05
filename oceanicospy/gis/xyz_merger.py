from __future__ import annotations

import os
import glob
import math
from typing import List, Optional, Dict, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

from .io_xyz import read_xyz, write_xyz
from .xyz_tile import XYZTile


class XYZMerger:
    """
    Merge multiple XYZ tiles honoring user/manual priority or automatic priority
    (by point-spacing, finer spacing = higher priority). Overlaps are resolved
    by removing lower-priority points that fall within higher-priority coverage
    polygons.

    This is an architectural refactor of the old XYZMerger:
    - File I/O delegated to io_xyz (read_xyz / write_xyz).
    - Tile representation handled by XYZTile.
    - Coverage polygons and priority logic remain faithful to the old behavior.
    """

    def __init__(
        self,
        input_dir: str,
        bathy_positive: bool = True,
        manual_priority: Optional[List[str]] = None,
        xy_round_decimals: int = 6,
        sample_size_spacing: int = 5000,
        crs_epsg: str = "EPSG:9377",
    ):
        """
        Parameters
        ----------
        input_dir : str
            Directory containing .xyz files.
        bathy_positive : bool, optional
            If False, z values will be sign-inverted after loading.
        manual_priority : list of str, optional
            List of filenames or paths specifying highest priority first.
        xy_round_decimals : int, optional
            Decimal precision used for coverage polygon grid snapping.
        sample_size_spacing : int, optional
            Sample size used to estimate spacing.
        crs_epsg : str, optional
            CRS string, e.g., 'EPSG:32617' or 'EPSG:9377'.
        """
        self.input_dir = input_dir
        self.bathy_positive_z = bathy_positive
        self.manual_priority = manual_priority
        self.xy_round_decimals = xy_round_decimals
        self.sample_size_spacing = sample_size_spacing
        self.crs = crs_epsg

        self._file_list: List[str] = []
        self._tiles: List[XYZTile] = []
        self._merged_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def run_merge(self, output_xyz_path: str) -> None:
        """
        Orchestrate the full workflow: discover, load, prioritize, merge, export.
        """
        self._discover_tiles()
        self._load_all_tiles()
        self._assign_priorities_to_tiles()
        self._merge_tiles_respecting_priority_with_polygons()
        self._export_merged_xyz(output_xyz_path)

    # ------------------------------------------------------------------
    # STAGE 1 — DISCOVER FILES
    # ------------------------------------------------------------------
    def _discover_tiles(self) -> None:
        """
        Populate the internal file list with all .xyz files in input_dir.
        """
        pattern = os.path.join(self.input_dir, "*.xyz")
        self._file_list = sorted(glob.glob(pattern))
        if not self._file_list:
            raise FileNotFoundError(f"No XYZ files found in directory: {self.input_dir}")

    # ------------------------------------------------------------------
    # STAGE 2 — LOAD AND WRAP TILES
    # ------------------------------------------------------------------
    def _load_all_tiles(self) -> None:
        """
        Load all XYZ files into XYZTile instances, estimate spacing,
        and compute coverage polygons.
        """
        self._tiles = []

        for path in self._file_list:
            df_tile = self._load_single_xyz(path)

            tile = XYZTile(
                path=path,
                points=df_tile,
                crs=self.crs,
                spacing_estimate=None,
                priority_rank=-1,
            )

            # Spacing estimation faithful to old behavior
            tile.compute_spacing_estimate(sample_size=self.sample_size_spacing)

            # Coverage polygon faithful to old XYZFileData.compute_coverage_polygon
            tile.compute_coverage_polygon(
                xy_round_decimals=self.xy_round_decimals,
            )

            self._tiles.append(tile)

    def _load_single_xyz(self, filepath: str) -> pd.DataFrame:
        """
        Load a single XYZ file into a DataFrame with columns ['x', 'y', 'z'].

        If bathy_positive_z is False, invert the sign of 'z'.
        Uses io_xyz.read_xyz to keep I/O consistent in the gis subpackage.
        """
        # Use default XYZFormatSpec inference (x, y, z without header is fine)
        df = read_xyz(filepath)

        # Ensure we have at least three columns
        expected_cols = ["x", "y", "z"]
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"File {filepath} is missing required columns: {missing}"
            )

        if not self.bathy_positive_z:
            df["z"] = -df["z"]

        return df

    # ------------------------------------------------------------------
    # STAGE 3 — PRIORITY ASSIGNMENT
    # ------------------------------------------------------------------
    def _assign_priorities_to_tiles(self) -> None:
        """
        Assign priority_rank to each tile. Rank 0 = highest priority.

        If manual_priority is provided, use its order first; remaining tiles
        are ordered by spacing (finer first), exactly as in the old version.
        """
        path_to_tile: Dict[str, Tuple[float, XYZTile]] = {
            t.path: (t.spacing_estimate if t.spacing_estimate is not None else math.inf, t)
            for t in self._tiles
        }
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
            remaining: List[Tuple[str, float]] = [
                (p, data[0]) for p, data in path_to_tile.items() if p not in rank_map
            ]
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

    # ------------------------------------------------------------------
    # STAGE 4 — MERGE USING COVERAGE POLYGONS
    # ------------------------------------------------------------------
    def _merge_tiles_respecting_priority_with_polygons(self) -> None:
        """
        Merge tiles by removing points from lower-priority tiles that fall
        within any higher-priority coverage polygon.

        The final merged DataFrame is stored in self._merged_df.
        """
        # Ensure tiles are ordered by ascending priority_rank
        self._tiles.sort(key=lambda t: t.priority_rank)

        tile_points_gdf_list: List[gpd.GeoDataFrame] = []
        tile_polygons_list: List[gpd.GeoDataFrame] = []

        for tile in self._tiles:
            gdf_points = gpd.GeoDataFrame(
                tile.points.copy(),
                geometry=gpd.points_from_xy(tile.points["x"], tile.points["y"]),
                crs=self.crs,
            )
            tile_points_gdf_list.append(gdf_points)
            tile_polygons_list.append(tile.coverage_polygon)

        trimmed_points_list: List[pd.DataFrame] = []

        for i, _ in enumerate(self._tiles):
            # Highest priority: keep all points
            if i == 0:
                trimmed_points_list.append(
                    tile_points_gdf_list[i][["x", "y", "z"]].copy()
                )
                continue

            # Combine coverage of all higher-priority tiles
            higher_priority_polys = pd.concat(
                [tile_polygons_list[j] for j in range(i)],
                ignore_index=True,
            )

            if higher_priority_polys.empty:
                trimmed_points_list.append(
                    tile_points_gdf_list[i][["x", "y", "z"]].copy()
                )
                continue

            gdf_points_i = tile_points_gdf_list[i]

            # Spatial join: mark points that fall within any higher-priority polygon
            joined = gpd.sjoin(
                gdf_points_i,
                higher_priority_polys,
                how="left",
                predicate="within",
            )

            # Keep only points not within higher-priority coverage
            keep_mask = joined["index_right"].isna()
            kept_points = joined.loc[keep_mask, ["x", "y", "z"]].copy()
            trimmed_points_list.append(kept_points)

        merged_df = pd.concat(trimmed_points_list, ignore_index=True)
        merged_df = merged_df.sort_values(by=["y", "x"]).reset_index(drop=True)
        self._merged_df = merged_df

    # ------------------------------------------------------------------
    # STAGE 5 — EXPORT
    # ------------------------------------------------------------------
    def _export_merged_xyz(self, output_xyz_path: str) -> None:
        """
        Save the merged XYZ data to disk with fixed numeric formatting.
        Uses write_xyz to stay consistent with the gis I/O layer.
        """
        if self._merged_df is None:
            raise RuntimeError("No merged data found. Run the merge pipeline before exporting.")

        # By default, write_xyz will use XYZFormatSpec() → x y z, no header, space-separated
        write_xyz(self._merged_df, output_xyz_path, float_format="%.6f")
        print(f"Merged XYZ exported to: {output_xyz_path}")
