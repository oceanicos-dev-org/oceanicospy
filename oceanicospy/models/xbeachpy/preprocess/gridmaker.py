import numpy as np
import glob as glob
import pandas as pd
from .. import utils
import shapefile
import os
import shutil
import geopandas as gpd
from shapely.geometry import Point
from itertools import zip_longest

class GridMaker():
    """
    A class for creating a Xbeach computational grid from bathymetry data and filling grid information in a params file.
    Args:
        root_path (str): The root path of the project.
        dx (float): The grid spacing in the x-direction.
        dy (float): The grid spacing in the y-direction.

    """
    def __init__ (self,init,dx,dy=None,end_x_point=None,*args,**kwargs):
        self.init = init
        self.dx = dx
        self.dy = dy
        self.end_x_point = end_x_point   

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
        - The function assumes the profile files are plain-text numeric grids compatible with numpy.loadtxt.
        - The returned file paths in the dictionary are filenames (not absolute paths) as they are intended to
            reference the copied files in the run folder.
        """

        x_path = os.path.join(self.init.dict_folders["input"], "x_profile.grd")
        y_path = os.path.join(self.init.dict_folders["input"], "y_profile.grd")

        if not (os.path.exists(x_path) and os.path.exists(y_path)):
            return None

        x = np.loadtxt(x_path)
        y = np.loadtxt(y_path)

        if x.shape != y.shape:
            raise ValueError("x and y profile files must have same shape.")

        is_2d = y.ndim - 1
        meshes_x = len(x[0,:]) - 1 if is_2d else len(x) - 1
        meshes_y = len(y[:,0]) - 1 if is_2d else 0

        dest_x_path = os.path.join(self.init.dict_folders["run"], "x_profile.grd")
        dest_y_path = os.path.join(self.init.dict_folders["run"], "y_profile.grd")
        shutil.copy(x_path, dest_x_path)
        shutil.copy(y_path, dest_y_path)

        grid_dict = {
            'xfilepath': 'x_profile.grd',
            'yfilepath': 'y_profile.grd',
            'meshes_x': meshes_x,
            'meshes_y': meshes_y
        }

        return grid_dict

    def cumulative_distance(self,dist_segments, up_to_segment):
        """
        Compute the cumulative x and y distance up to a given segment (inclusive).

        Args:
            dist_segments (dict): Dictionary of segments like
                {'1': {'x': 840, 'y': 760}, '2': {'x': 50, 'y': 70}, ...}
            up_to_segment (str or int): Segment key to compute distance up to.

        Returns:
            dict: {'x': total_x, 'y': total_y}
        """
        total_x = 0
        total_y = 0
        
        # Ensure numeric ordering of segment keys
        for key in sorted(dist_segments.keys(), key=lambda k: int(k)):
            total_x += dist_segments[key]['x']
            total_y += dist_segments[key]['y']
            
            if str(key) == str(up_to_segment):
                break

        return {'x': total_x, 'y': total_y}


    def rectangular(self,source_file=None,xvar=False,start_segments=None,dist_segments=None,delta_segments=None):
        """
        Generate rectangular grid files for XBeachpy preprocessing.
        Parameters
        ----------
        source_file : str, optional
            Name of an input file used to derive the grid extent. If None, a 1-D profile
            (x only) is created using self.end_x_point and self.dx. If the filename ends
            with '.shp', the first shape in the shapefile located at
            self.init.dict_folders['input'] + source_file is read and its bounding box
            (min_lon, min_lat, max_lon, max_lat) is used to build a 2-D regular grid.
            Default is None.
        Returns
        -------
        grid_dict : dict
            Dictionary describing the generated grid and file names:
            - 'xfilepath' (str): filename written for x coordinates (always 'x_profile.grd').
            - 'yfilepath' (str): filename written for y coordinates (always 'y_profile.grd').
            - 'meshes_x' (int): number of mesh intervals in the x direction (nx - 1).
            - 'meshes_y' (int): number of mesh intervals in the y direction (ny - 1),
            set to 0 for 1-D profiles.
        Notes
        -----
        - Behavior depends on self.init.dict_ini_data['dims']:
        - If dims == '1', the method creates x_points = arange(0, self.end_x_point, self.dx)
            and y_points filled with zeros (same shape as x_points). meshes_y is set to 0.
        - Otherwise, if self.dy is None it will be set to self.dx. For a shapefile input,
            the method reads the first shape, extracts its bounding box and constructs
            x and y 1-D arrays from min to max with steps self.dx and self.dy, then
            constructs 2-D grids with numpy.meshgrid. The coordinates are shifted so the
            grid origin corresponds to the minimum bounding-box coordinates (values
            written to files are relative to that origin).
        - The method writes the x and y grids to files named 'x_profile.grd' and
        'y_profile.grd' inside the folder specified by self.init.dict_folders['run']
        using numpy.savetxt with format '%.4f'.
        Raises
        ------
        AttributeError
            If required attributes on self are missing (for example: init, init.dict_ini_data,
            init.dict_folders, dx, end_x_point).
        FileNotFoundError
            If a shapefile is requested (source_file ends with '.shp') but the file is not
            found at the expected location (self.init.dict_folders['input'] + source_file).
        ValueError
            If provided dx or dy are non-positive or otherwise invalid for numpy.arange.
        Examples
        --------
        # 1-D profile (uses self.end_x_point and self.dx):
        >>> grid = obj.rectangular()
        # 2-D grid from a shapefile (input folder path must be correct and shapefile present):
        >>> grid = obj.rectangular('domain.shp')
        """
    
        if self.init.dict_ini_data['dims']=='1':
            start_x_point = 0
            x_points = np.arange(start_x_point,self.end_x_point,self.dx)
            y_points = np.zeros(x_points.shape)
            grid_dict={'xfilepath':'x_profile.grd','yfilepath':'y_profile.grd',
                        'meshes_x':len(x_points)-1,'meshes_y':0}
        else:
            if self.dy == None:
                self.dy = self.dx

            if source_file.endswith('.shp'):
                sf = shapefile.Reader(f'{self.init.dict_folders["input"]}{source_file}')
                shape = sf.shapes()[0]

                # Extract the bounding box (min_lon, min_lat, max_lon, max_lat)
                min_lon, min_lat, max_lon, max_lat = shape.bbox

                if not xvar:
                    x_points_flat = np.arange(min_lon,max_lon+self.dx,self.dx)-min_lon
                    y_points_flat = np.arange(min_lat,max_lat+self.dy,self.dy)-min_lat

                    x_points,y_points = np.meshgrid(x_points_flat,y_points_flat)

                    # geometry = [Point(x, y) for x, y in zip(x_points.flatten()+min_lon, y_points.flatten()+min_lat)]
                    # gdf = gpd.GeoDataFrame(pd.DataFrame({'x': x_points.flatten()+min_lon, 'y': y_points.flatten()+min_lat}),
                    #                     geometry=geometry,
                    #                     crs="EPSG:9377")
                    # gdf.to_file(f'{self.init.dict_folders["input"]}XBeach_domain_points_grid.shp')

                    grid_dict={'xfilepath':'x.grd','yfilepath':'y.grd',
                                'meshes_x':len(x_points[0,:])-1,'meshes_y':len(y_points[:,0])-1}

                    np.savetxt(f'{self.init.dict_folders["run"]}x.grd',x_points,fmt='%4.4f')
                    np.savetxt(f'{self.init.dict_folders["run"]}y.grd',y_points,fmt='%4.4f')

                else:
                    list_x_points_flat_all = []
                    list_y_points_flat_all = []
                    for segment in start_segments.keys():
                        if segment == '1':
                            x_points_flat_seg = np.arange(min_lon,(min_lon+dist_segments[segment]['x'])+delta_segments[segment]['x'],delta_segments[segment]['x'])-min_lon
                            y_points_flat_seg = np.arange(min_lat,(min_lat+dist_segments[segment]['y'])+delta_segments[segment]['y'],delta_segments[segment]['y'])-min_lat

                        else:
                            cum_distance_x = self.cumulative_distance(dist_segments,segment)['x']
                            cum_distance_y = self.cumulative_distance(dist_segments,segment)['y']

                            cum_distance_x_minus1 = self.cumulative_distance(dist_segments,f'{int(segment)-1}')['x']
                            cum_distance_y_minus1 = self.cumulative_distance(dist_segments,f'{int(segment)-1}')['y']

                            x_points_flat_seg = np.arange(min_lon + cum_distance_x_minus1 + delta_segments[segment]['x'],
                                                min_lon + cum_distance_x + delta_segments[segment]['x'],
                                                delta_segments[segment]['x'])-min_lon
                            y_points_flat_seg = np.arange(min_lat + cum_distance_y_minus1 + delta_segments[segment]['y'],
                                                min_lat + cum_distance_y + delta_segments[segment]['y'],
                                                delta_segments[segment]['y'])-min_lat

                        list_x_points_flat_all.append(x_points_flat_seg)
                        list_y_points_flat_all.append(y_points_flat_seg)

                    x_points_flat = np.concatenate(list_x_points_flat_all)
                    y_points_flat = np.concatenate(list_y_points_flat_all)

                    x_points_flat_10m = np.arange(min_lon,max_lon+self.dx,self.dx)-min_lon
                    y_points_flat_10m = np.arange(min_lat,max_lat+self.dy,self.dy)-min_lat

                    out_path_x = f'{self.init.dict_folders["run"]}x.grd'
                    def _one_line(arr):
                        return ' '.join(f'{float(v):.4f}' for v in np.asarray(arr).flatten())
                    with open(out_path_x, 'w') as fh:
                        for idx, element in enumerate(y_points_flat):
                            if element <= 350:
                                line = _one_line(x_points_flat_10m)
                            elif element > 350 and element <= 420:
                                line = _one_line(x_points_flat)
                            else:
                                line = _one_line(x_points_flat_10m)
                            fh.write(line + '\n')

                    list_y_points = []
                    for idx, element in enumerate(x_points_flat):
                        if element <=110:
                            list_y_points.append(y_points_flat_10m)
                        elif element >110 and element <= 160:
                            list_y_points.append(y_points_flat)
                        else:
                            list_y_points.append(y_points_flat_10m)

                    out_path_y = f'{self.init.dict_folders["run"]}y.grd'
                    with open(out_path_y, 'w') as f:
                        for x in zip_longest(*list_y_points, fillvalue=''):
                            formatted = (f'{float(v):12.4f}' if v != '' else ' ' * 12 for v in x)
                            f.write(''.join(formatted) + '\n')

                    with open(f'{self.init.dict_folders["run"]}x.grd', 'r') as file_x:
                        with open(f'{self.init.dict_folders["run"]}y.grd', 'r') as file_y:
                            for line_x, line_y in zip(file_x, file_y):
                                x_vals = [float(v) for v in line_x.split()] if line_x else []
                                y_vals = [float(v) for v in line_y.split()] if line_y else []

                                if len(x_vals) <= len(y_vals):
                                    y_vals = y_vals[:len(x_vals)]
                                elif len(y_vals) < len(x_vals):
                                    y_vals = y_vals + [y_vals[-1]]*(len(x_vals)-len(y_vals))
                                else:
                                    pass

                                try:
                                    geometry
                                except NameError:
                                    geometry = []

                                for xv, yv in zip(x_vals, y_vals):
                                    geometry.append(Point(xv + min_lon, yv + min_lat))
                        coords = [(pt.x, pt.y) for pt in geometry]
                        df = pd.DataFrame({'x': [c[0] for c in coords], 'y': [c[1] for c in coords]})
                        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:9377")
                        out_shp = os.path.join(self.init.dict_folders["input"], "XBeach_domain_grid_points_reef_MSON.shp")
                        gdf.to_file(out_shp)

                    grid_dict={'xfilepath':'x.grd','yfilepath':'y.grd'}

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