import numpy as np
from pathlib import Path

class Grid:
    def __init__(self,dx: float,dy: float,
                 x_start: float = None,x_end: float = None,
                 y_start: float = None,y_end: float = None,
                 shapefile_path: str = None,
                 xvar: bool = False):
        self.x_start = x_start
        self.x_end = x_end
        self.y_start = y_start
        self.y_end = y_end
        self.dx = dx
        self.dy = dy
        self.shapefile_path = shapefile_path
        self.xvar = xvar

        self._grid_dict = None
        self.x_2d = None
        self.y_2d = None

    @property
    def nx(self):
        if self.x_start is None or self.x_end is None:
            raise ValueError("x_start and x_end must be set before accessing nx.")
        return int((self.x_end - self.x_start)/self.dx) + 1

    @property
    def ny(self):
        if self.y_start is None or self.y_end is None:
            raise ValueError("y_start and y_end must be set before accessing ny.")
        return int((self.y_end - self.y_start)/self.dy) + 1

    def _check_epsg(self):
        pass

    def build_uniform(self):
        missing = [n for n, v in (("x_start", self.x_start), ("x_end", self.x_end),
                                   ("y_start", self.y_start), ("y_end", self.y_end)) if v is None]
        if missing:
            raise ValueError(f"Cannot build uniform grid: {', '.join(missing)} not set.")
        self._check_epsg()
        self.x_1d = np.arange(self.x_start, self.x_end + self.dx, self.dx)
        self.y_1d = np.arange(self.y_start, self.y_end + self.dy, self.dy)
        self.x_2d, self.y_2d = np.meshgrid(self.x_1d, self.y_1d)

    def build_variable(self):
        pass

    def build_from_shapefile(self,shapefile_path: str | Path):
        if not shapefile_path or not Path(shapefile_path).exists():
            raise FileNotFoundError(f"Shapefile not found at '{shapefile_path}'. "
                                    "Check input folder and name.")
        try:
            import shapefile
        except ImportError as e:
            raise ImportError(
                "PyShp (shapefile) is required for 2D grid generation. "
                "Install it via pip or conda."
            ) from e
        
        sf = shapefile.Reader(shapefile_path)
        shape = sf.shapes()[0]
        min_lon, min_lat, max_lon, max_lat = shape.bbox

        if not self.xvar:
            # Values written to file are relative to (min_lon, min_lat).
            x_points_flat = np.arange(min_lon, max_lon + self.dx, self.dx) - min_lon
            y_points_flat = np.arange(min_lat, max_lat + self.dy, self.dy) - min_lat

            self.x_2d, self.y_2d = np.meshgrid(x_points_flat, y_points_flat)
            return self.x_2d, self.y_2d
        else: 
            pass #TODO: implement xvar=True behaviour with or without segment dicts

    def export_to_grd_file(self,output_folder: str):
        x_run_path = Path(output_folder) / "x.grd"
        y_run_path = Path(output_folder) / "y.grd"

        np.savetxt(x_run_path, self.x_2d, fmt="%.4f")
        np.savetxt(y_run_path, self.y_2d, fmt="%.4f")