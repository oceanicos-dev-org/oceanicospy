import numpy as np
import glob as glob
import pandas as pd
from .. import utils
import shapefile
import os
import shutil
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point


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

        # Store planar coordinates
        self.start_xy = np.array(start_xy, dtype=float) if start_xy is not None else None
        self.end_xy = np.array(end_xy, dtype=float) if end_xy is not None else None

        self.final_end_xy = None

        # Compute profile length if planar coordinates were provided
        if self.start_xy is not None and self.end_xy is not None and self.end_x_point is None:
            self.end_x_point = float(np.linalg.norm(self.end_xy - self.start_xy))


    def load_existing_grid(self):
        """
        Load any pair of .grd files found in the input folder using pathlib and return
        basic grid information after validating consistency between the two grids.

        This method does not require specific filenames such as 'x_profile.grd' or
        'y_profile.grd'. Instead, it searches for all files with the '.grd' extension
        inside the input folder and interprets the first two found as the x and y grids.
        The method then loads both grids, verifies that they share the same numerical
        shape, and copies them into the run folder using standardized filenames
        ('x_profile.grd' and 'y_profile.grd').

        Parameters
        ----------
        None

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

        Raises
        ------
        ValueError
            Raised when the two loaded '.grd' files do not match in shape.

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
        # Locate all .grd files inside the input folder
        input_folder = Path(self.init.dict_folders["input"])
        grd_files = list(input_folder.glob("*.grd"))

        # Require at least two files to identify x and y
        if len(grd_files) < 2:
            return None

        # Select the first two .grd files
        x_file_path = grd_files[0]
        y_file_path = grd_files[1]

        # Load numeric data
        x = np.loadtxt(x_file_path)
        y = np.loadtxt(y_file_path)

        # Validate shapes
        if x.shape != y.shape:
            raise ValueError("Loaded .grd files do not have matching shapes.")

        # Detect dimension
        is_2d = (y.ndim == 2)
        meshes_x = x.shape[1] - 1 if is_2d else x.shape[0] - 1
        meshes_y = y.shape[0] - 1 if is_2d else 0

        # Copy into run folder with standardized names
        run_folder = Path(self.init.dict_folders["run"])
        dest_x = run_folder / "x_profile.grd"
        dest_y = run_folder / "y_profile.grd"

        shutil.copy(str(x_file_path), str(dest_x))
        shutil.copy(str(y_file_path), str(dest_y))

        # Return descriptor
        return {
            "xfilepath": "x_profile.grd",
            "yfilepath": "y_profile.grd",
            "meshes_x": meshes_x,
            "meshes_y": meshes_y
        }
    
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
            Dictionary with keys 'x' and 'y' for cumulative distances.
        """
        total_x = 0.0
        total_y = 0.0

        for key in sorted(dist_segments.keys(), key=lambda k: int(k)):
            total_x += dist_segments[key]['x']
            total_y += dist_segments[key]['y']
            if str(key) == str(up_to_segment):
                break

        return {"x": total_x, "y": total_y}
    
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
                    # keep extending with the last dx until we cross target,
                    # then add one final full step so that the last cell length
                    # equals last_dx.
                    while x[-1] + last_dx < target:
                        x.append(x[-1] + last_dx)
                    x.append(x[-1] + last_dx)
                else:
                    # Original behavior: force the last point to be exactly `end`
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
                        # NEW: extend using the full last dx (overshoot allowed)
                        x.append(x[-1] + dx)
                    else:
                        # Original behavior: force exact nominal end
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
                    # NEW: extend using the last dx until we cross target,
                    # then add one final full step.
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
                        # NEW: extend using the full last dx (overshoot allowed)
                        x.append(next_x)
                    else:
                        # Original behavior: force exact nominal end
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
            Generate rectangular grid files for XBeachpy preprocessing.

            Parameters
            ----------
            source_file : str, optional
                Name of an input file used to derive the grid extent. If None and
                dims == '1', a 1-D profile is created using self.end_x_point and
                self.dx (or using planar coordinates start_xy / end_xy if provided).
                If the filename ends with '.shp', the first shape in the shapefile
                located at self.init.dict_folders['input'] + source_file is read and
                its bounding box (min_lon, min_lat, max_lon, max_lat) is used to
                construct a 2-D rectangular grid.

            xvar : bool, optional
                If False (default), builds a uniform grid in both x and y directions.
                If True, a segmented, variable-resolution grid is built based on
                start_segments, dist_segments and delta_segments (2-D case only).

            start_segments : dict, optional
                Dictionary containing starting positions for each segment when
                xvar=True (2-D variable resolution case).

            dist_segments : dict, optional
                Dictionary containing segment lengths for each segment when
                xvar=True (2-D variable resolution case).

            delta_segments : dict, optional
                Dictionary containing grid spacing (dx) for each segment when
                xvar=True (2-D variable resolution case).

            Returns
            -------
            dict or None
                If dims == '1', returns a dictionary with:
                    - 'xfilepath' : 'x_profile.grd'
                    - 'yfilepath' : 'y_profile.grd'
                    - 'meshes_x'  : number of cells in x-direction
                    - 'meshes_y'  : 0

                If dims != '1', returns a dictionary with:
                    - 'xfilepath' : 'x.grd'
                    - 'yfilepath' : 'y.grd'
                    - 'meshes_x'  : number of cells in x-direction
                    - 'meshes_y'  : number of cells in y-direction

                Returns None if fewer than two '.grd' files are found in
                self.init.dict_folders['input'] when trying to import an
                existing grid.

            Notes
            -----
            * If dims == '1':
                - With planar coordinates (start_xy and end_xy not None), a 1-D
                profile is created along the straight line between these points.
                In this modified version, the files written are:
                    x_profile.grd: local 1-D coordinate s = [0, dx, 2dx, ...]
                    y_profile.grd: 0 for all points
                The actual planar end-point reached after applying dx and
                auto_extend/as_n_cells is stored in self.final_end_xy.
                - Without planar coordinates, a 1-D profile in x-only is created
                using end_x_point and dx. x_profile.grd contains the 1-D
                coordinate (starting at 0), and y_profile.grd is all zeros.

            * If dims != '1':
                - If self.dy is None it will be set to self.dx.
                - For a shapefile input, the method reads the first shape, extracts
                its bounding box and constructs x and y 1-D arrays which are
                then meshed into a rectangular grid.

            Raises
            ------
            AttributeError
                If required attributes on self are missing (for example: init,
                init.dict_ini_data, init.dict_folders, dx, end_x_point).
            FileNotFoundError
                If a shapefile is requested (source_file ends with '.shp') but the
                file is not found at the expected location
                (self.init.dict_folders['input'] + source_file).
            ValueError
                - If provided dx or dy are non-positive or otherwise invalid for
                grid generation.
                - If dims == '1' and neither end_x_point nor planar coordinates
                (start_xy, end_xy) are provided.
                - If dims != '1' and source_file is missing or does not end with
                '.shp' when a 2-D grid is requested.

            Examples
            --------
            # 1-D profile in x only (uses self.end_x_point and self.dx):
            >>> grid = obj.rectangular()

            # 1-D profile along a planar line:
            >>> obj.start_xy = (1000.0, 2000.0)
            >>> obj.end_xy = (1105.0, 2000.0)
            >>> grid = obj.rectangular()

            # 2-D grid from a shapefile:
            >>> grid = obj.rectangular('domain.shp')
            """

            # ----------------------------------------------------------------------
            # Step 0: check for pre-existing .grd files in the input folder.
            # If found (at least 2 files), standardize their names and return
            # them directly, assuming the user provides an existing grid.
            # ----------------------------------------------------------------------
            input_folder = self.init.dict_folders["input"]

            grd_files = glob.glob(os.path.join(input_folder, "*.grd"))

            if len(grd_files) >= 2:
                # Rename or move files to standard names 'x.grd' and 'y.grd'
                xfile = None
                yfile = None

                for f in grd_files:
                    fname = os.path.basename(f).lower()
                    if 'x' in fname and xfile is None:
                        xfile = f
                    elif 'y' in fname and yfile is None:
                        yfile = f

                # Fall back if xfile or yfile could not be clearly inferred
                if xfile is None:
                    xfile = grd_files[0]
                if yfile is None:
                    yfile = grd_files[1]

                # Standardized filenames inside the run folder
                x_out = os.path.join(input_folder, "x.grd")
                y_out = os.path.join(input_folder, "y.grd")

                shutil.copy(xfile, x_out)
                shutil.copy(yfile, y_out)

                return {
                    'xfilepath': 'x.grd',
                    'yfilepath': 'y.grd',
                    'meshes_x': None,
                    'meshes_y': None
                }

            # ----------------------------------------------------------------------
            # Step 1: no pre-existing grid – build a new one.
            # ----------------------------------------------------------------------

            # Get backward-compatible flags from self; if not present, defaults
            # are used to keep backward compatibility.
            auto_extend_flag = getattr(self, "auto_extend", True)
            as_n_cells_flag = getattr(self, "as_n_cells", False)

            if self.init.dict_ini_data['dims'] == '1':
                # --------------------------------------------------------------
                # 1D CASE: profile grid
                # --------------------------------------------------------------

                # If planar coordinates are available, create a profile along
                # the straight line between start_xy and end_xy.
                if self.start_xy is not None and self.end_xy is not None:
                    # Vector between planar points
                    vec = self.end_xy - self.start_xy
                    L_geom = float(np.linalg.norm(vec))

                    if L_geom == 0.0:
                        raise ValueError(
                            "start_xy and end_xy are identical; profile length is zero."
                        )

                    # If the user did not explicitly set end_x_point, use the
                    # geometric length between the two points as nominal length.
                    if self.end_x_point is None:
                        self.end_x_point = L_geom

                    # Build the "s-axis" (curvilinear coordinate along the profile)
                    # using the flexible dx specification. This call may internally
                    # extend the profile length so that the last cell matches the
                    # last spacing used.
                    s_axis = self._build_variable_dx_axis(
                        start=0.0,
                        end=self.end_x_point,
                        dx_spec=self.dx,
                        auto_extend=auto_extend_flag,
                        as_n_cells=as_n_cells_flag
                    )

                    # Unit direction vector along the original line
                    direction = vec / L_geom

                    # Use s_axis as local 1D coordinate: x = [0, dx, 2dx, ...], y = 0
                    # So x_profile.grd contains a single column [0, dx, 2dx, ...]
                    # and y_profile.grd contains zeros, regardless of the planar
                    # orientation of the original line.
                    x_points = s_axis.copy()
                    y_points = np.zeros_like(s_axis)

                    # Store the adjusted final coordinate in planar coordinates
                    # (this may differ from the originally provided end_xy if
                    # auto_extend/as_n_cells modified the effective length).
                    self.final_end_xy = (
                        float(self.start_xy[0] + direction[0] * s_axis[-1]),
                        float(self.start_xy[1] + direction[1] * s_axis[-1]),
                    )

                    grid_dict = {
                        'xfilepath': 'x_profile.grd',
                        'yfilepath': 'y_profile.grd',
                        'meshes_x': len(x_points) - 1,
                        'meshes_y': 0
                    }

                else:
                    # 1-D profile in x only (no planar coordinates)
                    if self.end_x_point is None:
                        raise ValueError(
                            "For 1D grid without planar coordinates you must provide 'end_x_point'."
                        )

                    start_x_point = 0.0

                    # Use the flexible axis builder, which may adjust the final
                    # coordinate depending on auto_extend and as_n_cells.
                    x_points = self._build_variable_dx_axis(
                        start=start_x_point,
                        end=self.end_x_point,
                        dx_spec=self.dx,
                        auto_extend=auto_extend_flag,
                        as_n_cells=as_n_cells_flag
                    )
                    y_points = np.zeros_like(x_points)

                    grid_dict = {
                        'xfilepath': 'x_profile.grd',
                        'yfilepath': 'y_profile.grd',
                        'meshes_x': len(x_points) - 1,
                        'meshes_y': 0
                    }

            else:
                # --------------------------------------------------------------
                # 2D CASE: rectangular grid from shapefile
                # --------------------------------------------------------------
                if self.dy is None:
                    # If dy is not provided, use the same spacing as dx
                    self.dy = self.dx

                if source_file is None or not source_file.endswith('.shp'):
                    raise ValueError(
                        "For dims != '1' you must provide a shapefile source_file ending with '.shp'."
                    )

                # Read shapefile and get bounding box
                sf = shapefile.Reader(f'{self.init.dict_folders["input"]}{source_file}')
                shape = sf.shapes()[0]

                # Extract the bounding box (min_lon, min_lat, max_lon, max_lat)
                min_lon, min_lat, max_lon, max_lat = shape.bbox

                # ------------------------------------------------------------------
                # Branch 1: uniform grid (current behaviour)
                # ------------------------------------------------------------------
                if not xvar:
                    # Build uniform grid in x and y directions
                    x_points_flat = np.arange(min_lon, max_lon + self.dx, self.dx)
                    y_points_flat = np.arange(min_lat, max_lat + self.dy, self.dy)

                    # Generate meshgrid
                    x_points, y_points = np.meshgrid(x_points_flat, y_points_flat)

                    grid_dict = {
                        'xfilepath': 'x.grd',
                        'yfilepath': 'y.grd',
                        'meshes_x': x_points.shape[1] - 1,
                        'meshes_y': y_points.shape[0] - 1
                    }

                # ------------------------------------------------------------------
                # Branch 2: segmented, variable-resolution grid (Franklin's logic)
                # ------------------------------------------------------------------
                else:
                    # Basic validation of required dictionaries
                    if start_segments is None or dist_segments is None or delta_segments is None:
                        raise ValueError(
                            "When xvar=True you must provide 'start_segments', "
                            "'dist_segments' and 'delta_segments' dictionaries."
                        )

                    list_x_points_flat_all = []
                    list_y_points_flat_all = []

                    # Loop through all segments defined in start_segments
                    for seg_key in start_segments.keys():
                        start_x = start_segments[seg_key]
                        dist = dist_segments[seg_key]
                        dx_seg = delta_segments[seg_key]

                        seg_end_x = start_x + dist
                        seg_x = np.arange(start_x, seg_end_x, dx_seg)
                        list_x_points_flat_all.append(seg_x)

                    # Concatenate all x segments
                    x_points_flat = np.unique(np.concatenate(list_x_points_flat_all))

                    # Build y direction uniformly, for simplicity
                    y_points_flat = np.arange(min_lat, max_lat + self.dy, self.dy)

                    # Generate meshgrid
                    x_points, y_points = np.meshgrid(x_points_flat, y_points_flat)

                    grid_dict = {
                        'xfilepath': 'x.grd',
                        'yfilepath': 'y.grd',
                        'meshes_x': x_points.shape[1] - 1,
                        'meshes_y': y_points.shape[0] - 1
                    }

            # ----------------------------------------------------------------------
            # Step 2: Save the computed grid(s) to .grd files
            # ----------------------------------------------------------------------
            x_run_path = os.path.join(self.init.dict_folders["run"],   grid_dict['xfilepath'])
            x_input_path = os.path.join(self.init.dict_folders["input"], grid_dict['xfilepath'])

            y_run_path = os.path.join(self.init.dict_folders["run"],   grid_dict['yfilepath'])
            y_input_path = os.path.join(self.init.dict_folders["input"], grid_dict['yfilepath'])

            # Save X points in both locations
            np.savetxt(x_run_path,   x_points, fmt='%.4f')
            np.savetxt(x_input_path, x_points, fmt='%.4f')

            # Save Y points in both locations
            np.savetxt(y_run_path,   y_points, fmt='%.4f')
            np.savetxt(y_input_path, y_points, fmt='%.4f')

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

    # def fill_grid_section(self,grid_dict):
    #     print ('\n*** Adding/Editing grid information in params file ***\n')
    #     utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',grid_dict)