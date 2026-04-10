import numpy as np
import pandas as pd
import xarray as xr
import os
from pathlib import Path

<<<<<<< HEAD
from .... import utils
from ....retrievals import *

class BoundaryConditions():
    def __init__ (self,init,domain_number,dict_info=None,input_filename=None,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.dict_info = dict_info
        self.input_filename = input_filename
        self.use_link = use_link 
=======
from .. import utils
from ....retrievals import *

class BoundaryConditions():
    """
    Class representing the boundary conditions for a simulation.
    Args:
        input_filename (str): The name of the input file.
        dict_bounds_params (dict): A dictionary containing the boundary parameters.
        list_sides (list): A list of sides.
    Attributes:
        input_filename (str): The name of the input file.
        dict_bounds_params (dict): A dictionary containing the boundary parameters.
        list_sides (list): A list of sides.
        tpar_method_invoked (bool): Indicates whether the tpar method has been invoked.
    Methods:
        tpar_from_rawdata(output_filename): Generate TPAR data from raw data.
        tpar_from_ERA5_wave_data(output_filename): Generate TPAR data from ERA5 wave data.
        fill_boundaries_section(*args): Fill the boundaries section of the simulation.
    """
    def __init__ (self,init,domain_number,input_filename=None,dict_bounds_params=None,list_sides=None,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.input_filename = input_filename
        self.dict_bounds_params = dict_bounds_params
        self.list_sides = list_sides
        self.tpar_method_invoked = False
        self.bounds_var = False
        self.use_link = use_link

        if self.domain_number==1:
            self.isnested = False
        else:
            self.isnested = True
        print(f'\n*** Initializing boundary conditions for domain {self.domain_number} ***\n')

    def _download_ERA5(self,difference_to_UTC, filepath=None,wind_info=None):
        """
        Downloads ERA5 wave data for the specified region and time period.
        This method initializes an ERA5Downloader object with the required wave variables and region boundaries,
        downloads the data, and formats it to local time.
        Parameters
        ----------
        difference_to_UTC : int
            The time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            The file path where the downloaded ERA5 data will be saved. If None, a default path is used.
        """
    
        ERA5download_obj = ERA5Downloader(
                        variables=["mean_wave_direction",
                                   "significant_height_of_combined_wind_waves_and_swell",
                                   "peak_wave_period"],
                        lon_min=wind_info['lon_ll_wind'],
                        lon_max=wind_info['lon_ll_wind'] + (wind_info['meshes_x_wind'] * wind_info['dx_wind']),
                        lat_min=wind_info['lat_ll_wind'],
                        lat_max=wind_info['lat_ll_wind'] + (wind_info['meshes_y_wind'] * wind_info['dy_wind']),
                        start_datetime_local=self.init.ini_date,
                        end_datetime_local=self.init.end_date,
                        difference_to_UTC=difference_to_UTC,
                        output_path=filepath
                        )
        ERA5download_obj.download()
        ERA5download_obj.format_to_localtime()
        print("\t ERA5 wind data downloaded successfully")

    def _download_CMDS(self,difference_to_UTC, filepath=None,wind_info=None):
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
    
        CMDSdownload_obj = CMDSDownloader.for_waves(
                        lon_min=wind_info['lon_ll_wind'],
                        lon_max=wind_info['lon_ll_wind'] + (wind_info['meshes_x_wind'] * wind_info['dx_wind']),
                        lat_min=wind_info['lat_ll_wind'],
                        lat_max=wind_info['lat_ll_wind'] + (wind_info['meshes_y_wind'] * wind_info['dy_wind']),
                        start_datetime_local=self.init.ini_date,
                        end_datetime_local=self.init.end_date,
                        difference_to_UTC=difference_to_UTC,
                        output_path=filepath
                        )
        CMDSdownload_obj.download()
        CMDSdownload_obj.format_to_localtime()
        print("\t CMDS wind data downloaded successfully")

    def _single_tpar_from_ERA5(self,tpar_filename,lati,long,wave_filename='waves_era5.nc'):
        ds = xr.open_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{wave_filename}')
        time = ds.valid_time.values
        strtime = [pd.to_datetime(t).strftime("%Y%m%d.%H%M") for t in time]
        lat_idx = np.argmin(np.abs(ds.latitude.values - lati))
        lon_idx = np.argmin(np.abs(ds.longitude.values - long))

        swh = np.zeros(len(time))
        pp = np.zeros(len(time))
        mwd = np.zeros(len(time))
        for i in range(len(time)):
            data_per_time = ds.isel(valid_time=np.where(ds.valid_time.values==time[i])[0][0],
                            latitude=lat_idx,longitude=lon_idx)
            swh[i] = data_per_time.swh.values
            pp[i] = data_per_time.pp1d.values
            mwd[i] = data_per_time.mwd.values
        df_tpar = pd.DataFrame({'Tiempo':strtime,'Altura':swh,'Periodo':pp,'Direccion':mwd,'dd':40})
        with open (tpar_filename+'.bnd', "w") as file:
                file.write("TPAR \n")
                np.savetxt(file,df_tpar,fmt =('%s  %7.9f  %8.9f  %9.9f  %5.1f'))
        return df_tpar

    def _single_tpar_from_CMDS(self,tpar_filename,lati,long,wave_filename='waves_cmds.nc'):
        ds = xr.open_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{wave_filename}')
        time = ds.time.values
        strtime = [pd.to_datetime(t).strftime("%Y%m%d.%H%M") for t in time]
        lat_idx = np.argmin(np.abs(ds.latitude.values - lati))
        lon_idx = np.argmin(np.abs(ds.longitude.values - long))

        swh = np.zeros(len(time))
        pp = np.zeros(len(time))
        mwd = np.zeros(len(time))
        for i in range(len(time)):
            data_per_time = ds.isel(time=np.where(ds.time.values==time[i])[0][0],
                            latitude=lat_idx,longitude=lon_idx)
            swh[i] = data_per_time.VHM0.values
            pp[i] = data_per_time.VTPK.values
            mwd[i] = data_per_time.VMDR.values
        df_tpar = pd.DataFrame({'Tiempo':strtime,'Altura':swh,'Periodo':pp,'Direccion':mwd,'dd':40})
        with open (tpar_filename+'.bnd', "w") as file:
                file.write("TPAR \n")
                np.savetxt(file,df_tpar,fmt =('%s  %7.9f  %8.9f  %9.9f  %5.1f'))
        return df_tpar

    def get_waves_from_ERA5(self,difference_to_UTC,wind_info_dict,filename='waves_era5.nc',override=False):
        """
        Downloads or verifies the existence of ERA5 wave data for the specified domain.
        This method checks if the ERA5 wave data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wave data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

        """
        if self.isnested == False:
            filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
            file_exists = utils.verify_file(filepath)
            if not file_exists or override:
                self._download_ERA5(difference_to_UTC,wind_info=wind_info_dict,filepath=filepath)
            else:
                print("\t ERA5 wave data already exists, skipping download")

    def get_waves_from_CMDS(self,difference_to_UTC,wind_info_dict,filename='waves_cmds.nc',override=False):
        """
        Downloads or verifies the existence of CMDS wave data for the specified domain.
        This method checks if the CMDS wave data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wave data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

        """
        if self.isnested == False:
            filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
            file_exists = utils.verify_file(filepath)
            if not file_exists or override:
                self._download_CMDS(difference_to_UTC,wind_info=wind_info_dict,filepath=filepath)
            else:
                print("\t CMDS wave data already exists, skipping download")

    def tpar_from_ERA5(self,points_lat,points_lon):
        """
        Generates TPAR files from ERA5 data for specified boundary points.

        For a non-nested domain, this method iterates over the provided latitude and longitude points,
        generating TPAR files for the north, south, east, and west boundaries using ERA5 data.

        Parameters
        ----------
        points_lat : list or array-like
            List of latitude points defining the boundary.
        points_lon : list or array-like
            List of longitude points defining the boundary.
        """
        points_lon = np.array(points_lon)
        if np.any(points_lon<0):
            points_lon += 360
        if self.isnested == False:
            self.input_path = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'
            for idx_lon,lon in enumerate(points_lon):
                self._single_tpar_from_ERA5(f'{self.input_path}TparN2025_{idx_lon+1}',max(points_lat),lon)
                self._single_tpar_from_ERA5(f'{self.input_path}TparS2025_{idx_lon+1}',min(points_lat),lon)

            for idx_lat,lat in enumerate(points_lat):
                self._single_tpar_from_ERA5(f'{self.input_path}TparE2025_{idx_lat+1}',lat,max(points_lon))
                self._single_tpar_from_ERA5(f'{self.input_path}TparO2025_{idx_lat+1}',lat,min(points_lon))

            run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
            origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

            bnd_files = [f for f in os.listdir(self.input_path) if f.endswith('.bnd')]

            for bnd_file in bnd_files:
                if self.use_link != None:
                    if self.use_link:
                        if utils.verify_file(f'{run_domain_dir}{bnd_file}'):
                            os.remove(f'{run_domain_dir}{bnd_file}')
                        if not utils.verify_link(bnd_file, run_domain_dir):
                            utils.create_link(
                                bnd_file,
                                origin_domain_dir,
                                run_domain_dir
                            )
                    else:
                        if utils.verify_link(bnd_file, run_domain_dir):
                            utils.remove_link(bnd_file, run_domain_dir)
                        os.system(
                            f'cp {origin_domain_dir}/{bnd_file} '
                            f'{run_domain_dir}'
                        )
            print(f'\t*** Finished processing boundary files for domain {self.domain_number} ***\n')

    def tpar_from_CMDS(self,points_lat,points_lon):
        """
        Generates TPAR files from CMDS data for specified boundary points.

        For a non-nested domain, this method iterates over the provided latitude and longitude points,
        generating TPAR files for the north, south, east, and west boundaries using CMDS data.

        Parameters
        ----------
        points_lat : list or array-like
            List of latitude points defining the boundary.
        points_lon : list or array-like
            List of longitude points defining the boundary.
        """
        points_lon = np.array(points_lon)
        if self.isnested == False:
            self.input_path = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'
            for idx_lon,lon in enumerate(points_lon):
                self._single_tpar_from_CMDS(f'{self.input_path}TparN2025_{idx_lon+1}',max(points_lat),lon)
                self._single_tpar_from_CMDS(f'{self.input_path}TparS2025_{idx_lon+1}',min(points_lat),lon)

            for idx_lat,lat in enumerate(points_lat):
                self._single_tpar_from_CMDS(f'{self.input_path}TparE2025_{idx_lat+1}',lat,max(points_lon))
                self._single_tpar_from_CMDS(f'{self.input_path}TparO2025_{idx_lat+1}',lat,min(points_lon))

            run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
            origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

            bnd_files = [f for f in os.listdir(self.input_path) if f.endswith('.bnd')]

            for bnd_file in bnd_files:
                if self.use_link != None:
                    if self.use_link:
                        if utils.verify_file(f'{run_domain_dir}{bnd_file}'):
                            os.remove(f'{run_domain_dir}{bnd_file}')
                        if not utils.verify_link(bnd_file, run_domain_dir):
                            utils.create_link(
                                bnd_file,
                                origin_domain_dir,
                                run_domain_dir
                            )
                    else:
                        if utils.verify_link(bnd_file, run_domain_dir):
                            utils.remove_link(bnd_file, run_domain_dir)
                        os.system(
                            f'cp {origin_domain_dir}/{bnd_file} '
                            f'{run_domain_dir}'
                        )
            print(f'\t*** Finished processing boundary files for domain {self.domain_number} ***\n')

    def fill_boundaries_section(self):
        if self.isnested == False:  # This is hardcoded
            string_bounds = f"$ Frontera Norte \n\
BOUN SIDE N CLOCKW VAR FILE 0 '../../input/domain_0{self.domain_number}/TparN2025_1.bnd' 1 & \n\
                        0.1	'../../input/domain_0{self.domain_number}/TparN2025_2.bnd' 1 & \n\
                        0.2	'../../input/domain_0{self.domain_number}/TparN2025_3.bnd' 1  \n\
$ Frontera oeste \n\
BOUN SIDE W CLOCKW VAR FILE 0	'../../input/domain_0{self.domain_number}/TparO2025_1.bnd' 1 & \n\
                        0.1	'../../input/domain_0{self.domain_number}/TparO2025_2.bnd' 1 &\n\
                        0.2	'../../input/domain_0{self.domain_number}/TparO2025_3.bnd' 1 &\n\
                        0.3	'../../input/domain_0{self.domain_number}/TparO2025_4.bnd' 1  \n\
$ Frontera sur\n\
BOUN SIDE S CLOCKW VAR FILE 0	'../../input/domain_0{self.domain_number}/TparS2025_3.bnd' 1 &\n\
                        0.1	'../../input/domain_0{self.domain_number}/TparS2025_2.bnd' 1 &\n\
                        0.2	'../../input/domain_0{self.domain_number}/TparS2025_1.bnd' 1 \n\
$ Frontera este\n\
BOUN SIDE E CLOCKW VAR FILE 0	'../../input/domain_0{self.domain_number}/TparE2025_4.bnd' 1 &\n\
                        0.1	'../../input/domain_0{self.domain_number}/TparE2025_3.bnd' 1 &\n\
                        0.2	'../../input/domain_0{self.domain_number}/TparE2025_2.bnd' 1 &\n\
                        0.3	'../../input/domain_0{self.domain_number}/TparE2025_1.bnd' 1" 
        else:
            string_bounds = f'BOUN NEST \'child0{self.init.dict_ini_data["parent_domains"][self.domain_number]}_0{self.domain_number}.NEST\' CLOSED'
        
        self.dict_boundaries={'values_bounds':string_bounds}
        print (f'\n \t*** Adding/Editing boundary information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.dict_boundaries)
>>>>>>> 5d48c5cb29036c1269753c1321a4ce9d6bc43c90


        if self.init.dict_ini_data["parent_domains"][domain_number] != None:
            self.isnested = True
        else:
            self.isnested = False

        self.boundary_line = None
        print(f'\n*** Initializing boundary conditions for domain {self.domain_number} ***\n')

    def _download_ERA5(self,difference_to_UTC, filepath=None,wind_info=None):
        """
        Downloads ERA5 wave data for the specified region and time period.
        This method initializes an ERA5Downloader object with the required wave variables and region boundaries,
        downloads the data, and formats it to local time.
        Parameters
        ----------
        difference_to_UTC : int
            The time difference to UTC in hours for local time conversion.
        filepath : str or None, optional
            The file path where the downloaded ERA5 data will be saved. If None, a default path is used.
        """
        filepath = Path(filepath)
        ERA5download_obj = ERA5Downloader(
                        variables = ["mean_wave_direction",
                                   "significant_height_of_combined_wind_waves_and_swell",
                                   "peak_wave_period"],
                        lon_min = wind_info['lon_ll_corner_wind'],
                        lon_max = wind_info['lon_ll_corner_wind'] + (wind_info['nx_wind'] * wind_info['dx_wind']),
                        lat_min = wind_info['lat_ll_corner_wind'],
                        lat_max = wind_info['lat_ll_corner_wind'] + (wind_info['ny_wind'] * wind_info['dy_wind']),
                        start_datetime_local = self.init.ini_date,
                        end_datetime_local = self.init.end_date,
                        difference_to_UTC = difference_to_UTC,
                        output_path = filepath.parent,
                        output_filename = filepath.name
                        )
        ERA5download_obj.download()
        ERA5download_obj.format_to_localtime()
        print("\t ERA5 wind data downloaded successfully")

<<<<<<< HEAD
    def _download_CMDS(self,difference_to_UTC, filepath=None,wind_info=None):
=======
        output_file_path = f'{self.dict_folders["run"]}{output_filename}'
        
        # Open the file in write mode and write the first line
        with open(output_file_path, 'w') as f:
            f.write('TPAR\n')
    
        # Append the dataset to the file
        formatted_data = file_to_save.to_string(header=False,index=True,float_format='{:7.2f}'.format)

        with open(output_file_path, 'a') as f:
            f.write(formatted_data)

    def tpar_from_ERA5_wave_data_pre(self,output_filename):
>>>>>>> 5d48c5cb29036c1269753c1321a4ce9d6bc43c90
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
        filepath = Path(filepath)
        CMDSdownload_obj = CMDSDownloader.for_waves(
                        lon_min = wind_info['lon_ll_corner_wind'],
                        lon_max = wind_info['lon_ll_corner_wind'] + (wind_info['nx_wind'] * wind_info['dx_wind']),
                        lat_min = wind_info['lat_ll_corner_wind'],
                        lat_max = wind_info['lat_ll_corner_wind'] + (wind_info['ny_wind'] * wind_info['dy_wind']),
                        start_datetime_local = self.init.ini_date,
                        end_datetime_local = self.init.end_date,
                        difference_to_UTC = difference_to_UTC,
                        output_path = filepath.parent,
                        output_filename = filepath.name
                        )
        CMDSdownload_obj.download()
        CMDSdownload_obj.format_to_localtime()
        print("\t CMDS wind data downloaded successfully")

<<<<<<< HEAD
    def _single_tpar_from_ERA5(self,tpar_filename,lati,long,wave_filename='waves_era5.nc'):
        ds = xr.open_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{wave_filename}')
        time = ds.valid_time.values
        strtime = [pd.to_datetime(t).strftime("%Y%m%d.%H%M") for t in time]
        lat_idx = np.argmin(np.abs(ds.latitude.values - lati))
        lon_idx = np.argmin(np.abs(ds.longitude.values - long))

        swh = np.zeros(len(time))
        pp = np.zeros(len(time))
        mwd = np.zeros(len(time))
        for i in range(len(time)):
            data_per_time = ds.isel(valid_time=np.where(ds.valid_time.values==time[i])[0][0],
                            latitude=lat_idx,longitude=lon_idx)
            swh[i] = data_per_time.swh.values
            pp[i] = data_per_time.pp1d.values
            mwd[i] = data_per_time.mwd.values
        df_tpar = pd.DataFrame({'Tiempo':strtime,'Altura':swh,'Periodo':pp,'Direccion':mwd,'dd':40})
        with open (tpar_filename+'.bnd', "w") as file:
                file.write("TPAR \n")
                np.savetxt(file,df_tpar,fmt =('%s  %7.9f  %8.9f  %9.9f  %5.1f'))
        return df_tpar

    def _single_tpar_from_CMDS(self,tpar_filename,lati,long,wave_filename='waves_cmds.nc'):
        ds = xr.open_dataset(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{wave_filename}')
        time = ds.time.values
        strtime = [pd.to_datetime(t).strftime("%Y%m%d.%H%M") for t in time]
        lat_idx = np.argmin(np.abs(ds.latitude.values - lati))
        lon_idx = np.argmin(np.abs(ds.longitude.values - long))

        swh = np.zeros(len(time))
        pp = np.zeros(len(time))
        mwd = np.zeros(len(time))
        for i in range(len(time)):
            data_per_time = ds.isel(time=np.where(ds.time.values==time[i])[0][0],
                            latitude=lat_idx,longitude=lon_idx)
            swh[i] = data_per_time.VHM0.values
            pp[i] = data_per_time.VTPK.values
            mwd[i] = data_per_time.VMDR.values
        df_tpar = pd.DataFrame({'Tiempo':strtime,'Altura':swh,'Periodo':pp,'Direccion':mwd,'dd':40})
        with open (tpar_filename+'.bnd', "w") as file:
                file.write("TPAR \n")
                np.savetxt(file,df_tpar,fmt =('%s  %7.9f  %8.9f  %9.9f  %5.1f'))
        return df_tpar

    def _process_boundary_points(self,points_lat,points_lon,single_tpar_fn):
        if self.isnested:
            return
        self.input_path = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'
        for idx_lon,lon in enumerate(points_lon):
            single_tpar_fn(f'{self.input_path}TparN_{idx_lon+1}',max(points_lat),lon)
            single_tpar_fn(f'{self.input_path}TparS_{idx_lon+1}',min(points_lat),lon)

        for idx_lat,lat in enumerate(points_lat):
            single_tpar_fn(f'{self.input_path}TparE_{idx_lat+1}',lat,max(points_lon))
            single_tpar_fn(f'{self.input_path}TparW_{idx_lat+1}',lat,min(points_lon))

        self._copy_or_link_bnd_files()
        print(f'\t*** Finished processing boundary files for domain {self.domain_number} ***\n')

    def _copy_or_link_bnd_files(self):
        if self.use_link is None:
            return
        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

        bnd_files = [f for f in os.listdir(self.input_path) if f.endswith('.bnd')]

        for bnd_file in bnd_files:
            utils.deploy_input_file(bnd_file, origin_domain_dir, run_domain_dir, self.use_link)

    def get_waves_from_ERA5(self,difference_to_UTC,wind_info_dict,filename='waves_era5.nc',override=False):
        """
        Downloads or verifies the existence of ERA5 wave data for the specified domain.
        This method checks if the ERA5 wave data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wave data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

=======
        output_file_path = f'{self.dict_folders["run"]}{output_filename}'
        
        # Open the file in write mode and write the first line
        with open(output_file_path, 'w') as f:
            f.write('TPAR\n')
    
        # Append the dataset to the file
        formatted_data = file_to_save.to_string(header=False,index=True,float_format='{:7.2f}'.format)

        with open(output_file_path, 'a') as f:
            f.write(formatted_data)
    
    def tpar_from_user(self):
        self.tpar_method_invoked=True
        self.bounds_var=True

    def fill_boundaries_section_v2(self,*args):
        """
        Fill the boundaries section of the simulation.
        Args:
            *args: Variable length argument list.
        Returns:
            None
>>>>>>> 5d48c5cb29036c1269753c1321a4ce9d6bc43c90
        """
        if self.isnested == False:
            filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
            file_exists = utils.verify_file(filepath)
            if not file_exists or override:
                self._download_ERA5(difference_to_UTC,wind_info=wind_info_dict,filepath=filepath)
            else:
                print("\t ERA5 wave data already exists, skipping download")

    def get_waves_from_CMDS(self,difference_to_UTC,wind_info_dict,filename='waves_cmds.nc',override=False):
        """
        Downloads or verifies the existence of CMDS wave data for the specified domain.
        This method checks if the CMDS wave data NetCDF file exists in the input directory for the current domain.
        If the file does not exist, it downloads the wave data using the parameters specified in `self.wind_info`
        and saves it to the appropriate location. If the file already exists, the download is skipped.

        """
        if self.isnested == False:
            filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/{filename}"
            file_exists = utils.verify_file(filepath)
            if not file_exists or override:
                self._download_CMDS(difference_to_UTC,wind_info=wind_info_dict,filepath=filepath)
            else:
                print("\t CMDS wave data already exists, skipping download")

    def tpar_from_ERA5(self,points_lat,points_lon):
        """
        Generates TPAR files from ERA5 data for specified boundary points.

        For a non-nested domain, this method iterates over the provided latitude and longitude points,
        generating TPAR files for the north, south, east, and west boundaries using ERA5 data.

        Parameters
        ----------
        points_lat : list or array-like
            List of latitude points defining the boundary.
        points_lon : list or array-like
            List of longitude points defining the boundary.
        """
        points_lon = np.array(points_lon)
        if np.any(points_lon<0):
            points_lon += 360

        self._process_boundary_points(points_lat,points_lon,self._single_tpar_from_ERA5)

    def tpar_from_CMDS(self,points_lat,points_lon):
        """
        Generates TPAR files from CMDS data for specified boundary points.

        For a non-nested domain, this method iterates over the provided latitude and longitude points,
        generating TPAR files for the north, south, east, and west boundaries using CMDS data.

        Parameters
        ----------
        points_lat : list or array-like
            List of latitude points defining the boundary.
        points_lon : list or array-like
            List of longitude points defining the boundary.
        """
        points_lon = np.array(points_lon)
        self._process_boundary_points(points_lat,points_lon,self._single_tpar_from_CMDS)

    _VALID_SIDES = {'N', 'S', 'E', 'W'}

    def _build_side_boundary_line(self, side: str, wave_params: dict | None, 
                                  points_lon: list[float], points_lat: list[float]) -> str:
        """
        Build a single SWAN ``BOUN SIDE`` command string for one boundary side.

        Parameters
        ----------
        side : str
            Cardinal direction of the boundary side.  Must be one of
            ``'N'``, ``'S'``, ``'E'``, ``'O'``.
        wave_params : dict or None
            Wave parameters required when ``dict_info['variable_bound']``
            is ``'constant'``.  Expected keys:

            * ``'hs'``     — significant wave height (m)
            * ``'tp'``     — peak period (s)
            * ``'dir'``    — mean wave direction (deg)
            * ``'spread'`` — directional spreading

            Must be ``None`` or omitted for variable (file-driven) boundaries.

        Returns
        -------
        str
            A single SWAN boundary command, e.g.
            ``"BOUN SIDE N CLOCKW CON PAR 1.5 10.0 270 4"`` or
            ``"BOUN SIDE N CLOCKW CON VAR FILE"``.

        Raises
        ------
        ValueError
            If *side* is not in ``{'N', 'S', 'E', 'O'}``.
        ValueError
            If ``variable_bound`` is ``'constant'`` but *wave_params* is ``None``.
        """
        if side not in self._VALID_SIDES:
            raise ValueError(
                f"Invalid boundary side '{side}'. "
                f"Valid options are: {sorted(self._VALID_SIDES)}."
            )

        if self.dict_info['variable_bound']:
            if wave_params is None:
                raise ValueError(
                    "wave_params must be provided when variable_bound is 'constant'."
                )
            lines_per_side = f"BOUN SIDE {side} CLOCKW CON PAR {wave_params['hs']} {wave_params['tp']} {wave_params['dir']} {wave_params['spread']}"
        else:
            self.input_path = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'
            bnd_files = [f for f in os.listdir(self.input_path) if f.endswith('.bnd') and f'{side}' in f]
            sorted_bnd_files = sorted(bnd_files, key=lambda x: int(''.join(filter(str.isdigit, x))))

            lines_per_side = ""
            for idx, bnd_file in enumerate(sorted_bnd_files):
                if side in ['N', 'S']:
                    difference = points_lon[idx] - points_lon[0]
                else:
                    difference = points_lat[idx] - points_lat[0]
                round_difference = round(difference, 2)

                if idx == 0:
                    lines_per_side += f"BOUN SIDE {side} CLOCKW VAR FILE {round_difference} '{self.input_path}{bnd_file}' 1 & \n"
                else:
                    is_last = idx == len(sorted_bnd_files) - 1
                    newline = '' if is_last else ' \n'
                    lines_per_side += f"{round_difference} '{self.input_path}{bnd_file}' 1 &{newline}"
            
            print(lines_per_side)

        return lines_per_side

    def create_boundary_line(self, list_sides: list[str] | None = None,
                              wave_params: dict | None = None,
                              points_lon: list[float] = None, points_lat: list[float] = None) -> None:
        """
        Build and store the SWAN boundary command lines for all requested sides.

        For each entry in *list_sides*, delegates to
        :meth:`_build_side_boundary_line` to produce one ``BOUN SIDE``
        command.  All commands are joined with newlines and stored in
        :attr:`boundary_line`, ready for :meth:`fill_boundaries_section`.

        Parameters
        ----------
        list_sides : list of str, optional
            Ordered list of boundary sides to configure, e.g.
            ``['N', 'S', 'E', 'O']``.  Each entry must be a valid side
            accepted by :meth:`_build_side_boundary_line`.
        wave_params : dict or None, optional
            Wave parameters forwarded to :meth:`_build_side_boundary_line`
            when ``dict_info['variable_bound']`` is ``'constant'``.
            Ignored for variable (file-driven) boundaries.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If :attr:`dict_info` is ``None`` (boundary type not configured).
        NotImplementedError
            If ``dict_info['bound_type']`` is not ``'side'``.
        ValueError
            If any entry in *list_sides* is not a valid boundary side.
        """
        if self.dict_info is None:
            raise ValueError(
                "Boundary type information is missing. "
                "Please ensure 'dict_info' is provided at initialisation."
            )

        if not self.isnested:
            if self.dict_info['bound_type'] != 'side':
                raise NotImplementedError(
                    f"Boundary type '{self.dict_info['bound_type']}' is not supported. "
                    "Only 'side' boundaries are currently implemented."
                )
            self.list_sides = list_sides or []
            self.boundary_line = "\n".join(self._build_side_boundary_line(side, wave_params, points_lon, points_lat) for side in self.list_sides)
        else:
            self.boundary_line = f"BOUN NEST 'child0{self.init.dict_ini_data['parent_domains'][self.domain_number]}_0{self.domain_number}.NEST' CLOSED"


    def fill_boundaries_section(self):
        if self.boundary_line is not None:
            self.dict_boundaries={'boundaries_line':self.boundary_line}
            print (f'\n \t*** Adding/Editing boundary information for domain {self.domain_number} in configuration file ***\n')
            utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.dict_boundaries)
        else:
            raise ValueError("Boundary line information is missing. Please ensure 'create_boundary_line' method has been called successfully before filling the boundaries section.")