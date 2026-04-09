import xarray as xr
import pandas as pd
import glob as glob

from pathlib import Path

from .. import utils
from ....retrievals import *

class WindForcing():
    """
    Parameters
    ----------
    init : object
        An initialization object containing configuration data and folder paths.
    domain_number : int
        Identifier for the domain being processed.
    dict_info : dict or None, optional
        Dictionary containing spatial wind information. If None, winds must be provided via `filename`.
    filename : str or None, optional
        Path to the file containing wind data. If None, wind must be provided via `dict_info`.
    share_winds : bool, optional
        If True, shares wind data across domains. Defaults to True.
    use_link : bool or None, optional
        If True, creates symbolic links for wind files instead of copying them.
        If False, copies the files. If None, no file placement is performed.
    """

    def __init__(self,init,domain_number,dict_info=None,filename=None,share_winds=True,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.dict_info = dict_info
        self.filename = filename
        self.share_winds = share_winds
        self.use_link = use_link
        print(f'\n*** Initializing winds for domain {self.domain_number} ***\n')

    def _download_ERA5(self,difference_to_UTC, filepath=None):
        """
        Download ERA5 wind data for the specified region and time period.

        Initializes an ERA5Downloader with the required wind variables and region
        boundaries, downloads the data, and converts it to local time.

        Parameters
        ----------
        difference_to_UTC : int
            Time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            File path where the downloaded ERA5 data will be saved.
        """
        filepath = Path(filepath)
        ERA5download_obj = ERA5Downloader(
                        variables = ['10m_u_component_of_wind', '10m_v_component_of_wind'],
                        lon_min = self.dict_info['lon_ll_corner_wind'],
                        lon_max = self.dict_info['lon_ll_corner_wind'] + (self.dict_info['nx_wind'] * self.dict_info['dx_wind']),
                        lat_min = self.dict_info['lat_ll_corner_wind'],
                        lat_max = self.dict_info['lat_ll_corner_wind'] + (self.dict_info['ny_wind'] * self.dict_info['dy_wind']),
                        start_datetime_local = self.init.ini_date,
                        end_datetime_local = self.init.end_date,
                        difference_to_UTC = difference_to_UTC,
                        output_path = filepath.parent,
                        output_filename = filepath.name
                        )
        ERA5download_obj.download()
        ERA5download_obj.format_to_localtime()
        print("\t ERA5 wind data downloaded successfully")

    def _download_CMDS(self,difference_to_UTC, filepath=None):
        """
        Download CMDS wind data for the specified region and time period.

        Initializes a CMDSDownloader with the required wind variables and region
        boundaries, downloads the data, and converts it to local time.

        Parameters
        ----------
        difference_to_UTC : int
            Time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            File path where the downloaded CMDS data will be saved.
        """
        filepath = Path(filepath)
        CMDSdownload_obj = CMDSDownloader.for_winds(
                        lon_min = self.dict_info['lon_ll_corner_wind'],
                        lon_max = self.dict_info['lon_ll_corner_wind'] + (self.dict_info['nx_wind'] * self.dict_info['dx_wind']),
                        lat_min = self.dict_info['lat_ll_corner_wind'],
                        lat_max = self.dict_info['lat_ll_corner_wind'] + (self.dict_info['ny_wind'] * self.dict_info['dy_wind']),
                        start_datetime_local = self.init.ini_date,
                        end_datetime_local = self.init.end_date,
                        difference_to_UTC = difference_to_UTC,
                        output_path = filepath.parent,
                        output_filename = filepath.name
                        )
        CMDSdownload_obj.download()
        CMDSdownload_obj.format_to_localtime()
        print("\t CMDS wind data downloaded successfully")

    def _ERA5_nc_to_ascii(self,era5_filename,ascii_filename):
        """
        Convert ERA5 wind data from a NetCDF file to a custom ASCII format.

        Parameters
        ----------
        era5_filename : str
            Name of the ERA5 NetCDF file containing wind data (u10, v10, valid_time).
        ascii_filename : str
            Name of the output ASCII file to write the formatted wind data.
        """

        ds_era5 = xr.load_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{era5_filename}',engine='netcdf4')

        v10 = ds_era5.variables['v10'].values
        u10 = ds_era5.variables['u10'].values
        time = pd.to_datetime(ds_era5.variables['valid_time'].values)
        time_to_write = time.format(formatter=lambda x: x.strftime('%Y%m%d.%H%M'))

        file = open(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{ascii_filename}','w')
        for idx,t in enumerate(time_to_write):
            file.write(t)
            file.write('\n')
            u10_to_write=u10[idx]
            v10_to_write=v10[idx]
            file.write(pd.DataFrame(u10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
            file.write(pd.DataFrame(v10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
        file.close()

    def _CMDS_nc_to_ascii(self,cmds_filename,ascii_filename):
        """
        Convert CMDS wind data from a NetCDF file to a custom ASCII format.

        Parameters
        ----------
        cmds_filename : str
            Name of the CMDS NetCDF file containing wind data (eastward_wind,
            northward_wind, time).
        ascii_filename : str
            Name of the output ASCII file to write the formatted wind data.
        """

        ds_cdms = xr.load_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{cmds_filename}',engine='netcdf4')

        v10 = ds_cdms.variables['northward_wind'].values
        u10 = ds_cdms.variables['eastward_wind'].values
        time = pd.to_datetime(ds_cdms.variables['time'].values)
        time_to_write = time.format(formatter=lambda x: x.strftime('%Y%m%d.%H%M'))

        file = open(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{ascii_filename}','w')
        for idx,t in enumerate(time_to_write):
            file.write(t)
            file.write('\n')
            u10_to_write=u10[idx,::-1,:] # the order in the latitude is reversed because higher lats are first
            v10_to_write=v10[idx,::-1,:]
            file.write(pd.DataFrame(u10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
            file.write(pd.DataFrame(v10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
        file.close()

    def get_winds_from_ERA5(self,difference_to_UTC,filename='winds_era5.nc',override=False):
        """
        Download ERA5 wind data for the current domain, or skip if already present.

        Checks if the ERA5 NetCDF file exists in the domain input directory. If not,
        downloads it. When `share_winds` is True, only domain 1 downloads the data;
        other domains reuse it.

        Parameters
        ----------
        difference_to_UTC : int
            Time difference to UTC in hours for local time conversion.
        filename : str, optional
            Name of the ERA5 NetCDF output file. Defaults to ``'winds_era5.nc'``.
        override : bool, optional
            If True, re-downloads the file even if it already exists. Defaults to False.
        """
        filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
        file_exists = utils.verify_file(filepath)

        if not self.share_winds:
            if not file_exists or override:
                self._download_ERA5(difference_to_UTC, filepath=filepath)
            else:
                print("\t ERA5 wind data already exists, skipping download")
        else:
            if self.domain_number == 1:
                if not file_exists or override:
                    self._download_ERA5(difference_to_UTC, filepath=filepath)
                else:
                    print("\t ERA5 wind data already exists, skipping download")
            else:
                    print("\t ERA5 wind data already exists in domain 1, skipping download")

    def get_winds_from_CMDS(self,difference_to_UTC,filename='winds_cmds.nc',override=False):
        """
        Download CMDS wind data for the current domain, or skip if already present.

        Checks if the CMDS NetCDF file exists in the domain input directory. If not,
        downloads it. When `share_winds` is True, only domain 1 downloads the data;
        other domains reuse it.

        Parameters
        ----------
        difference_to_UTC : int
            Time difference to UTC in hours for local time conversion.
        filename : str, optional
            Name of the CMDS NetCDF output file. Defaults to ``'winds_cmds.nc'``.
        override : bool, optional
            If True, re-downloads the file even if it already exists. Defaults to False.
        """
        filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
        file_exists = utils.verify_file(filepath)

        if not self.share_winds:
            if not file_exists or override:
                self._download_CMDS(difference_to_UTC, filepath=filepath)
            else:
                print("\t CMDS wind data already exists, skipping download")
        else:
            if self.domain_number == 1:
                if not file_exists or override:
                    self._download_CMDS(difference_to_UTC, filepath=filepath)
                else:
                    print("\t CMDS wind data already exists, skipping download")
            else:
                    print("\t CMDS wind data already exists in domain 1, skipping download")

    def write_ERA5_ascii(self,era5_filename,ascii_filename):
        """
        Convert ERA5 wind data to ASCII and place it for the SWAN model run.

        Converts the ERA5 NetCDF wind file to ASCII format and ensures the output
        is correctly placed or linked in the domain run directory. When `share_winds`
        is True, only domain 1 performs the conversion; other domains link to it.

        Parameters
        ----------
        era5_filename : str
            Name of the ERA5 NetCDF wind file located in the domain input directory.
        ascii_filename : str
            Name of the output ASCII file to be generated or linked.

        Returns
        -------
        dict or None
            Updated wind information dictionary if ``self.dict_info`` is not None,
            otherwise None.
        """
        
        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

        if not self.share_winds:
            self._ERA5_nc_to_ascii(era5_filename, ascii_filename)
            print(f"\t ERA5 wind data converted to ASCII format and saved as {ascii_filename}")
        else:
            if self.domain_number == 1:
                self._ERA5_nc_to_ascii(era5_filename, ascii_filename)
                print(f"\t ERA5 wind data converted to ASCII format and saved as {ascii_filename}")

            else:
                origin_domain_dir = f'{self.init.dict_folders["input"]}domain_01/'
                print(f"\t ERA5 wind data converted to ASCII format and saved as {ascii_filename} in domain 01, linking to domain {self.domain_number}")

        utils.deploy_forcing_file(ascii_filename, origin_domain_dir, run_domain_dir, self.use_link)

        if self.dict_info!=None:
            if not self.share_winds:
                self.dict_info.update({"winds_file":f"../../input/domain_0{self.domain_number}/winds.wnd"})
            else:
                self.dict_info.update({"winds_file":f"../../input/domain_01/winds.wnd"})
            return self.dict_info
        return None

    def write_CMDS_ascii(self,cdms_filename,ascii_filename):
        """
        Convert CMDS wind data to ASCII and place it for the SWAN model run.

        Converts the CMDS NetCDF wind file to ASCII format and ensures the output
        is correctly placed or linked in the domain run directory. When `share_winds`
        is True, only domain 1 performs the conversion; other domains link to it.

        Parameters
        ----------
        cdms_filename : str
            Name of the CMDS NetCDF wind file located in the domain input directory.
        ascii_filename : str
            Name of the output ASCII file to be generated or linked.

        Returns
        -------
        dict or None
            Updated wind information dictionary if ``self.dict_info`` is not None,
            otherwise None.
        """
        
        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

        if not self.share_winds:
            self._CMDS_nc_to_ascii(cdms_filename, ascii_filename)
            print(f"\t CMDS wind data converted to ASCII format and saved as {ascii_filename}")
        else:
            if self.domain_number == 1:
                self._CMDS_nc_to_ascii(cdms_filename, ascii_filename)
                print(f"\t CMDS wind data converted to ASCII format and saved as {ascii_filename}")

            else:
                origin_domain_dir = f'{self.init.dict_folders["input"]}domain_01/'
                print(f"\t CMDS wind data converted to ASCII format and saved as {ascii_filename} in domain 01, linking to domain {self.domain_number}")

        utils.deploy_forcing_file(ascii_filename, origin_domain_dir, run_domain_dir, self.use_link)

        if self.dict_info!=None:
            if not self.share_winds:
                self.dict_info.update({"winds_file":f"../../input/domain_0{self.domain_number}/winds.wnd"})
            else:
                self.dict_info.update({"winds_file":f"../../input/domain_01/winds.wnd"})

            return self.dict_info

    def use_constant_wind(self,wind_speed,wind_dir):
        """
        Return a constant wind field configuration for the SWAN model.

        Does not perform any file handling. Returns a dictionary with the wind
        speed and direction needed to configure a spatially uniform wind field.

        Parameters
        ----------
        wind_speed : float
            Constant wind speed in meters per second (m/s).
        wind_dir : float
            Constant wind direction in degrees under nautical convention
            (0° = North, 90° = East).

        Returns
        -------
        dict
            Dictionary with keys ``'wind_speed'`` and ``'wind_dir'``.
        """
        constant_wind_info =  {"wind_speed":wind_speed, "wind_dir":wind_dir}

        if self.dict_info != None:
            self.dict_info.update(constant_wind_info)
        else:
            self.dict_info = constant_wind_info
        return self.dict_info

    def fill_wind_section(self):
        """
        Write wind configuration into the SWAN run file for the current domain. 
        Uses the information in ``self.dict_info`` to fill the appropriate section of the .swn file.

        Raises
        ------
        ValueError
            If no wind information was provided at initialization.
        """

        if self.dict_info == None:
            raise ValueError(f'Wind information is not provided for domain {self.domain_number}.')

        print (f'\n \t*** Adding/Editing winds information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.dict_info)

    # def write_constant_wind(self, ascii_filepath):
    #     """
    #     Writes constant wind data to an ASCII file.
    #     Args:
    #         ascii_filepath (str): Path to the output ASCII file.
    #     Returns:
    #         dict: Dictionary containing wind parameters.
    #     """
    #     ds=pd.read_csv(f'{self.dict_folders["input"]}{self.input_filename}',delimiter=' ')
    #     dates=pd.date_range(self.ini_date,self.end_date,freq='1h')
    #     ds=ds.set_index(dates)
    #     ds_to_save=ds[['Dir','Vel']]
    #     ds_to_save.index=ds_to_save.index.strftime('%Y%m%d.%H%M%S')
        
    #     file = open(f'{self.dict_folders["run"]}{ascii_filepath}','w')
    #     for idx,t in enumerate(ds_to_save.index):
    #         file.write(t)
    #         file.write('\n')
    #         ds_to_save['Dir_to'] = (ds_to_save['Dir'] + 180) % 360
    #         u10_to_write = ds_to_save['Vel'].iloc[idx] * np.sin(np.deg2rad(ds_to_save['Dir_to'].iloc[idx]))
    #         v10_to_write = ds_to_save['Vel'].iloc[idx] * np.cos(np.deg2rad(ds_to_save['Dir_to'].iloc[idx]))

    #         u10_to_write = round(u10_to_write,2)
    #         v10_to_write = round(v10_to_write,2)

    #         u10_to_write = u10_to_write*np.ones((25,25))
    #         v10_to_write = v10_to_write*np.ones((25,25))
                        
    #         file.write(pd.DataFrame(u10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
    #         file.write(pd.DataFrame(v10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))

    #     file.close()
    
    #     ll_lon_on,ll_lat_on=4931900,2799400 #quemado

    #     self.wind_params=dict(lon_ll_wind=ll_lon_on,lat_ll_wind=ll_lat_on,
    #                           meshes_x_wind=24,meshes_y_wind=24,
    #                           dx_wind=2000,dy_wind=2000,ini_wind_date=ds_to_save.index[0],
    #                           dt_wind_hours=1,end_wind_date=ds_to_save.index[-1])
    #     return self.wind_params

    # def winds_from_user(self):
    #     wind_file_path = glob.glob(f'{self.dict_folders["input"]}domain_0{self.domain_number}/*.wnd')[0]
    #     wind_filename=wind_file_path.split('/')[-1]

    #     if not utils.verify_link(wind_filename,f'{self.dict_folders["run"]}domain_0{self.domain_number}/'):
    #         utils.create_link(wind_filename,f'{self.dict_folders["input"]}domain_0{self.domain_number}/',
    #                             f'{self.dict_folders["run"]}domain_0{self.domain_number}/')

    #     # os.system(f'rsync {self.dict_folders["input"]}domain_0{self.domain_number}/{wind_filename}\
    #     #                         {self.dict_folders["run"]}domain_0{self.domain_number}/')

    #     if self.wind_info!=None:
    #         self.wind_info.update({"winds.wnd":wind_filename})
    #         return self.wind_info

