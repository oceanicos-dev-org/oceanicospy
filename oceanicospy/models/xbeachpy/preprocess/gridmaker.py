import numpy as np
import shutil
from pathlib import Path
from .... import utils
from ....gis import Grid

class GridMaker:
    """
    A class for creating a Xbeach computational grid from bathymetry data and filling grid information in a params file.
        
    Parameters
    ----------
    init : object
        Project initialization object with folder configuration.
    dx : float | int | list | dict | callable
        Nominal spacing definition for x-axis. By default interpreted as
        a spacing. If `as_n_cells=True` and dx is an integer > 0, it is
        interpreted as the number of cells.
    dy : float, optional
        Spacing in y-direction for 2D grids.
    end_x_point : float, optional
        Nominal profile length when working in 1D.
    start_xy, end_xy : tuple(float, float), optional
        Planar coordinates of the profile start and end points.
    auto_extend : bool, optional
        If True (default), the final coordinate of the profile is extended
        so that the last cell length matches the last dx used in the grid
        generation. If False, the final coordinate is forced to match the
        nominal end_x_point.
    as_n_cells : bool, optional
        If True, and `dx` is an integer > 0, `dx` is interpreted as the
        number of divisions of the profile. If False (default), `dx` is
        interpreted as a spacing.
    profile_csv : str, optional
        Filename of a CSV file in the input folder containing the profile 
        coordinates. 

    Notes
    -----
    - auto_extend and as_n_cells are passed into _build_variable_dx_axis().

    """

    def __init__(
        self,
        init,
        dx,
        dy=None,
        end_x_point=None,
        start_xy=None,
        end_xy=None,
        auto_extend=True,
        as_n_cells=False,
        profile_csv=None,
        *args,
        **kwargs
        ):

        self.init = init
        self.dx = dx
        self.dy = dy
        self.end_x_point = end_x_point
        self.auto_extend = auto_extend
        self.as_n_cells = as_n_cells
        self.profile_csv = profile_csv 
        self._grid_dict = None

        # Store planar coordinates
        self.start_xy = np.array(start_xy, dtype=float) if start_xy is not None else None
        self.end_xy = np.array(end_xy, dtype=float) if end_xy is not None else None
        self.final_end_xy = None

        # Compute profile length if planar coordinates were provided and end_x_point was not set by the user
        if self.start_xy is not None and self.end_xy is not None and self.end_x_point is None:
            self.end_x_point = float(np.linalg.norm(self.end_xy - self.start_xy))

    @property
    def metadata(self):
        """
        Return the grid metadata dictionary that would be used to fill the grid section in params.txt.
        This is useful for inspection or testing purposes after grid generation.

        Returns
        -------
        dict or None
            The grid metadata dictionary with keys 'xfilepath', 'yfilepath', 'meshes_x', 'meshes_y',
            or None if the grid has not been generated yet.
        """
        return self._grid_dict

    def _load_existing_grid(self):
        """
        Load an existing grid from the configured input folder, validate it, copy the files into the run folder,
        and return a small descriptor dictionary.

        The function distinguishes between 1D and 2D profiles based on the dimensionality of the loaded y array:
        - For a 1D profile (y.ndim == 1) meshes_x is computed as len(x) - 1 and meshes_y is set to 0.
        - For a 2D profile (y.ndim == 2) meshes_x is computed as number of columns in x minus 1 and
            meshes_y as number of rows in y minus 1.

        Returns
        -------
        dict or None
            Returns None if fewer than two '.grd' files are found in the input folder.
            Otherwise, returns a dictionary containing:
                - `xfilepath` : str
                    Standardized filename for the x-grid inside the run folder.
                - `yfilepath` : str
                    Standardized filename for the y-grid inside the run folder.
                - `meshes_x`  : int
                    Number of mesh intervals in the x direction. Computed as:
                    - (n_columns - 1) for 2-D grids.
                    - (n_points - 1) for 1-D grids.
                - `meshes_y`  : int
                    Number of mesh intervals in the y direction. Computed as:
                    - (n_rows - 1) for 2-D grids.
                    - 0 for 1-D grids.

        Raises
        ------
        ValueError
            If the loaded x and y arrays do not have the same shape.

        Notes
        -----
        - Grid dimensionality is inferred automatically: if the loaded arrays are
        2-dimensional, the grid is treated as 2-D; otherwise, it is treated as 1-D.
        - The first two '.grd' files discovered in the input folder are used. If more
        than two files exist, no additional filtering is performed.
        - The copied grids inside the run folder always use the filenames
        'x_profile.grd' and 'y_profile.grd', regardless of the original names.
        - Numeric loading assumes plain-text grid files compatible with `numpy.loadtxt`.
        """

        input_folder = Path(self.init.dict_folders["input"])
        run_folder = Path(self.init.dict_folders["run"])
   
        fixed_x = input_folder / "x_profile.grd"
        fixed_y = input_folder / "y_profile.grd"

        if fixed_x.exists() and fixed_y.exists():
            x_file = fixed_x
            y_file = fixed_y
        else:
            grd_files = list(input_folder.glob("*.grd"))
            if len(grd_files) < 2:
                return None

            # Select first two files assuming they are in order (no additional checks)
            x_file = grd_files[0]
            y_file = grd_files[1]

        # Load arrays
        x = np.loadtxt(x_file)
        y = np.loadtxt(y_file)

        if x.shape != y.shape:
            raise ValueError("Loaded .grd files do not have matching shapes.")

        # Detect 1-D or 2-D
        is_2d = (x.ndim == 2)

        meshes_x = x.shape[1] - 1 if is_2d else x.shape[0] - 1
        meshes_y = x.shape[0] - 1 if is_2d else 0

        # Copy to run folder with standardized filenames
        dest_x = run_folder / "x.grd"
        dest_y = run_folder / "y.grd"

        shutil.copy(str(x_file), str(dest_x))
        shutil.copy(str(y_file), str(dest_y))

        grid_dict = {
            'xfilepath': 'x.grd',
            'yfilepath': 'y.grd',
            'meshes_x': meshes_x,
            'meshes_y': meshes_y
        }

        return grid_dict

    def profile_1d(self):
        pass

    def build_rectangular_grid(
            self,
            source_file=None,
            xvar=False
        ):
        
        existing = self._load_existing_grid()
        if existing is not None:
            return existing

        input_folder = self.init.dict_folders["input"]
        run_folder = self.init.dict_folders["run"]
        dims = self.init.dict_ini_data.get("dims")

        if str(dims) == "2":
            if getattr(self, "dy", None) is None:
                self.dy = self.dx

            # A shapefile source is required for 2D grids
            if source_file is None or not source_file.endswith(".shp"):
                raise ValueError(
                    "For 2D grids (dims == 2) you must provide a shapefile"
                )

            grid = Grid(dx=self.dx, dy=self.dy, xvar=xvar)
            shp_path = Path(input_folder) / source_file
            x_2d, y_2d = grid.build_from_shapefile(shp_path)
            grid.export_to_grd_file(run_folder)

            self._grid_dict = {
                "xfilepath": "x.grd",
                "yfilepath": "y.grd",
                "meshes_x": x_2d.shape[1] - 1, # number of columns - 1
                "meshes_y": y_2d.shape[0] - 1, # number of rows - 1
            }

        else:
            raise ValueError(f"Unsupported dims value: {dims}. Expected 2 dimensions.")

        


    def fill_grid_section(self):
        if self._grid_dict is None:
            raise ValueError("Grid has not been generated yet. Call a grid generation method first.")
        print ('\n*** Adding/Editing grid information in params file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',self._grid_dict)