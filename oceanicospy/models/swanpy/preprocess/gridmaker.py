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
    domain_number : int
        Identifier for the domain being processed.
    grid_info : dict, optional
        User-provided grid information dictionary.
    dx : float
        Grid spacing in the x-direction (longitude).
    dy : float
        Grid spacing in the y-direction (latitude).

    Notes
    -----
    This class is used to generate and manage grid information for SWAN simulations.
    """

    def __init__(self, init, domain_number, grid_info = None, dx = None, dy = None):
        self.init = init
        self.domain_number = domain_number
        self.grid_info = grid_info
        self.dx = dx
        self.dy = dy     
        print(f'\n*** Initializing gridmaker for domain {self.domain_number} ***\n')

    def get_info_from_bathy(self):
        """
        Extracts grid parameters from the bathymetry file for the specified domain.

        Reads the `.dat` bathymetry file, computes the geographic extents, and derives
        the number of grid cells in each direction based on `dx` and `dy`.

        Returns
        -------
        dict
            Dictionary with string-valued grid parameters: ``lon_ll_corner``,
            ``lat_ll_corner``, ``x_extent``, ``y_extent``, ``nx``, and ``ny``.
        """
        if self.init.dict_ini_data["nested_domains"]>0:
            bathy_file_path = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.dat')[0]
        else:
            bathy_file_path = glob.glob(f'{self.init.dict_folders["input"]}*.dat')[0]

        data = np.loadtxt(bathy_file_path)
        longitude = data[:, 0]
        latitude = data[:, 1]

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
    
    def get_info_from_user(self):
        """
        Retrieves grid parameters provided by the user.

        The grid_info dictionary should contain the following keys: 
        ``lon_ll_corner``: longitude of the lower-left corner of the grid
        ``lat_ll_corner``: latitude of the lower-left corner of the grid
        ``x_extent``: total extent of the grid in the x-direction (longitude)
        ``y_extent``: total extent of the grid in the y-direction (latitude)
        ``nx`` : number of grid cells in the x-direction
        ``ny``: number of grid cells in the y-direction
        
        All values should be convertible to strings.

        Returns
        -------
        dict
            The ``grid_info`` dictionary supplied at initialisation.

        Raises
        ------
        ValueError
            If ``grid_info`` was not provided (is ``None``).
        """
        if self.grid_info is not None:
            return self.grid_info
        else:
            raise ValueError("Grid information has not been provided by the user (self.grid_info is None).")

    def fill_grid_section(self,dict_grid_data):
        """
        Replaces and updates the `.swn` file with the grid configuration for a specific domain.

        Parameters
        ----------
        dict_grid_data : dict
            Dictionary containing the grid parameters to be written into the configuration file.
        """

        dict_grid_data["domain_number"] = self.domain_number

        print (f'\n \t*** Adding/Editing grid information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_grid_data)