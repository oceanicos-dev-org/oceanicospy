import rasterio
import geopandas as gpd
from shapely.geometry import Point

def tif_to_points_shp(tif_path, shp_path):
    """
    Convert a .tif raster to a shapefile of points (x, y, z).
    Each point corresponds to the center of a raster cell.
    """
    # Open raster
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        transform = src.transform
        
        # Generate coordinates for pixel centers
        points = []
        values = []
        for row in range(src.height):
            for col in range(src.width):
                x, y = rasterio.transform.xy(transform, row, col, offset='center')
                z = data[row, col]
                if z != src.nodata:  # exclude NoData values
                    points.append(Point(x, y))
                    values.append(z)
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({'z': values}, geometry=points, crs=src.crs)
    gdf.to_file(shp_path)
    print(f"Shapefile successfully created: {shp_path}")

