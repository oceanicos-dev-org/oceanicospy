import glob as glob
from scipy.interpolate import griddata
from pathlib import Path
from .... import utils

class BathyMaker:
    """
    BathyMaker is a utility class for generating and managing the bathymetry information for SWAN.

    Parameters
    ----------
    init : object
        An initialization object containing configuration data and folder paths.
    domain_number : int
        Identifier for the domain being processed.
    grid_info : dict or None, optional
        Dictionary containing bathymetric information. If None, spatial info for bathymetry must be provided via `get_info_from_bathy()`.
    use_link: bool, optional
        If True, creates symbolic links for bathymetry files instead of copying them. Defaults to True.
    """

    def __init__(self, init, domain_number, bathy_info = None, use_link = None):
        self.init = init
        self.domain_number = domain_number
        self.bathy_info = bathy_info
        self.use_link = use_link
        print(f'\n*** Initializing bathymaker for domain {self.domain_number} ***\n')

    def use_ascii_file_from_user(self):
        """
        Handles the selection and linking or copying of a bathymetry file for the current domain.

        Searches for a `.bot` bathymetry file in the input directory for the specified domain.
        Depending on ``use_link``, the file is either symlinked or physically copied into the
        run directory.

        Returns
        -------
        dict or None
            The updated ``bathy_info`` dictionary if it was provided at initialisation,
            otherwise ``None``.

        Raises
        ------
        FileNotFoundError
            If no `.bot` file is found in the expected input directory.
        """
    
        bathy_filepaths = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.bot')
        if not bathy_filepaths:
            raise FileNotFoundError(f'Bathymetry file not found in {self.init.dict_folders["input"]}domain_0{self.domain_number}/ or file extension is not .bot')
        bathy_filepath = Path(bathy_filepaths[0])
        bathy_filename = bathy_filepath.name

        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'

        utils.deploy_input_file(bathy_filename, f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/', run_domain_dir, self.use_link)
        
        if self.bathy_info!=None:
            self.bathy_info.update({"bathy_file":f"../../input/domain_0{self.domain_number}/{bathy_filename}"})
            return self.bathy_info
        else:
            raise ValueError('No bathymetry information provided at initialization. ' \
            'Bathymetry file has been linked/copied to run directory, but no metadata dictionary to return.')
        
    # TODO: this can be more like a call to gis module to obtain a standardized bathymetry info.
    # def convert_xyz2asc(self,nodata_value):
    #     """
    #     Converts bathymetry data from XYZ format to ESRI ASCII Grid format.

    #     Reads a space-delimited `.dat` file, interpolates the scattered data onto a
    #     regular grid using linear interpolation, and writes the result as an ESRI
    #     ASCII Grid (`.bot`) file.

    #     Parameters
    #     ----------
    #     nodata_value : float
    #         Value used to fill cells where interpolation produced NaN.

    #     Returns
    #     -------
    #     dict
    #         Dictionary with string-valued bathymetry metadata: ``lon_ll_bat_corner``,
    #         ``lat_ll_bat_corner``, ``x_bot``, ``y_bot``, ``spacing_x``, and ``spacing_y``.
    #     """
    #     bathy_xyz_path = glob.glob(f'{self.dict_folders["input"]}*.dat')[0]
    #     ascfile = f'{self.dict_folders["run"]}{self.filename}.bot'
    #     np.set_printoptions(formatter={'float_kind':'{:f}'.format})

    #     # Read bathymetry file
    #     longitude,latitude,z = np.loadtxt(bathy_xyz_path, delimiter=' ', unpack=True)

    #     min_longitude = np.min(longitude)
    #     min_latitude = np.min(latitude)

    #     max_longitude = np.max(longitude)
    #     max_latitude = np.max(latitude)

    #     min_longitude = int(np.ceil(min_longitude / 100) * 100)
    #     max_longitude = int(np.floor(max_longitude / 100) * 100)
    #     min_latitude = int(np.ceil(min_latitude / 100) * 100)
    #     max_latitude = int(np.floor(max_latitude / 100) * 100)

    #     xmax=max_longitude
    #     xmin=min_longitude
    #     ymax=max_latitude
    #     ymin=min_latitude

    #     nx_bathy = int((xmax - xmin)/self.dx_bat)
    #     ny_bathy = int((ymax - ymin)/self.dx_bat)
    #     # Generate grid with data
    #     xi, yi = np.mgrid[xmin:xmax:(nx_bathy+1)*1j, ymin:ymax:(ny_bathy+1)*1j]

    #     # Interpolate bathymetry. Method can be 'linear', 'nearest' or 'cubic'
    #     zi = griddata((longitude,latitude), z, (xi, yi), method='linear')
    #     # Change Nans for values
    #     zi[np.isnan(zi)] = nodata_value
    #     # Flip array in the left/right direction
    #     zi = np.fliplr(zi)
    #     # Transpose it
    #     zi = zi.T
    #     # Write ESRI ASCII Grid file
    #     zi_str = np.where(zi == nodata_value, str(nodata_value), np.round(zi, 3))
    #     np.savetxt(ascfile, zi_str, fmt='%8s', delimiter=' ')
    #     print('File %s saved successfuly.' % ascfile)

    #     self.grid_info={'lon_ll_bat_corner':min_longitude,'lat_ll_bat_corner':min_latitude,'x_bot':nx_bathy,'y_bot':ny_bathy,'spacing_x':self.dx_bat,'spacing_y':self.dx_bat}
    #     for key,value in self.grid_info.items():
    #         self.grid_info[key] = str(value)
    #     return self.grid_info
    
    def fill_bathy_section(self):
        """
        Replaces and updates the `.swn` file with the bathymetry configuration for a specific domain.

        Raises
        ------
        ValueError
            If no bathymetry information was provided at initialization.
        """

        if self.bathy_info == None:
            raise ValueError('No bathymetry information provided at initialization. Cannot fill bathymetry section in configuration file.')

        print (f'\n \t*** Adding/Editing bathymetry information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.bathy_info)
