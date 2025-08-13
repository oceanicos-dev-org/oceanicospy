import xarray as xr
import pandas as pd
import numpy as np
import glob as glob
import os

from .. import utils
from ....retrievals import *

class WindForcing():
    def __init__(self,init,domain_number,wind_info=None,filename=None,share_winds=True,use_link=True):
        """
        Parameters
        ----------
        init : object
            An initialization object containing configuration data and folder paths.
        domain_number : int
            Identifier for the domain being processed.
        wind_info : dict or None, optional
            Dictionary containing wind information. If None, winds must be provided via `filename`.
        filename : str or None, optional
            Path to the file containing wind data. If None, wind must be provided via `wind_info`.
        use_link: bool, optional
            If True, creates symbolic links for wind files instead of copying them. Defaults to True.
        share_winds: bool, optional
            If True, shares wind data across domains. Defaults to True.
        """
        self.init = init
        self.domain_number = domain_number
        self.wind_info = wind_info
        self.input_filename = filename
        self.share_winds = share_winds
        self.use_link = use_link
        print(f'\n*** Initializing winds for domain {self.domain_number} ***\n')

    def _download_ERA5(self,difference_to_UTC, filepath=None):
        """
        Downloads ERA5 wind data for the specified region and time period.
        This method initializes an ERA5Downloader object with the required wind variables and region boundaries,
        downloads the data, and formats it to local time.
        Parameters
        ----------
        difference_to_UTC : int
            The time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            The file path where the downloaded ERA5 data will be saved. If None, a default path is used.
        """
    
        ERA5download_obj = ERA5Downloader(
                        variables=['10m_u_component_of_wind', '10m_v_component_of_wind'],
                        lon_min=self.wind_info['lon_ll_wind'],
                        lon_max=self.wind_info['lon_ll_wind'] + (self.wind_info['meshes_x_wind'] * self.wind_info['dx_wind']),
                        lat_min=self.wind_info['lat_ll_wind'],
                        lat_max=self.wind_info['lat_ll_wind'] + (self.wind_info['meshes_y_wind'] * self.wind_info['dy_wind']),
                        start_datetime_local=self.init.ini_date,
                        end_datetime_local=self.init.end_date,
                        difference_to_UTC=difference_to_UTC,
                        output_path=filepath
                        )
        ERA5download_obj.download()
        ERA5download_obj.format_to_localtime()
        print("\t ERA5 wind data downloaded successfully")

    def _ERA5_nc_to_ascii(self,era5_filename,ascii_filename):
        """
        Converts ERA5 wind data from a NetCDF file to a custom ASCII format.
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

    def get_winds_from_ERA5(self,difference_to_UTC,filename='winds_era5.nc',override=False):
        """
        Downloads or verifies the existence of ERA5 wind data for the specified domain.
        This method checks if the ERA5 wind data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wind data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

        """
        filepath = f"{self.init.dict_folders["input"]}domain_0{self.domain_number}/{filename}"
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

    def write_ERA5_ascii(self,era5_filename,ascii_filename):
        """
        Converts ERA5 wind data from NetCDF to ASCII format and manages file/link placement for SWAN model input.
        Depending on the configuration, this method processes the ERA5 NetCDF wind file, converts it to ASCII format,
        and ensures the resulting file is correctly placed or linked in the appropriate domain directory for model runs.
        It also updates wind information metadata if available.
        Parameters
        ----------
        era5_filename : str
            Path to the input ERA5 NetCDF wind file.
        ascii_filename : str
            Name of the output ASCII file to be generated or linked.
        Returns
        -------
        dict or None
            Updated wind information dictionary if `self.wind_info` is not None, otherwise None.
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

        if self.use_link:
            if utils.verify_file(f'{run_domain_dir}{ascii_filename}'):
                os.remove(f'{run_domain_dir}{ascii_filename}')
            if not utils.verify_link(ascii_filename, run_domain_dir):
                utils.create_link(
                    ascii_filename,
                    origin_domain_dir,
                    run_domain_dir
                )
        else:
            if utils.verify_link(ascii_filename, run_domain_dir):
                utils.remove_link(ascii_filename, run_domain_dir)
            os.system(
                f'cp {origin_domain_dir}/{ascii_filename} '
                f'{run_domain_dir}'
            )

        if self.wind_info!=None:
            self.wind_info.update({"winds.wnd":"winds.wnd"})
            return self.wind_info
        return None

    def fill_wind_section(self,dict_wind_data):
        """
        Replaces and updates the .swn file with the wind configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing winds information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_wind_data)

    def write_constant_wind(self, ascii_filepath):
        """
        Converts CMDS wind data from a NetCDF file to a custom ASCII format.
        Parameters
        ----------
        era5_filename : str
            Name of the CMDS NetCDF file containing wind data (u10, v10, valid_time).
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
        Downloads or verifies the existence of ERA5 wind data for the specified domain.
        This method checks if the ERA5 wind data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wind data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

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
        Downloads or verifies the existence of CMDS wind data for the specified domain.
        This method checks if the CMDS wind data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wind data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

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
        Converts ERA5 wind data from NetCDF to ASCII format and manages file/link placement for SWAN model input.
        Depending on the configuration, this method processes the ERA5 NetCDF wind file, converts it to ASCII format,
        and ensures the resulting file is correctly placed or linked in the appropriate domain directory for model runs.
        It also updates wind information metadata if available.
        Parameters
        ----------
        era5_filename : str
            Path to the input ERA5 NetCDF wind file.
        ascii_filename : str
            Name of the output ASCII file to be generated or linked.
        Returns
        -------
        dict or None
            Updated wind information dictionary if `self.wind_info` is not None, otherwise None.
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

        if self.use_link != None:
            if self.use_link:
                if utils.verify_file(f'{run_domain_dir}{ascii_filename}'):
                    os.remove(f'{run_domain_dir}{ascii_filename}')
                if not utils.verify_link(ascii_filename, run_domain_dir):
                    utils.create_link(
                        ascii_filename,
                        origin_domain_dir,
                        run_domain_dir
                    )
            else:
                if utils.verify_link(ascii_filename, run_domain_dir):
                    utils.remove_link(ascii_filename, run_domain_dir)
                os.system(
                    f'cp {origin_domain_dir}/{ascii_filename} '
                    f'{run_domain_dir}'
                )

        if self.wind_info!=None:
            if not self.share_winds:
                self.wind_info.update({"winds_file":f"../../input/domain_0{self.domain_number}/winds.wnd"})
            else:
                self.wind_info.update({"winds_file":f"../../input/domain_01/winds.wnd"})
            return self.wind_info
        return None

