import numpy as np
import glob as glob
from .. import utils

class GridMaker():
    """
    GridMaker is a utility class for generating and managing the grid information for SWAN.

    Parameters
    ----------
    init : object
        An initialization object containing configuration data and folder paths.
    dx : float
        Grid spacing in the x-direction (longitude).
    dy : float
        Grid spacing in the y-direction (latitude).
    domain_number : int
        Identifier for the domain being processed.
    grid_info : dict, optional
        User-provided grid information dictionary.

    Methods
    -------
    params_from_bathy():
        Extracts grid parameters from a bathymetry file, calculating extents and grid size based on bathymetric data.
    params_from_user():
        Retrieves grid parameters provided by the user. Raises ValueError if not set.
    fill_grid_section(dict_grid_data):
        Fills or updates the grid section in the configuration file for the specified domain using provided grid data.
    """

    def __init__(self,init,domain_number,grid_info=None,dx=None,dy=None):
        """
        Initializes the gridmaker object with the specified parameters.

        Parameters:
        -----------
            init: object
                Initialization parameter for the gridmaker.
            domain_number: int
                Identifier for the computational domain.
            grid_info: dict or None, optional
                Additional information about the grid. Defaults to None.
            dx: float, optional
                Grid spacing in the x-direction.
            dy: float, optional
                Grid spacing in the y-direction.

        """

        self.init = init
        self.domain_number = domain_number
        self.grid_info = grid_info
        self.dx = dx
        self.dy = dy     
        print(f'\n*** Initializing gridmaker for domain {self.domain_number} ***\n')

    def params_from_bathy(self):
        if self.init.dict_ini_data["nested_domains"]>0:
            bathy_file_path = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.dat')[0]
        else:
            bathy_file_path = glob.glob(f'{self.init.dict_folders["input"]}*.dat')[0]

        data = np.loadtxt(bathy_file_path)
        longitude = data[:, 0]
        latitude = data[:, 1]
        elevation = data[:, 2]

        min_longitude = np.min(longitude)
        min_latitude = np.min(latitude)

        max_longitude = np.max(longitude)
        max_latitude = np.max(latitude)
        min_longitude = int(np.ceil(min_longitude / 100) * 100)
        max_longitude = int(np.floor(max_longitude / 100) * 100)
        min_latitude = int(np.ceil(min_latitude / 100) * 100)
        max_latitude = int(np.floor(max_latitude / 100) * 100)

        x_extent=max_longitude-min_longitude
        y_extent=max_latitude-min_latitude

        nx = int(x_extent/self.dx)
        ny = int(y_extent/self.dy)
        
        grid_dict={'lon_ll_corner':min_longitude,'lat_ll_corner':min_latitude,'x_extent':x_extent,'y_extent':y_extent,'nx':nx,'ny':ny}
        for key,value in grid_dict.items():
            grid_dict[key]=str(value)

        return grid_dict
    
    def params_from_user(self):
        """
        Retrieves grid parameters provided by the user.
        Returns:
        --------
            dict: The grid information if it has been set.
        """
        if self.grid_info is not None:
            return self.grid_info
        else:
            raise ValueError("Grid information has not been provided by the user (self.grid_info is None).")

    def fill_grid_section(self,dict_grid_data):
        """
        Replaces and updates the .swn file with the grid configuration for a specific domain.
        """

        dict_grid_data["domain_number"]=self.domain_number

        print (f'\n \t*** Adding/Editing grid information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_grid_data)