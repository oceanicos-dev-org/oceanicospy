import numpy as np
import os
import glob
import shutil
from pathlib import Path
import shapefile
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from itertools import zip_longest
from .. import utils

class GridMaker():
    """
    A class for creating a Xbeach computational grid from bathymetry data and filling grid information in a params file.
    Args:
        root_path (str): The root path of the project.
        dx (float): The grid spacing in the x-direction.
        dy (float): The grid spacing in the y-direction.

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
        """
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

        Notes
        -----
        - auto_extend and as_n_cells are passed into _build_variable_dx_axis().
        """

        self.init = init
        self.dx = dx
        self.dy = dy
        self.end_x_point = end_x_point

        self.auto_extend = auto_extend
        self.as_n_cells = as_n_cells
        self.profile_csv = profile_csv 
        # Store planar coordinates
        self.start_xy = np.array(start_xy, dtype=float) if start_xy is not None else None
        self.end_xy = np.array(end_xy, dtype=float) if end_xy is not None else None

        self.final_end_xy = None

        # Compute profile length if planar coordinates were provided
        if self.start_xy is not None and self.end_xy is not None and self.end_x_point is None:
            self.end_x_point = float(np.linalg.norm(self.end_xy - self.start_xy))

    def load_existing_grid(self):
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
                - 'xfilepath' : str
                    Standardized filename for the x-grid inside the run folder.
                - 'yfilepath' : str
                    Standardized filename for the y-grid inside the run folder.
                - 'meshes_x'  : int
                    Number of mesh intervals in the x direction. Computed as:
                    - (n_columns - 1) for 2-D grids.
                    - (n_points - 1) for 1-D grids.
                - 'meshes_y'  : int
                    Number of mesh intervals in the y direction. Computed as:
                    - (n_rows - 1) for 2-D grids.
                    - 0 for 1-D grids.
                - None if either "x_profile.grd" or "y_profile.grd" does not exist in the input folder.
                - On success, a dictionary with keys:
                        'xfilepath' : 'x_profile.grd'  (filename as placed in the run folder)
                        'yfilepath' : 'y_profile.grd'
                        'meshes_x'  : int (number of x meshes = number_of_x_points - 1)
                        'meshes_y'  : int (number of y meshes = number_of_y_points - 1, or 0 for 1D profiles)

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
        - Numeric loading assumes plain-text grid files compatible with numpy.loadtxt.
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

            # Select first two files
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
        dest_x = run_folder / "x_profile.grd"
        dest_y = run_folder / "y_profile.grd"

        shutil.copy(str(x_file), str(dest_x))
        shutil.copy(str(y_file), str(dest_y))

        grid_dict = {
            'xfilepath': 'x_profile.grd',
            'yfilepath': 'y_profile.grd',
            'meshes_x': meshes_x,
            'meshes_y': meshes_y
        }

        return grid_dict
    
    def cumulative_distance(self, dist_segments, up_to_segment):
        """
        Compute cumulative distances in x and y up to a given segment (inclusive).

        Parameters
        ----------
        dist_segments : dict
            Dictionary like {'1': {'x': 840, 'y': 760}, '2': {'x': 50, 'y': 70}, ...}
        up_to_segment : str or int
            Segment key up to which distances are accumulated.

        Returns
        -------
        dict
            {'x': total_x, 'y': total_y}
        """

        total_x = 0.0
        total_y = 0.0

        # Numeric ordering of segment keys
        for key in sorted(dist_segments.keys(), key=lambda k: int(k)):
            seg = dist_segments[key]

            total_x += seg['x']
            total_y += seg['y']

            if str(key) == str(up_to_segment):
                break

        return {'x': total_x, 'y': total_y}

    
    def _build_variable_dx_axis(
        self,
        start: float,
        end: float,
        dx_spec,
        auto_extend: bool = True,
        as_n_cells: bool = False,
    ):
        """
        Build a 1D axis with flexible dx definition.

        Parameters
        ----------
        start : float
            Starting coordinate (usually 0).
        end : float
            Nominal end coordinate (e.g., self.end_x_point).
        dx_spec : float | int | list | tuple | np.ndarray | dict | callable
            Defines how dx varies along the axis:
            - float / int:
                * By default, interpreted as a spacing (dx).
                * If `as_n_cells=True` and dx_spec is an int > 0, it is
                  interpreted as the number of cells (N) between start and end.
            - list / tuple / np.ndarray:
                Sequence of spacings. They are applied in order until the
                nominal length is covered. The last spacing is used to
                adjust the final point if `auto_extend=True`.
            - dict:
                Piecewise-constant spacing definition {x_to: dx}. Spacings
                are applied segment by segment until the nominal length is
                covered. The last spacing is used to adjust the final point
                if `auto_extend=True`.
            - callable:
                Function f(x_current) -> dx. The last dx produced by the
                function is used to adjust the final point if
                `auto_extend=True`.

        auto_extend : bool, optional
            If True (default), when the accumulated length does not land
            exactly on `end`, the final coordinate is extended in the same
            direction using the LAST spacing value. This guarantees that
            the last cell length is equal to the last dx that was used.
            If False, the last coordinate is forced to be equal to `end`
            (original behavior), which may produce a shorter last cell.

        as_n_cells : bool, optional
            If True and `dx_spec` is an integer > 0, `dx_spec` is interpreted
            as the number of cells (N) in the interval [start, end], and the
            grid will have N+1 points exactly between start and end (no
            extension and `end` is exact).
            If False (default), `dx_spec` is always interpreted as a spacing,
            even if it is an integer.

        Returns
        -------
        np.ndarray
            Array of coordinates along the axis.

        Notes
        -----
        - In all cases, `self.end_x_point` is updated to reflect the ACTUAL
          length of the constructed axis (`x[-1] - start`).
        - With `auto_extend=True`, the final coordinate is allowed to be
          greater than the nominal `end`, so that the last interval length
          equals the last dx that was used.
        """

        x = [start]
        length = end - start

        # ---------------------------------------------------------------------
        # 1) Optional "number of cells" interpretation (explicit opt-in)
        #    - Only used when as_n_cells=True AND dx_spec is an integer.
        #    - In this mode, we do NOT extend the axis: the last coordinate is
        #      exactly `end`, and we simply divide [start, end] into N cells.
        # ---------------------------------------------------------------------
        if as_n_cells and isinstance(dx_spec, int) and dx_spec > 0:
            n_cells = dx_spec
            dx = (end - start) / n_cells
            coords = start + np.arange(0, n_cells + 1) * dx
            self.end_x_point = coords[-1] - start  # should be equal to length
            return coords

        # ---------------------------------------------------------------------
        # 2) Default: dx_spec is interpreted as a spacing (dx), even if it is
        #    an integer. This is the main branch for uniform grids.
        # ---------------------------------------------------------------------
        if isinstance(dx_spec, (int, float)):
            dx = float(dx_spec)
            if dx <= 0.0:
                raise ValueError("dx must be positive.")

            if auto_extend:
                # length is an integer multiple of dx. This may produce a
                # final coordinate > end.
                n_cells = int(np.ceil(length / dx)) if length > 0 else 1
                if n_cells < 1:
                    n_cells = 1
                coords = start + np.arange(0, n_cells + 1) * dx
            else:
                # keep end as the nominal last coordinate,
                # which may create a shorter last cell.
                coords = np.arange(start, end, dx)
                if coords.size == 0 or coords[-1] < end:
                    coords = np.append(coords, end)

            self.end_x_point = coords[-1] - start
            return coords

        # ---------------------------------------------------------------------
        # 3) List / tuple / ndarray of explicit dx values
        #    - By default (auto_extend=True), the final point is adjusted
        #      so that the last cell length equals the last dx that was used.
        # ---------------------------------------------------------------------
        elif isinstance(dx_spec, (list, tuple, np.ndarray)):
            last_dx = None
            target = start + length  # nominal end in absolute coordinates

            for raw_dx in dx_spec:
                dx = float(raw_dx)
                if dx <= 0.0:
                    raise ValueError("All dx values must be positive.")
                last_dx = dx

                next_x = x[-1] + dx

                # When the next point would reach or exceed the nominal end
                if next_x >= target:
                    if auto_extend:
                        x.append(next_x)
                    else:
                        # Original behavior: force exact nominal end
                        x.append(target)
                    break
                else:
                    x.append(next_x)

            # If we ran out of dx_spec values but still haven't reached `end`
            if x[-1] < target:
                if auto_extend and last_dx is not None:
                    while x[-1] + last_dx < target:
                        x.append(x[-1] + last_dx)
                    x.append(x[-1] + last_dx)
                else:
                    x.append(target)

            coords = np.array(x)
            self.end_x_point = coords[-1] - start
            return coords

        # ---------------------------------------------------------------------
        # 4) Piecewise-constant dx defined by a dict {x_to: dx}
        #    - Each entry is interpreted as: "from current x until x_to, use dx".
        #    - With auto_extend=True, the last segment is extended using the
        #      last dx and is allowed to overshoot `end`.
        # ---------------------------------------------------------------------
        elif isinstance(dx_spec, dict):
            last_dx = None
            target = start + length  # nominal end in absolute coordinates

            for x_to, raw_dx in sorted(dx_spec.items()):
                dx = float(raw_dx)
                if dx <= 0.0:
                    raise ValueError("All dx values in dict must be positive.")
                last_dx = dx

                segment_end = min(x_to, target)

                # Step within this segment with constant dx
                while x[-1] + dx < segment_end:
                    x.append(x[-1] + dx)

                # If the next step would reach or exceed the nominal end
                if x[-1] + dx >= target:
                    if auto_extend:
                        x.append(x[-1] + dx)
                    else:
                        x.append(target)
                    break

                # Otherwise, we reached x_to but not yet the global target;
                # move on to the next dict entry
                if x[-1] < target and segment_end == x_to:
                    # Do nothing special here; next iteration will continue
                    continue

            # If dict definition ended before reaching nominal end
            if x[-1] < target:
                if auto_extend and last_dx is not None:
                    while x[-1] + last_dx < target:
                        x.append(x[-1] + last_dx)
                    x.append(x[-1] + last_dx)
                else:
                    # Original behavior: force last point to nominal end
                    x.append(target)

            coords = np.array(x)
            self.end_x_point = coords[-1] - start
            return coords

        # ---------------------------------------------------------------------
        # 5) Callable dx = f(x)
        #    - f(x_current) must return a positive spacing.
        #    - With auto_extend=True, the last step uses the full dx and is
        #      allowed to overshoot end.
        # ---------------------------------------------------------------------
        elif callable(dx_spec):
            target = start + length  # nominal end in absolute coordinates

            while True:
                dx = float(dx_spec(x[-1]))
                if dx <= 0.0:
                    raise ValueError("dx function returned non-positive value.")
                next_x = x[-1] + dx

                if next_x >= target:
                    if auto_extend:
                        x.append(next_x)
                    else:
                        x.append(target)
                    break

                x.append(next_x)

            coords = np.array(x)
            self.end_x_point = coords[-1] - start
            return coords

        else:
            raise TypeError(
                "dx_spec must be float, int, list, tuple, np.ndarray, dict, "
                "callable, or an int > 0 when used with as_n_cells=True."
            )


    def rectangular(
            self,
            source_file=None,
            xvar=False,
            start_segments=None,
            dist_segments=None,
            delta_segments=None
        ):
        """

        This method:
        - Adds 1D profile support (with optional planar coordinates) and
        segmented 2D grids with scalar segment definitions.
        - Automatically chooses the appropriate behaviour based on `dims` and the
        structure of the segment dictionaries, without exposing explicit
        "old/new" mode flags to the user.

        Parameters
        ----------
        source_file : str, optional
            Name of an input file used to derive the grid extent.
            - If dims == '1' or 1 and source_file is None:
                A 1-D profile is created using `self.end_x_point` and `self.dx`
                (or using planar coordinates `self.start_xy` / `self.end_xy`
                if provided).
            - If dims != '1' and the filename ends with '.shp':
                The first shape in the shapefile located at
                self.init.dict_folders['input'] / source_file is read and its
                bounding box (min_lon, min_lat, max_lon, max_lat) is used to
                construct a 2-D rectangular grid.

        xvar : bool, optional
            For 2-D grids only.
            - If False (default), builds a uniform grid in both x and y directions.
            - If True and the segment dictionaries contain nested {'x','y'} entries.
            - If True and the segment dictionaries contain scalar values, a modern
            segmented x-direction grid with uniform y is built.

        start_segments : dict, optional
            Segment starting positions for x-direction when xvar=True.

        dist_segments : dict, optional
            Segment lengths for each segment when xvar=True. If the values are
            dict-like with keys {'x','y'}.

        delta_segments : dict, optional
            Grid spacings for each segment when xvar=True. If the values are
            dict-like with keys {'x','y'}.

        Returns
        -------
        dict
            For 1-D grids:
                - 'xfilepath' : 'x_profile.grd'
                - 'yfilepath' : 'y_profile.grd'
                - 'meshes_x'  : number of cells in x-direction
                - 'meshes_y'  : 0

            For 2-D grids:
                - 'xfilepath' : 'x.grd'
                - 'yfilepath' : 'y.grd'
                - 'meshes_x'  : number of cells in x-direction
                - 'meshes_y'  : number of cells in y-direction
        
        Notes
        -----
        Step 0:
            If at least two '.grd' files already exist in the input folder, the
            method standardizes their names to 'x.grd' and 'y.grd' in both input
            and run folders and returns immediately, assuming the user provided
            an existing grid.

        Step 1 (dims == '1'):
            - If planar coordinates (start_xy and end_xy) are available, a 1-D
            profile is created along the straight line between these points.
            x_profile.grd stores the local coordinate s = [0, dx, 2dx, ...];
            y_profile.grd stores zeros. The actual planar end point reached
            after applying dx and auto_extend/as_n_cells is stored in
            self.final_end_xy.
            - Otherwise, a 1-D profile in x-only is created from 0 to end_x_point.

        Step 2 (dims != '1'):
            - If dy is None, it is set to dx.
            - A shapefile is required and its bounding box is used to define the
            grid extent.
            - If xvar=False, a uniform grid is created.
            - If xvar=True:
                * If dist_segments[seg] are dicts with keys {'x','y'}.
                * Otherwise, a simpler modern segmented x-grid with uniform y is
                built.

        Raises
        ------
        AttributeError
            If required attributes on self are missing.

        FileNotFoundError
            If a shapefile is requested but cannot be found.

        ValueError
            If provided spacings are invalid, or required inputs for a given mode
            are missing.
        """

        # ----------------------------------------------------------------------
        # Step 0: check for pre-existing .grd files in the input folder.
        # If found (>= 2 files), standardize their names and return them,
        # keeping backwards compatibility with workflows that supply grids.
        # ----------------------------------------------------------------------
        input_folder = self.init.dict_folders["input"]
        run_folder = self.init.dict_folders["run"]

        grd_files = glob.glob(os.path.join(input_folder, "*.grd"))

        if len(grd_files) >= 2:
            # Try to infer x and y files by name; fall back to the first two.
            xfile = None
            yfile = None

            for f in grd_files:
                fname = os.path.basename(f).lower()
                if "x" in fname and xfile is None:
                    xfile = f
                elif "y" in fname and yfile is None:
                    yfile = f

            if xfile is None:
                xfile = grd_files[0]
            if yfile is None:
                yfile = grd_files[1]

            # Standardized filenames in both input and run folders
            x_input_path = os.path.join(input_folder, "x.grd")
            y_input_path = os.path.join(input_folder, "y.grd")
            x_run_path = os.path.join(run_folder, "x.grd")
            y_run_path = os.path.join(run_folder, "y.grd")

            shutil.copy(xfile, x_input_path)
            shutil.copy(yfile, y_input_path)
            shutil.copy(xfile, x_run_path)
            shutil.copy(yfile, y_run_path)
            # Load grids to compute mesh sizes 
            x = np.loadtxt(x_input_path)
            y = np.loadtxt(y_input_path)

            is_2d = (x.ndim == 2)
            meshes_x = x.shape[1] - 1 if is_2d else x.shape[0] - 1
            meshes_y = x.shape[0] - 1 if is_2d else 0

            return {
                "xfilepath": "x.grd",
                "yfilepath": "y.grd",
                "meshes_x": meshes_x,
                "meshes_y": meshes_y,
            }

        # ----------------------------------------------------------------------
        # Step 1: no pre-existing grid – build a new one.
        # ----------------------------------------------------------------------
        auto_extend_flag = getattr(self, "auto_extend", True)
        as_n_cells_flag = getattr(self, "as_n_cells", False)

        dims = self.init.dict_ini_data.get("dims")

        # ======================================================================
        # 1D CASE
        # ======================================================================
        if str(dims) == "1":
            if self.profile_csv is None:
                raise ValueError("No planar coordinates provided and no 'profile_csv' specified.")

            input_folder = Path(self.init.dict_folders["input"])
            profile_path = input_folder / self.profile_csv

            if not profile_path.exists():
                raise FileNotFoundError(f"Specified profile file '{self.profile_csv}' not found in input folder.")

            arr = np.loadtxt(profile_path, delimiter=",", skiprows=1)
            if arr.shape[1] < 2:
                raise ValueError(f"File '{self.profile_csv}' must contain at least two columns (x, z).")

            # --------------------------------------------------------------
            # 1D profile grid
            # --------------------------------------------------------------
            start_xy = getattr(self, "start_xy", None)
            end_xy = getattr(self, "end_xy", None)

            if start_xy is not None and end_xy is not None:
                # Vector between planar points
                vec = end_xy - start_xy
                L_geom = float(np.linalg.norm(vec))

                if L_geom == 0.0:
                    raise ValueError(
                        "start_xy and end_xy are identical; profile length is zero."
                    )

                # If user did not set end_x_point, use geometric length
                if getattr(self, "end_x_point", None) is None:
                    self.end_x_point = L_geom

                # Build the curvilinear s-axis with flexible dx specification
                s_axis = self._build_variable_dx_axis(
                    start=0.0,
                    end=self.end_x_point,
                    dx_spec=self.dx,
                    auto_extend=auto_extend_flag,
                    as_n_cells=as_n_cells_flag,
                )

                # Unit direction vector along the line
                direction = vec / L_geom

                # Local 1D coordinates: x = s, y = 0
                x_points = s_axis.copy()
                y_points = np.zeros_like(s_axis)

                # Store adjusted final planar coordinate
                self.final_end_xy = (
                    float(start_xy[0] + direction[0] * s_axis[-1]),
                    float(start_xy[1] + direction[1] * s_axis[-1]),
                )

                grid_dict = {
                    "xfilepath": "x_profile.grd",
                    "yfilepath": "y_profile.grd",
                    "meshes_x": len(x_points) - 1,
                    "meshes_y": 0,
                }

            else:
                # Load the x,z profile to infer the end_x_point
                arr = np.loadtxt(profile_path, delimiter=",", skiprows=1)
                x_values = arr[:, 0]

                x_values = arr[:, 0]
                if x_values.size < 2:
                    raise ValueError("Profile file must contain at least two x values.")

                # Estimate length from x[0] to x[-1]
                x0 = float(x_values[0])
                x1 = float(x_values[-1])
                length = abs(x1 - x0)

                if getattr(self, "end_x_point", None) is None:
                    self.end_x_point = length

                start_x_point = 0.0

                x_points = self._build_variable_dx_axis(
                    start=start_x_point,
                    end=self.end_x_point,
                    dx_spec=self.dx,
                    auto_extend=auto_extend_flag,
                    as_n_cells=as_n_cells_flag,
                )
                y_points = np.zeros_like(x_points)


                grid_dict = {
                    "xfilepath": "x_profile.grd",
                    "yfilepath": "y_profile.grd",
                    "meshes_x": len(x_points) - 1,
                    "meshes_y": 0,
                }

            # ------------------------------------------------------------------
            # Save 1D grid in both run and input folders and return
            # ------------------------------------------------------------------
            x_run_path = os.path.join(run_folder, grid_dict["xfilepath"])
            y_run_path = os.path.join(run_folder, grid_dict["yfilepath"])
            x_input_path = os.path.join(input_folder, grid_dict["xfilepath"])
            y_input_path = os.path.join(input_folder, grid_dict["yfilepath"])

            np.savetxt(x_run_path, x_points, fmt="%.4f")
            np.savetxt(y_run_path, y_points, fmt="%.4f")
            np.savetxt(x_input_path, x_points, fmt="%.4f")
            np.savetxt(y_input_path, y_points, fmt="%.4f")

            return grid_dict

        # ======================================================================
        # 2D CASE
        # ======================================================================
        # Ensure dy is defined
        if getattr(self, "dy", None) is None:
            self.dy = self.dx

        # A shapefile source is required for 2D grids
        if source_file is None or not source_file.endswith(".shp"):
            raise ValueError(
                "For 2D grids (dims != '1') you must provide a shapefile "
                "source_file ending with '.shp'."
            )

        shp_path = os.path.join(input_folder, source_file)
        if not os.path.exists(shp_path):
            raise FileNotFoundError(
                f"Shapefile not found at '{shp_path}'. Check input folder and name."
            )

        sf = shapefile.Reader(shp_path)
        shape = sf.shapes()[0]
        min_lon, min_lat, max_lon, max_lat = shape.bbox

        # ----------------------------------------------------------------------
        # Branch 1: uniform grid (xvar = False)  
        # ----------------------------------------------------------------------
        if not xvar:
            # Values written to file are relative to (min_lon, min_lat).
            x_points_flat = np.arange(min_lon, max_lon + self.dx, self.dx) - min_lon
            y_points_flat = np.arange(min_lat, max_lat + self.dy, self.dy) - min_lat

            x_points, y_points = np.meshgrid(x_points_flat, y_points_flat)

            grid_dict = {
                "xfilepath": "x.grd",
                "yfilepath": "y.grd",
                "meshes_x": x_points.shape[1] - 1,
                "meshes_y": y_points.shape[0] - 1,
            }

            x_run_path = os.path.join(run_folder, grid_dict["xfilepath"])
            y_run_path = os.path.join(run_folder, grid_dict["yfilepath"])
            x_input_path = os.path.join(input_folder, grid_dict["xfilepath"])
            y_input_path = os.path.join(input_folder, grid_dict["yfilepath"])

            np.savetxt(x_run_path, x_points, fmt="%.4f")
            np.savetxt(y_run_path, y_points, fmt="%.4f")
            np.savetxt(x_input_path, x_points, fmt="%.4f")
            np.savetxt(y_input_path, y_points, fmt="%.4f")

            return grid_dict

        # ----------------------------------------------------------------------
        # Branch 2: xvar = True → segmented grids
        # - If segment dicts have {'x','y'}.
        # - Else → grid in x, uniform in y.
        # ----------------------------------------------------------------------
        if start_segments is None or dist_segments is None or delta_segments is None:
            raise ValueError(
                "When xvar=True you must provide 'start_segments', "
                "'dist_segments' and 'delta_segments' dictionaries."
            )

        is_xy_segmented = False
        if isinstance(dist_segments, dict):
            try:
                first_val = next(iter(dist_segments.values()))
                if isinstance(first_val, dict) and "x" in first_val and "y" in first_val:
                    is_xy_segmented = True
            except StopIteration:
                pass

        # ----------------------------------------------------------------------
        # 2A. 
        # ----------------------------------------------------------------------
        if is_xy_segmented:
            list_x_points_flat_all = []
            list_y_points_flat_all = []

            # Build per-segment x,y arrays
            for segment in sorted(start_segments.keys(), key=int):
                if segment == "1":
                    x_points_flat_seg = (
                        np.arange(
                            min_lon,
                            (min_lon + dist_segments[segment]["x"])
                            + delta_segments[segment]["x"],
                            delta_segments[segment]["x"],
                        )
                        - min_lon
                    )
                    y_points_flat_seg = (
                        np.arange(
                            min_lat,
                            (min_lat + dist_segments[segment]["y"])
                            + delta_segments[segment]["y"],
                            delta_segments[segment]["y"],
                        )
                        - min_lat
                    )
                else:
                    cum_distance_x = self.cumulative_distance(dist_segments, segment)["x"]
                    cum_distance_y = self.cumulative_distance(dist_segments, segment)["y"]

                    cum_distance_x_minus1 = self.cumulative_distance(
                        dist_segments, f"{int(segment) - 1}"
                    )["x"]
                    cum_distance_y_minus1 = self.cumulative_distance(
                        dist_segments, f"{int(segment) - 1}"
                    )["y"]

                    x_points_flat_seg = (
                        np.arange(
                            min_lon
                            + cum_distance_x_minus1
                            + delta_segments[segment]["x"],
                            min_lon + cum_distance_x + delta_segments[segment]["x"],
                            delta_segments[segment]["x"],
                        )
                        - min_lon
                    )
                    y_points_flat_seg = (
                        np.arange(
                            min_lat
                            + cum_distance_y_minus1
                            + delta_segments[segment]["y"],
                            min_lat + cum_distance_y + delta_segments[segment]["y"],
                            delta_segments[segment]["y"],
                        )
                        - min_lat
                    )

                list_x_points_flat_all.append(x_points_flat_seg)
                list_y_points_flat_all.append(y_points_flat_seg)

            x_points_flat = np.concatenate(list_x_points_flat_all)
            y_points_flat = np.concatenate(list_y_points_flat_all)

            x_points_flat_10m = np.arange(min_lon, max_lon + self.dx, self.dx) - min_lon
            y_points_flat_10m = np.arange(min_lat, max_lat + self.dy, self.dy) - min_lat

            # Write x.grd following original row-based switching logic
            out_path_x = os.path.join(run_folder, "x.grd")

            def _one_line(arr):
                arr_np = np.asarray(arr).flatten()
                return " ".join(f"{float(v):.4f}" for v in arr_np)

            with open(out_path_x, "w") as fh:
                for element in y_points_flat:
                    if element <= 350:
                        line = _one_line(x_points_flat_10m)
                    elif 350 < element <= 420:
                        line = _one_line(x_points_flat)
                    else:
                        line = _one_line(x_points_flat_10m)
                    fh.write(line + "\n")

            # Build list of y rows using original switching logic
            list_y_points = []
            for element in x_points_flat:
                if element <= 110:
                    list_y_points.append(y_points_flat_10m)
                elif 110 < element <= 160:
                    list_y_points.append(y_points_flat)
                else:
                    list_y_points.append(y_points_flat_10m)

            out_path_y = os.path.join(run_folder, "y.grd")
            with open(out_path_y, "w") as f:
                for col in zip_longest(*list_y_points, fillvalue=""):
                    formatted = (
                        f"{float(v):12.4f}" if v != "" else " " * 12 for v in col
                    )
                    f.write("".join(formatted) + "\n")

            # Optional: build shapefile of grid points (original behaviour)
            geometry = []
            with open(out_path_x, "r") as file_x, open(out_path_y, "r") as file_y:
                for line_x, line_y in zip(file_x, file_y):
                    x_vals = [float(v) for v in line_x.split()] if line_x.strip() else []
                    y_vals = [float(v) for v in line_y.split()] if line_y.strip() else []

                    if len(x_vals) <= len(y_vals):
                        y_vals = y_vals[: len(x_vals)]
                    elif len(y_vals) < len(x_vals) and len(y_vals) > 0:
                        y_vals = y_vals + [y_vals[-1]] * (len(x_vals) - len(y_vals))

                    for xv, yv in zip(x_vals, y_vals):
                        geometry.append(Point(xv + min_lon, yv + min_lat))

            if geometry:
                coords = [(pt.x, pt.y) for pt in geometry]
                df = pd.DataFrame(
                    {"x": [c[0] for c in coords], "y": [c[1] for c in coords]}
                )
                gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:9377")
                out_shp = os.path.join(
                    input_folder, "XBeach_domain_grid_points_reef_MSON.shp"
                )
                gdf.to_file(out_shp)

            # Also copy grid files to input folder for consistency
            shutil.copy(out_path_x, os.path.join(input_folder, "x.grd"))
            shutil.copy(out_path_y, os.path.join(input_folder, "y.grd"))


            x = np.loadtxt(out_path_x)
            y = np.loadtxt(out_path_y)

            is_2d = (x.ndim == 2)
            meshes_x = x.shape[1] - 1 if is_2d else x.shape[0] - 1
            meshes_y = x.shape[0] - 1 if is_2d else 0

            grid_dict = {
                "xfilepath": "x.grd",
                "yfilepath": "y.grd",
                "meshes_x": meshes_x,
                "meshes_y": meshes_y,
            }
            return grid_dict

        # ----------------------------------------------------------------------
        # 2B. 
        # ----------------------------------------------------------------------
        list_x_segments = []
        for seg_key in start_segments.keys():
            start_val = start_segments[seg_key]
            dist_val = dist_segments[seg_key]
            dx_seg = delta_segments[seg_key]

            end_val = start_val + dist_val
            # Use open interval [start_val, end_val) to avoid overlapping cells
            x_seg = np.arange(start_val, end_val, dx_seg)
            list_x_segments.append(x_seg)

        x_points_flat = np.unique(np.concatenate(list_x_segments))
        y_points_flat = np.arange(min_lat, max_lat + self.dy, self.dy) - min_lat

        x_points, y_points = np.meshgrid(x_points_flat, y_points_flat)

        grid_dict = {
            "xfilepath": "x.grd",
            "yfilepath": "y.grd",
            "meshes_x": x_points.shape[1] - 1,
            "meshes_y": y_points.shape[0] - 1,
        }

        x_run_path = os.path.join(run_folder, grid_dict["xfilepath"])
        y_run_path = os.path.join(run_folder, grid_dict["yfilepath"])
        x_input_path = os.path.join(input_folder, grid_dict["xfilepath"])
        y_input_path = os.path.join(input_folder, grid_dict["yfilepath"])

        np.savetxt(x_run_path, x_points, fmt="%.4f")
        np.savetxt(y_run_path, y_points, fmt="%.4f")
        np.savetxt(x_input_path, x_points, fmt="%.4f")
        np.savetxt(y_input_path, y_points, fmt="%.4f")

        return grid_dict
            


    # def params_2D_from_xyz(self):
    #     bathy_xyz_path = glob.glob(f'{self.init.dict_folders["input"]}bathy*.csv')[0]
    #     df_xyz = pd.read_csv(bathy_xyz_path)

    #     # compute the grid extents
    #     min_x,max_x = df_xyz['Y'].min(), df_xyz['Y'].max() # It depends and how the columns are originally named*
    #     min_y,max_y = df_xyz['X'].min(), df_xyz['X'].max()

    #     # Compute the number of grid cells
    #     nx_bathy = int((min_x - max_x)/self.dx)
    #     ny_bathy = int((max_y - min_y)/self.dy)

    #     # Generate grid with data
    #     xi, yi = np.mgrid[min_x:max_x:(nx_bathy+1)*1j, min_y:max_y:(ny_bathy+1)*1j]  # Caution
    #     yi_to_write = (xi.T-xi[0,0])*110000
    #     xi_to_write = (yi.T-yi[0,0])*110000

    #     np.savetxt(f'{self.init.dict_folders["run"]}x_profile.grd',yi_to_write,fmt='%f')
    #     np.savetxt(f'{self.init.dict_folders["run"]}y_profile.grd',xi_to_write,fmt='%f')

    #     grid_dict={'xfilepath':'x_profile.grd','yfilepath':'y_profile.grd','meshes_x':len(xi[:,0])-1,'meshes_y':len(yi[0,:])-1}
    #     for key,value in grid_dict.items():
    #         grid_dict[key]=str(value)
    #     return grid_dict        

    # def params_1D_from_bathy(self):
    #     dat_files=glob.glob(f'{self.dict_folders["input"]}*.dat')
    #     print(f'Using bathymetry file: {dat_files}')
    #     bathy_file = [file for file in dat_files if 'Perfil_0' in file][0]
    #     data=np.loadtxt(bathy_file)
    #     x=data[:,0]  # No esta reversado, caution!
    #     y=np.zeros(data[:,1].shape) 

    #     np.savetxt(f'{self.dict_folders["run"]}x_profile.grd',x,fmt='%f')
    #     np.savetxt(f'{self.dict_folders["run"]}y_profile.grd',y,fmt='%f')

    #     grid_dict={'xfilepath':'x_profile.grd','yfilepath':'y_profile.grd','meshes_x':len(x)-1,'meshes_y':0}
    #     for key,value in grid_dict.items():
    #         grid_dict[key]=str(value)
    #     return grid_dict

    # def params_2D_from_bathy(self):
    #     sf = shapefile.Reader(f'{self.dict_folders["input"]}Modelo_2D.shp')

    #     # Extract the shapes and records
    #     shapes = sf.shapes()
    #     records = sf.records()

    #     # Assuming the shapefile contains only one rectangle
    #     shape = shapes[0]

    #     # Extract the bounding box (min_lon, min_lat, max_lon, max_lat)
    #     min_lon, min_lat, max_lon, max_lat = shape.bbox

    #     # Print the bounding box
    #     # print(f'Bounding box: min_lon={min_lon}, min_lat={min_lat}, max_lon={max_lon}, max_lat={max_lat}')

    #     min_longitude = int(np.ceil(min_lon / 50) * 50)-50
    #     max_longitude = int(np.floor(max_lon / 50) * 50)+50
    #     min_latitude = int(np.ceil(min_lat / 50) * 50)-50
    #     max_latitude = int(np.floor(max_lat / 50) * 50)+50   

    #     ymax=max_longitude
    #     ymin=min_longitude
    #     xmin=max_latitude
    #     xmax=min_latitude


    #     x=np.arange(xmin-xmin,xmin-xmax+2,2)  # Caution
    #     y=np.arange(ymin-ymin,ymax-ymin+2,2)

    #     X,Y=np.meshgrid(x,y)

    #     np.savetxt(f'{self.dict_folders["run"]}x_profile.grd',X,fmt='%f')
    #     np.savetxt(f'{self.dict_folders["run"]}y_profile.grd',Y,fmt='%f')

    #     grid_dict={'xfilepath':'x_profile.grd','yfilepath':'y_profile.grd','meshes_x':len(x)-1,'meshes_y':len(y)-1}
    #     for key,value in grid_dict.items():
    #         grid_dict[key]=str(value)
    #     return grid_dict        

    # def params_2D_from_xyz(self):
    #     bathy_file_path = glob.glob(f'{self.dict_folders["input"]}*.csv')[0]

    #     bathy_data = pd.read_csv(bathy_file_path)
    #     print(bathy_data)
    #     min_lon = np.min(bathy_data.X)
    #     max_lon = np.max(bathy_data.X)
    #     min_lat = np.min(bathy_data.Y)
    #     max_lat = np.max(bathy_data.Y)

    #     ymax=max_lon
    #     ymin=min_lon
    #     xmin=max_lat
    #     xmax=min_lat

    #     print(xmin-xmin,xmin-xmax)

    #     x=np.arange(xmin-xmin,xmin-xmax+(10/110000),10/110000)  # Caution
    #     y=np.arange(ymin-ymin,ymax-ymin+(10/110000),10/110000)

    #     X,Y=np.meshgrid(x,y)

    #     np.savetxt(f'{self.dict_folders["run"]}x_profile.grd',X,fmt='%f')
    #     np.savetxt(f'{self.dict_folders["run"]}y_profile.grd',Y,fmt='%f')

    #     grid_dict={'xfilepath':'x_profile.grd','yfilepath':'y_profile.grd','meshes_x':len(x)-1,'meshes_y':len(y)-1}
    #     for key,value in grid_dict.items():
    #         grid_dict[key]=str(value)
    #     return grid_dict        

    # # def params_from_bathy(self):
    # #     bathy_file_path = glob.glob(f'{self.dict_folders["input"]}*.dat')[0]
    # #     data = np.loadtxt(bathy_file_path)
    # #     longitude = data[:, 0]
    # #     latitude = data[:, 1]
    # #     elevation = data[:, 2]

    # #     min_longitude = np.min(longitude)
    # #     min_latitude = np.min(latitude)

    # #     max_longitude = np.max(longitude)
    # #     max_latitude = np.max(latitude)
    # #     min_longitude = int(np.ceil(min_longitude / 100) * 100)
    # #     max_longitude = int(np.floor(max_longitude / 100) * 100)
    # #     min_latitude = int(np.ceil(min_latitude / 100) * 100)
    # #     max_latitude = int(np.floor(max_latitude / 100) * 100)

    # #     x_extent=max_longitude-min_longitude
    # #     y_extent=max_latitude-min_latitude

    # #     nx = int(x_extent/self.dx)
    # #     ny = int(y_extent/self.dy)
        
    # #     grid_dict={'lon_ll_corner':min_longitude,'lat_ll_corner':min_latitude,'x_extent':x_extent,'y_extent':y_extent,'nx':nx,'ny':ny}
    # #     for key,value in grid_dict.items():
    # #         grid_dict[key]=str(value)

    # #     return grid_dict

    # def grid_from_DELFT3D(self,filename_grd):
    #     os.system(f'cp {self.dict_folders["input"]}{filename_grd}.grd {self.dict_folders["run"]}')
    #     dict_asc={'grdfilepath':f'{filename_grd}.grd','model_origin':'delft3d'}
    #     return dict_asc

    def fill_grid_section(self,grid_dict):
        print ('\n*** Adding/Editing grid information in params file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',grid_dict)