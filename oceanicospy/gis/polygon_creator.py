import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, MultiPoint


class XYZCoverageBuilder:
    """
    Helper class to generate coverage polygons from XYZ files or existing shapefiles.

    Methods
    -------
    from_xyz(xyz_path: str) -> gpd.GeoDataFrame
        Generates a convex hull polygon from a .xyz file.

    from_shapefile(shp_path: str) -> gpd.GeoDataFrame
        Loads an existing shapefile or GeoJSON.

    export(gdf: gpd.GeoDataFrame, output_path: str) -> None
        Saves the polygon to a shapefile or GeoJSON.

    plot(gdf: gpd.GeoDataFrame) -> None
        Plots the geometry using matplotlib.
    """

    def __init__(self, xy_round_decimals: int = 3):
        self.xy_round_decimals = xy_round_decimals

    def from_xyz(self, xyz_path: str) -> gpd.GeoDataFrame:
        """
        Create a convex hull polygon from an XYZ file.
        """
        df = pd.read_csv(xyz_path, delim_whitespace=True, names=["x", "y", "z"])
        df["x"] = df["x"].round(self.xy_round_decimals)
        df["y"] = df["y"].round(self.xy_round_decimals)

        points = [Point(x, y) for x, y in zip(df["x"], df["y"])]
        multipoint = MultiPoint(points)
        polygon = multipoint.convex_hull  # Use alpha shape if needed

        return gpd.GeoDataFrame({"geometry": [polygon]}, crs="EPSG:4326")

    def from_shapefile(self, shp_path: str) -> gpd.GeoDataFrame:
        """
        Load an existing shapefile or GeoJSON.
        """
        return gpd.read_file(shp_path)

    def export(self, gdf: gpd.GeoDataFrame, output_path: str) -> None:
        """
        Export the GeoDataFrame to file (e.g. shapefile or GeoJSON).
        """
        gdf.to_file(output_path)

    def plot(self, gdf: gpd.GeoDataFrame) -> None:
        """
        Quick plot of the polygon.
        """
        gdf.plot()
        plt.show()
