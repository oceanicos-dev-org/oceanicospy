import numpy as np
import glob as glob
from scipy.interpolate import griddata
import os
from .. import utils

class BathyMaker():
    """"
    BathyMaker is a utility class for generating and managing the bathymetry information for SWAN.

    Attributes
    ----------
    init : object
        Initialization object with configuration and folder paths.
    domain_number : int
        Domain identifier.
    bathy_info : dict or None
        Bathymetric information dictionary.
    filename : str or None
        Bathymetry file name.
    dx_bat : float or None
        Bathymetry grid spacing.
    use_link : bool
        Whether to use symbolic links for bathymetry files.
    Methods
    -------
    ascii_from_user()
        Handles bathymetry files provided by the user, creating links or copying files as needed.
    xyz2asc(nodata_value)
        Converts bathymetry data from XYZ format to ESRI ASCII Grid format, interpolating and handling missing data.
    fill_bathy_section(dict_bathy_data)
        Updates the configuration file with bathymetry information for the specified domain.
    """

    def __init__(self, init, domain_number, bathy_info=None, filename=None, dx_bat=None, use_link = None):
        """
        Parameters
        ----------
        init : object
            An initialization object containing configuration data and folder paths.
        domain_number : int
            Identifier for the domain being processed.
        bathy_info : dict or None, optional
            Dictionary containing bathymetric information. If None, bathymetry must be provided via `filename`.
        filename : str or None, optional
            Path to the file containing bathymetric data. If None, bathymetry must be provided via `bathy_info`.
        dx_bat : float or None, optional
            Grid spacing for the bathymetric data. If None, default spacing is used.
        use_link: bool, optional
            If True, creates symbolic links for bathymetry files instead of copying them. Defaults to True.
        """

        self.init = init
        self.domain_number = domain_number
        self.bathy_info = bathy_info
        self.filename = filename
        self.dx_bat = dx_bat
        self.use_link = use_link
        print(f'\n*** Initializing bathymaker for domain {self.domain_number} ***\n')

    def get_from_user(self):
        """
        Handles the selection and linking or copying of a bathymetry file for the current domain.
        This method searches for a `.bot` bathymetry file in the input directory for the specified domain.

        Returns:
        --------
            dict or None: The updated `bathy_info` dictionary if it exists, otherwise None.
        """
    
        bathy_filepaths = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.bot')
        if not bathy_filepaths:
            raise FileNotFoundError(f'Bathymetry file not found in {self.init.dict_folders["input"]}domain_0{self.domain_number}/ or file extension is not .bot')
        bathy_filepath = bathy_filepaths[0]
        bathy_filename = bathy_filepath.split('/')[-1]

        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'

        if self.use_link !=None:
            if self.use_link:
                if utils.verify_file(f'{run_domain_dir}{bathy_filename}'):
                    os.remove(f'{run_domain_dir}{bathy_filename}')
                if not utils.verify_link(bathy_filename, run_domain_dir):
                    utils.create_link(
                        bathy_filename,
                        f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/',
                        run_domain_dir
                    )
            else:
                if utils.verify_link(bathy_filename, run_domain_dir):
                    utils.remove_link(bathy_filename, run_domain_dir)
                os.system(
                    f'cp {self.init.dict_folders["input"]}domain_0{self.domain_number}/{bathy_filename} '
                    f'{run_domain_dir}'
                )

        if self.bathy_info!=None:
            self.bathy_info.update({"bathy_file":f"../../input/domain_0{self.domain_number}/{bathy_filename}"})
            return self.bathy_info

    def xyz2asc(self,nodata_value):
        """
        Converts bathymetry data from XYZ format to ESRI ASCII Grid format.

        Args:
            nodata_value (float): The value to replace NaN values in the grid.

        Returns:
            dict: A dictionary containing the metadata of the generated grid.
        """
        bathy_xyz_path = glob.glob(f'{self.dict_folders["input"]}*.dat')[0]
        ascfile = f'{self.dict_folders["run"]}{self.filename}.bot'
        np.set_printoptions(formatter={'float_kind':'{:f}'.format})
        # Read bathymetry file
        longitude,latitude,z = np.loadtxt(bathy_xyz_path, delimiter=' ', unpack=True)

        min_longitude = np.min(longitude)
        min_latitude = np.min(latitude)

        max_longitude = np.max(longitude)
        max_latitude = np.max(latitude)

        min_longitude = int(np.ceil(min_longitude / 100) * 100)
        max_longitude = int(np.floor(max_longitude / 100) * 100)
        min_latitude = int(np.ceil(min_latitude / 100) * 100)
        max_latitude = int(np.floor(max_latitude / 100) * 100)

        xmax=max_longitude
        xmin=min_longitude
        ymax=max_latitude
        ymin=min_latitude

        nx_bathy = int((xmax - xmin)/self.dx_bat)
        ny_bathy = int((ymax - ymin)/self.dx_bat)
        # Generate grid with data
        xi, yi = np.mgrid[xmin:xmax:(nx_bathy+1)*1j, ymin:ymax:(ny_bathy+1)*1j]

        # Interpolate bathymetry. Method can be 'linear', 'nearest' or 'cubic'
        zi = griddata((longitude,latitude), z, (xi, yi), method='linear')
        # Change Nans for values
        zi[np.isnan(zi)] = nodata_value
        # Flip array in the left/right direction
        zi = np.fliplr(zi)
        # Transpose it
        zi = zi.T
        # Write ESRI ASCII Grid file
        zi_str = np.where(zi == nodata_value, str(nodata_value), np.round(zi, 3))
        np.savetxt(ascfile, zi_str, fmt='%8s', delimiter=' ')
        print('File %s saved successfuly.' % ascfile)

        dict_asc={'lon_ll_bat_corner':min_longitude,'lat_ll_bat_corner':min_latitude,'x_bot':nx_bathy,'y_bot':ny_bathy,'spacing_x':self.dx_bat,'spacing_y':self.dx_bat}
        for key,value in dict_asc.items():
            dict_asc[key]=str(value)
        return dict_asc
    

    def fill_bathy_section(self,dict_bathy_data):
        """
        Replaces and updates the .swn file with the bathymetry configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing bathymetry information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_bathy_data)


