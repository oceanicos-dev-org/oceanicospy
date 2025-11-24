import xarray as xr
import pandas as pd
from pyproj import Proj, transform
import glob as glob
import numpy as np

from .. import utils
from ....retrievals import *

class WindForcing():
    def __init__ (self,init,input_filename=None,wind_info=None,use_link=None):
        self.init = init
        self.input_filename=input_filename
        self.wind_info = wind_info
        self.use_link = use_link
        print(f'\n*** Initializing winds ***\n')

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

    def _download_CMDS(self,difference_to_UTC, filepath=None):
        """
        Downloads CDMS wind data for the specified region and time period.
        This method initializes an CDMSDownloader object with the required wind variables and region boundaries,
        downloads the data, and formats it to local time.
        Parameters
        ----------
        difference_to_UTC : int
            The time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            The file path where the downloaded ERA5 data will be saved. If None, a default path is used.
        """
    
        CMDSdownload_obj = CMDSDownloader.for_winds(
                        lon_min=self.wind_info['lon_ll_wind'],
                        lon_max=self.wind_info['lon_ll_wind'] + (self.wind_info['meshes_x_wind'] * self.wind_info['dx_wind']),
                        lat_min=self.wind_info['lat_ll_wind'],
                        lat_max=self.wind_info['lat_ll_wind'] + (self.wind_info['meshes_y_wind'] * self.wind_info['dy_wind']),
                        start_datetime_local=self.init.ini_date,
                        end_datetime_local=self.init.end_date,
                        difference_to_UTC=difference_to_UTC,
                        output_path=filepath
                        )
        CMDSdownload_obj.download()
        CMDSdownload_obj.format_to_localtime()
        print("\t CMDS wind data downloaded successfully")

    def get_winds_from_ERA5(self,difference_to_UTC,filename='winds_era5.nc',override=False):
        """
        Downloads or verifies the existence of ERA5 wind data for the specified domain.
        This method checks if the ERA5 wind data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wind data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

        """
        filepath = f"{self.init.dict_folders['input']}{filename}"
        file_exists = utils.verify_file(filepath)

        if not file_exists or override:
                self._download_ERA5(difference_to_UTC, filepath=filepath)
        else:
                print("\t ERA5 wind data already exists, skipping download")

    def _ERA5_nc_to_ascii(self,era5_filename,ascii_filename,lon_target=None,lat_target=None):
        """
        Converts ERA5 wind data from a NetCDF file to a custom ASCII format.
        Parameters
        ----------
        era5_filename : str
            Name of the ERA5 NetCDF file containing wind data (u10, v10, valid_time).
        ascii_filename : str
            Name of the output ASCII file to write the formatted wind data.
        """

        ds_era5 = xr.load_dataset(f'{self.init.dict_folders["input"]}{era5_filename}',engine='netcdf4')

        v10 = ds_era5.variables['v10'].values
        u10 = ds_era5.variables['u10'].values
        time = pd.to_datetime(ds_era5.variables['valid_time'].values)
        mask = (time >= self.init.ini_date) & (time <= self.init.end_date)
        if not mask.any():
            raise ValueError(f"No ERA5 data within start/end dates: {self.init.ini_date} - {self.init.end_date}")
        time = time[mask]
        u10 = u10[mask]
        v10 = v10[mask]
        time_to_write = (time - time[0]).total_seconds().astype(int).tolist()

        wind_speed = np.sqrt((v10**2)+(u10**2))
        wind_dir_cart = np.degrees(np.arctan2(v10,u10))
        wind_dir_naut = (270-wind_dir_cart)%360 # this needs to be verified somehow

        if lon_target == None and lat_target == None:
            df_to_save=pd.DataFrame({'Time':time_to_write,'Vel':wind_speed[:,-1,0],'Dir':wind_dir_naut[:,-1,0]},index=time)
        else:
            lats = ds_era5.variables['latitude'].values
            lons = ds_era5.variables['longitude'].values
            if lon_target <0:
                lon_target += 360
            lat_idx = np.argmin(np.abs(lats - lat_target))
            lon_idx = np.argmin(np.abs(lons - lon_target))
            df_to_save=pd.DataFrame({'Time':time_to_write,'Vel':wind_speed[:,lat_idx,lon_idx],'Dir':wind_dir_naut[:,lat_idx,lon_idx]},index=time)

        df_to_save.to_csv(f'{self.init.dict_folders["input"]}{ascii_filename}',sep=' ',header=False,index=False)

        self.wind_params=dict(windfilepath=f'{ascii_filename}')
        return self.wind_params

    def write_ERA5_ascii(self,era5_filename,ascii_filename,lon_target=None,lat_target=None):
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
        
        run_domain_dir = f'{self.init.dict_folders["run"]}'
        origin_domain_dir = f'{self.init.dict_folders["input"]}'

        self._ERA5_nc_to_ascii(era5_filename, ascii_filename, lon_target, lat_target)
        print(f"\t ERA5 wind data converted to ASCII format and saved as {ascii_filename}")

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
                    utils.delete_link(ascii_filename, run_domain_dir)
                os.system(
                    f'cp {origin_domain_dir}/{ascii_filename} '
                    f'{run_domain_dir}'
                )
        if self.wind_info!=None:
            self.wind_info.update({"windfilepath":"winds.wnd"})
            return self.wind_info
        return None

    def write_CMDS_ascii(self,cmds_filename,ascii_filename):
        """
        Converts CMDS wind data from NetCDF to ASCII format and manages file/link placement for SWAN model input.
        Depending on the configuration, this method processes the CMDS NetCDF wind file, converts it to ASCII format,
        and ensures the resulting file is correctly placed or linked in the appropriate domain directory for model runs.
        It also updates wind information metadata if available.
        Parameters
        ----------
        era5_filename : str
            Path to the input CMDS NetCDF wind file.
        ascii_filename : str
            Name of the output ASCII file to be generated or linked.
        Returns
        -------
        dict or None
            Updated wind information dictionary if `self.wind_info` is not None, otherwise None.
        """
        
        run_domain_dir = f'{self.init.dict_folders["run"]}'
        origin_domain_dir = f'{self.init.dict_folders["input"]}'

        self._CMDS_nc_to_ascii(cmds_filename, ascii_filename)
        print(f"\t ERA5 wind data converted to ASCII format and saved as {ascii_filename}")

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
                    utils.delete_link(ascii_filename, run_domain_dir)
                os.system(
                    f'cp {origin_domain_dir}/{ascii_filename} '
                    f'{run_domain_dir}'
                )
        
        if self.wind_info!=None:
            self.wind_info.update({"windfilepath":"winds.wnd"})
            return self.wind_info
        return None

    def txt_from_user(self):
        """
        Reads wind parameters from a user-defined file and returns them as a dictionary.
        """
        wind_file_path = glob.glob(f'{self.dict_folders["input"]}*.wnd')[0]
        wind_filename = wind_file_path.split('/')[-1]

        if not utils.verify_link(wind_filename,f'{self.dict_folders["run"]}/'):
            utils.create_link(wind_filename,f'{self.dict_folders["input"]}/',
                                f'{self.dict_folders["run"]}/')

        self.wind_info = {"windfilepath":wind_filename}
        return self.wind_info

    def fill_wind_section(self,dict_wind_data):
        """
        Replaces and updates the .swn file with the wind configuration for a specific domain.
        """
        print (f'\n*** Adding/Editing winds information for domain in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',dict_wind_data)

    # def write_constant_wind(self, ascii_filepath):
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