import numpy as np
import glob as glob
from scipy.interpolate import griddata
from scipy.signal import medfilt, savgol_filter 
import os
import shapefile
import pandas as pd
import glob as glob                   
from scipy.signal import medfilt, savgol_filter 

from .. import utils

class BathyMaker():
    """
    A class for preprocessing bathymetry data.

    Args:
        filename (str): The name of the output file.
        dx_bat (float): The grid spacing for the bathymetry data
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Attributes:
        filename (str): The name of the output file.
        dx_bat (float): The grid spacing for the bathymetry data.

    Methods:

    """
    def __init__(self, init, filename="bed.dep", *args, **kwargs):
        """
        Initialize BathyMaker.

        Parameters
        ----------
        init : object
            Holder with paths in init.dict_folders (expects 'input' and 'run').
        filename : str, optional
            Default .dep output filename (default 'bed.dep').
        """
        self.init = init
        self.filename = filename

    def read_xyz_file(xyz_path):
        """
        Read XYZ file (topobathymetry point cloud) with robust parsing.
        Assumes at least 3 numeric columns: X, Y, Z.
        Non-numeric rows (e.g. header) are automatically dropped.
        """
        # Try reading with whitespace delimiter and no header
        df = pd.read_csv(
            xyz_path,
            delim_whitespace=True,
            header=None,
            comment="#",
            engine="python"
        )

        # Keep only first three columns
        df = df.iloc[:, :3]

        # Convert to numeric and drop non-finite values
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()

        df.columns = ["X", "Y", "Z"]
        return df

    # -------------------------------
    # Internal utilities (NEW)
    # -------------------------------
    # def _autodetect_xyz_path(self, xyz_filename=None):
    #     """
    #     Return path to XYZ file in input/. If xyz_filename is None, search for *.xyz / *.csv.
    #     """
    #     in_dir = self.init.dict_folders["input"]
    #     if xyz_filename is not None:
    #         cand = os.path.join(in_dir, xyz_filename)
    #         if os.path.exists(cand):
    #             return cand
    #         raise FileNotFoundError(f"Specified XYZ file not found: {cand}")
    #     patterns = ["*.xyz", "*bathy*.xyz", "*.csv"]
    #     for pat in patterns:
    #         files = sorted(glob.glob(os.path.join(in_dir, pat)))
    #         if files:
    #             return files[0]
    #     raise FileNotFoundError("No XYZ file found in input/ folder.")

    # def _read_xyz(self, path):
    #     """
    #     Read XYZ (X Y Z) with basic delimiter/header autodetection.
    #     Returns X, Y, Z as 1D float arrays.
    #     """
    #     # Try whitespace first (no header)
    #     try:
    #         arr = np.loadtxt(path)
    #         if arr.ndim == 1:
    #             arr = arr.reshape(-1, 3)
    #         if arr.shape[1] >= 3:
    #             X, Y, Z = arr[:, 0].astype(float), arr[:, 1].astype(float), arr[:, 2].astype(float)
    #             return X, Y, Z
    #     except Exception:
    #         pass
    #     # Try pandas with common separators
    #     for sep in [None, ",", ";", "\t", " "]:
    #         try:
    #             df = pd.read_csv(path) if sep is None else pd.read_csv(path, sep=sep, header=None)
    #             if df.shape[1] >= 3:
    #                 X = pd.to_numeric(df.iloc[:, 0], errors="coerce").values
    #                 Y = pd.to_numeric(df.iloc[:, 1], errors="coerce").values
    #                 Z = pd.to_numeric(df.iloc[:, 2], errors="coerce").values
    #                 m = np.isfinite(X) & np.isfinite(Y) & np.isfinite(Z)
    #                 X, Y, Z = X[m], Y[m], Z[m]
    #                 if len(X) > 0:
    #                     return X.astype(float), Y.astype(float), Z.astype(float)
    #         except Exception:
    #             continue
    #     raise ValueError("Unable to read XYZ: check delimiter and ensure at least 3 numeric columns.")

    # def _load_x_profile(self):
    #     """
    #     Load run/x_profile.grd and return a 1D array of distances along the profile.
    #     """
    #     x_path = os.path.join(self.init.dict_folders["run"], "x_profile.grd")
    #     if not os.path.exists(x_path):
    #         raise FileNotFoundError("run/x_profile.grd not found. Create or load it using GridMaker first.")
    #     x = np.loadtxt(x_path)
    #     if x.ndim == 2:
    #         x = x.reshape(-1) if 1 in x.shape else x[0, :]
    #     return np.asarray(x, dtype=float)

    # def _build_profile_coords(self, start_xy, end_xy, s):
    #     """
    #     Given start/end coordinates and distances s, return query coordinates (Xq, Yq) along the line.
    #     """
    #     start = np.asarray(start_xy, dtype=float)
    #     end = np.asarray(end_xy, dtype=float)
    #     vec = end - start
    #     L = np.hypot(vec[0], vec[1])
    #     if L == 0:
    #         raise ValueError("Start and end points are identical.")
    #     u = vec / L
    #     Xq = start[0] + u[0] * s
    #     Yq = start[1] + u[1] * s
    #     return Xq, Yq

    # def _interpolate_along_profile(self, X, Y, Zval, Xq, Yq, method="linear", fill="nearest"):
    #     """
    #     Interpolate Z values from scattered (X, Y, Zval) onto (Xq, Yq).
    #     Supports 'linear' | 'nearest' | 'cubic'. fill='nearest' fills NaNs outside convex hull.
    #     """
    #     pts = np.column_stack([X, Y])
    #     Zq = griddata(pts, Zval, (Xq, Yq), method=method)
    #     if fill == "nearest":
    #         mask = ~np.isfinite(Zq)
    #         if np.any(mask):
    #             Zq_fill = griddata(pts, Zval, (Xq[mask], Yq[mask]), method="nearest")
    #             Zq[mask] = Zq_fill
    #     return Zq

    # def _apply_smoothing(self, z, smooth=None, window=5, poly=2):
    #     """
    #     Optional 1D smoothing: smooth=None|'median'|'savgol'.
    #     """
    #     if smooth is None:
    #         return z
    #     n = len(z)
    #     w = int(window)
    #     if w < 3: 
    #         return z
    #     if w % 2 == 0:
    #         w += 1
    #     w = min(w, n - (1 - n % 2))
    #     if w < 3:
    #         return z
    #     if smooth == "median":
    #         return medfilt(z, kernel_size=w)
    #     if smooth == "savgol":
    #         p = max(2, min(poly, w - 1))
    #         return savgol_filter(z, window_length=w, polyorder=p)
    #     return z

    # def xyzline2dep(
    #     self,
    #     start_xy,
    #     end_xy,
    #     *,
    #     xyz_filename=None,
    #     method="linear",
    #     fill="nearest",
    #     smooth=None,          # None | 'median' | 'savgol'
    #     smooth_window=5,
    #     smooth_poly=2,
    #     out_filename=None,    # default: self.filename
    #     posdwn=True,
    #     xyz_is_depth=False    # False => XYZ Z is elevation (+up). True => Z is depth (+down).
    # ):
    #     """
    #     Create a 1D XBeach .dep along a profile line using a scattered XYZ and run/x_profile.grd.

    #     Parameters
    #     ----------
    #     start_xy, end_xy : tuple(float, float)
    #         Start/end coordinates in the same planar CRS as the XYZ (e.g., UTM).
    #     xyz_filename : str | None
    #         XYZ filename inside input/. If None, autodetected (*.xyz or *.csv).
    #     method : {'linear','nearest','cubic'}
    #         Main interpolation method (default 'linear').
    #     fill : {None,'nearest'}
    #         Fill strategy for NaNs outside convex hull (default 'nearest').
    #     smooth : None | 'median' | 'savgol'
    #         Optional 1D smoothing of the resulting depth profile.
    #     smooth_window : int
    #         Smoothing window size (odd >=3).
    #     smooth_poly : int
    #         Polynomial order for Savitzky–Golay smoothing.
    #     out_filename : str | None
    #         Output .dep name (default self.filename, e.g. 'bed.dep').
    #     posdwn : bool
    #         If True, write positive-down depths (default True).
    #     xyz_is_depth : bool
    #         If True, Z in XYZ is already depth (+down). If False, Z is elevation (+up).

    #     Returns
    #     -------
    #     dict
    #         {'depfilepath': str, 'meshes_x': int, 'meshes_y': 0, 'posdwn': int, 'method': str, 'smooth': str | None}
    #     """
    #     # 1) Inputs and files
    #     xyz_path = self._autodetect_xyz_path(xyz_filename)
    #     X, Y, Zraw = self._read_xyz(xyz_path)
    #     s = self._load_x_profile()
    #     s = s - s[0]  # shift so profile starts at 0

    #     # 2) Build query coordinates along the line
    #     Xq, Yq = self._build_profile_coords(start_xy, end_xy, s)

    #     # 3) Convert XYZ Z to depth (+down) in memory
    #     Depth = Zraw.astype(float) if xyz_is_depth else -Zraw.astype(float)

    #     # 4) Interpolate along profile
    #     Zq = self._interpolate_along_profile(X, Y, Depth, Xq, Yq, method=method, fill=fill)
    #     if not np.all(np.isfinite(Zq)):
    #         raise ValueError("NaNs remain in interpolated profile; check XYZ coverage or use fill='nearest'.")

    #     # 5) Optional smoothing
    #     Zq_s = self._apply_smoothing(Zq, smooth=smooth, window=smooth_window, poly=smooth_poly)

    #     # 6) Output sign
    #     dep_vals = Zq_s if posdwn else -Zq_s

    #     # 7) Write .dep as a single row
    #     out_name = out_filename if out_filename is not None else self.filename
    #     dep_path = os.path.join(self.init.dict_folders["run"], out_name)
    #     np.savetxt(dep_path, dep_vals, fmt="%.3f")

    #     return {
    #         "depfilepath": os.path.basename(dep_path),
    #         "meshes_x": int(len(s) - 1),  # N-1 cells
    #         "meshes_y": 0,
    #         "posdwn": int(bool(posdwn)),
    #         "method": method,
    #         "smooth": smooth,
    #     }

    def xyz2asc(self,dx_bat,nodata_value):
        """
        Converts bathymetry data from XYZ format to ESRI ASCII Grid format.

        Args:
            nodata_value (float): The value to replace NaN values in the grid.

        Returns:
            dict: A dictionary containing the metadata of the generated grid.
        """
        bathy_xyz_path = glob.glob(f'{self.init.dict_folders["input"]}bathy*.csv')[0]
        ascfile = f'{self.init.dict_folders["run"]}{self.filename}.dep'
        # ascfile_ne_ones = f'{self.dict_folders["run"]}ne_layer_ones.dep'
        # np.set_printoptions(formatter={'float_kind':'{:f}'.format})
        df_xyz = pd.read_csv(bathy_xyz_path)

        # compute the grid extents
        min_x,max_x = df_xyz['Y'].min(), df_xyz['Y'].max() # It depends and how the columns are originally named*
        min_y,max_y = df_xyz['X'].min(), df_xyz['X'].max()

        # Compute the number of grid cells
        nx_bathy = int((min_x - max_x)/dx_bat)
        ny_bathy = int((max_y - min_y)/dx_bat)

        # Generate grid with data
        xi, yi = np.mgrid[min_x:max_x:(nx_bathy+1)*1j, min_y:max_y:(ny_bathy+1)*1j]  # Caution

        # Interpolate bathymetry. Method can be 'linear', 'nearest' or 'cubic'
        zi = griddata((df_xyz['Y'], df_xyz['X']), df_xyz['Z'], (xi, yi), method='linear')

        # Change Nans for values
        zi[np.isnan(zi)] = nodata_value

        zi[zi < -10] = -1

        # Flip array in the left/right direction
        zi = np.fliplr(zi)
        # # Transpose it
        zi = zi.T

        # Write ESRI ASCII Grid file
        zi_str = np.where(zi == nodata_value, str(nodata_value), np.round(zi, 3))
        np.savetxt(ascfile, zi_str, fmt='%8.6s', delimiter=' ')

        # zi_ones=np.ones(zi.shape)
        # np.savetxt(ascfile_ne_ones, zi_ones, fmt='%8s', delimiter=' ')

        print('File %s saved successfuly.' % ascfile)

        dict_asc={'depfilepath':f'{self.filename}.dep','x_bot':nx_bathy,'y_bot':ny_bathy,'spacing_x':dx_bat,'spacing_y':dx_bat,
                  'nelayerfilepath':'ne_layer.dep'}
        for key,value in dict_asc.items():
            dict_asc[key]=str(value)
        return dict_asc


    # def profile2asc(self):
    #     dat_files=glob.glob(f'{self.dict_folders["input"]}*.dat')
    #     bathy_file = [file for file in dat_files if 'Perfil_0' in file][0]
    #     print(f'Using bathymetry file: {bathy_file}')
    #     data=np.loadtxt(bathy_file)
    #     ascfile = f'{self.dict_folders["run"]}{self.filename}.dep'
    #     np.savetxt(ascfile,data[:,3][::-1],fmt='%f')
    #     print('File %s saved successfuly.' % ascfile)

    #     dict_asc={'depfilepath':f'{self.filename}.dep'}

    #     ne_layer=np.ones(data[:,1].shape)*1
    #     np.savetxt(f'{self.dict_folders["run"]}nelayer.dep',ne_layer,fmt='%f')

    #     for key,value in dict_asc.items():
    #         dict_asc[key]=str(value)
            
    #     return dict_asc


    # def xyz2asc(self,dx_bat,nodata_value):
    #     """
    #     Converts bathymetry data from XYZ format to ESRI ASCII Grid format.

    #     Args:
    #         nodata_value (float): The value to replace NaN values in the grid.

    #     Returns:
    #         dict: A dictionary containing the metadata of the generated grid.
    #     """
    #     bathy_xyz_path = glob.glob(f'{self.dict_folders["input"]}*.csv')[0]
    #     ascfile = f'{self.dict_folders["run"]}{self.filename}.dep'
    #     ascfile_ne_ones = f'{self.dict_folders["run"]}ne_layer_ones.dep'
    #     np.set_printoptions(formatter={'float_kind':'{:f}'.format})
    #     # Read bathymetry file
    #     longitude,latitude,z = np.loadtxt(bathy_xyz_path, delimiter=',', unpack=True, skiprows=1)

    #     # print(longitude,latitude,z)

    #     # Load the shapefile
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

    #     nx_bathy = int((xmin - xmax)/dx_bat)
    #     ny_bathy = int((ymax - ymin)/dx_bat)
    #     # # Generate grid with data
    #     xi, yi = np.mgrid[xmin:xmax:(nx_bathy+1)*1j, ymin:ymax:(ny_bathy+1)*1j]  # Caution

    #     # # Interpolate bathymetry. Method can be 'linear', 'nearest' or 'cubic'
    #     zi = griddata((latitude,longitude), z, (xi, yi), method='linear')
    #     # # Change Nans for values
    #     zi[np.isnan(zi)] = nodata_value
    #     # Flip array in the left/right direction
    #     # zi = np.fliplr(zi)
    #     # Transpose it
    #     zi = zi.T
    #     # Write ESRI ASCII Grid file
    #     zi_str = np.where(zi == nodata_value, str(nodata_value), np.round(zi, 3))

    #     zi_ones=np.ones(zi.shape)
    #     np.savetxt(ascfile, zi_str, fmt='%8s', delimiter=' ')
    #     np.savetxt(ascfile_ne_ones, zi_ones, fmt='%8s', delimiter=' ')

    #     print('File %s saved successfuly.' % ascfile)

    #     dict_asc={'depfilepath':f'{self.filename}.dep','x_bot':nx_bathy,'y_bot':ny_bathy,'spacing_x':dx_bat,'spacing_y':dx_bat,
    #               'nelayerfilepath':'ne_layer.dep'}
    #     for key,value in dict_asc.items():
    #         dict_asc[key]=str(value)
    #     return dict_asc
    
    # def read_dry_index(self):
    #     index_dry = glob.glob(f'{self.dict_folders["input"]}indexes_dry_points.txt')[0]
    #     points= np.loadtxt(index_dry)
    #     xi,yi=points[:,1],points[:,2]
    #     ne_layer_ones=np.loadtxt(f'{self.dict_folders["run"]}ne_layer_ones.dep')
    #     for idx_x,idx_y in zip(xi,yi):
    #         ne_layer_ones[int(idx_y),-int(idx_x)]=0
    #     # ne_layer_ones = np.fliplr(ne_layer_ones)
    #     # Transpose it
    #     # ne_layer_ones = ne_layer_ones.T
    #     ascfile_ne = f'{self.dict_folders["run"]}ne_layer.dep'
    #     np.savetxt(ascfile_ne, ne_layer_ones, fmt='%8s', delimiter=' ')
    #     print('File %s saved successfuly.' % ascfile_ne)

    # def bathy_from_DELFT3D(self,filename_dep,filename_nedep):
    #     os.system(f'cp {self.dict_folders["input"]}{filename_dep}.dep {self.dict_folders["run"]}')
    #     os.system(f'cp {self.dict_folders["input"]}{filename_nedep}.dep {self.dict_folders["run"]}')

    #     dict_asc={'depfilepath':f'{filename_dep}.dep','model_origin':'delft3d',
    #               'nelayerfilepath':f'{filename_nedep}.dep'}
    #     return dict_asc

    def fill_bathy_section(self,dict_data):

        print ('\n*** Adding/Editing bathymetry information in params file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',dict_data)


