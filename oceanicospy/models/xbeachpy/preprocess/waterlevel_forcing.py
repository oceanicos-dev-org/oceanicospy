import pandas as pd
import numpy as np
import glob as glob
from datetime import datetime
from scipy.signal import detrend
import os

from .. import utils
from ....retrievals import *

class WaterLevelForcing():
    def __init__ (self,init,wl_info=None,input_filename=None,use_link=None):
        self.init = init
        self.wl_info = wl_info
        self.input_filename = input_filename
        self.use_link = use_link
        print(f'\n*** Initializing water levels ***\n')

    def _download_UHSLC(self,station_code,filepath):
        UHSLCDownloader_obj = UHSLCDownloader(
                            station_code=station_code,
                            output_path=filepath,
                            )
        UHSLCDownloader_obj.download()
        print('\t UHSLC water level data was successfully downloaded')
    
    def _UHSLC_csv_to_ascii(self,UHSLC_filename,ascii_filename,detrend_wl=False):
        self.dataset = pd.read_csv(f'{self.init.dict_folders["input"]}{UHSLC_filename}',header=None,
                                            names=["year","month","day","hour","depth[mm]"],sep=',')
                                    
        self.dataset.index = pd.to_datetime(self.dataset[['year', 'month', 'day', 'hour']])
        self.dataset = self.dataset.drop(columns=['year', 'month', 'day', 'hour'])
        self.dataset[self.dataset['depth[mm]']<-30000]=np.nan
        self.dataset[(self.dataset.index>=datetime(1997,1,1,5)) & (self.dataset.index<=datetime(2018,12,31,23))]-=2000
        self.dataset.index = self.dataset.index- pd.DateOffset(hours=5)  # Adjusting for UTC-5
        self.dataset['depth[m]'] = self.dataset['depth[mm]'] / 1000.0
        if detrend_wl:
            valid_mask = np.isfinite(self.dataset['depth[m]'])
            self.dataset['depth[m]_detrended'] = np.nan
            # Apply detrend only on the valid part
            self.dataset.loc[valid_mask, 'depth[m]_detrended'] = detrend(self.dataset.loc[valid_mask, 'depth[m]'])

        self.dataset_filtered = self.dataset[(self.dataset.index >= self.init.ini_date) & (self.dataset.index <= self.init.end_date)]
        
        time_to_write = (self.dataset_filtered.index - self.dataset_filtered.index[0]).total_seconds().astype(int).tolist()

        df_to_save=pd.DataFrame({'Time':time_to_write,'water level[m]':self.dataset_filtered['depth[m]']},
                                index=self.dataset_filtered.index)

        df_to_save.to_csv(f'{self.init.dict_folders["input"]}{ascii_filename}',sep=' ',header=False,index=False)

        # Replace values in 'water_level' more negative than -2 with linear interpolation between neighbors
        # wl = self.dataset_filtered['water_level'].values
        # mask = wl < -2
        # for idx in np.where(mask)[0]:
        #     if 0 < idx < len(wl) - 1:
        #         wl[idx] = (wl[idx - 1] + wl[idx + 1]) / 2
        # self.dataset_filtered['water_level'] = wl

    def get_waterlevel_from_UHSLC(self,station_code):
        filepath = f"{self.init.dict_folders['input']}h{station_code}.csv"
        file_exists = utils.verify_file(filepath)

        if not file_exists:
            self._download_UHSLC(station_code, filepath=filepath)
        else:
            print("\t UHSLC water level data already exists, skipping download")

    def write_UHSLC_ascii(self,UHSLC_filename,ascii_filename):
        run_domain_dir = f'{self.init.dict_folders["run"]}'
        origin_domain_dir = f'{self.init.dict_folders["input"]}'

        self._UHSLC_csv_to_ascii(UHSLC_filename, ascii_filename)
        print('\t UHSLC water level data converted to ASCII format and saved as', ascii_filename)

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

        if self.wl_info!=None:
            self.wl_info.update({"sealevelfilepath":f"{ascii_filename}"})
        else:
            self.wl_info = {"sealevelfilepath":f"{ascii_filename}"}
        return self.wl_info


    def convert_data_from_CECOLDO(self, input_filename, output_filename):
        """
        Convert data from CECOLDO to XBeach format.
        Args:
            path_cecoldo (str): The path to the CECOLDO data.
            path_output (str): The path to the output data.
        Returns:
            None
        """
        data_cecoldo=pd.read_csv(f'{self.dict_folders["input"]}{input_filename}',sep='\t',skiprows=[1],
                                 na_values=['-99999.00'])
        data_cecoldo['Fecha'] = pd.to_datetime(data_cecoldo['Fecha [aaaa-mm-dd UT-5]'] + ' ' + data_cecoldo['Hora [hh:mm:ss UT-5]'])
        data_cecoldo.set_index('Fecha',inplace=True)
        data_cecoldo.drop(columns=['Fecha [aaaa-mm-dd UT-5]','Hora [hh:mm:ss UT-5]',
                                'Latitud [deg]','Longitud [deg]','Estacion [#]','QF [IODE]'],inplace=True)
        
        data_cecoldo=data_cecoldo[(data_cecoldo.index >= self.ini_date) & (data_cecoldo.index <= self.end_date)]

        # data_cecoldo = data_cecoldo.resample('1H').ffill()
        data_cecoldo['Nivel_mar [m]'] = data_cecoldo['Nivel_mar [m]']-np.nanmean(data_cecoldo['Nivel_mar [m]'])

        time_to_write = (data_cecoldo.index - data_cecoldo.index[0]).total_seconds().astype(int).tolist()
        df_to_save=pd.DataFrame({'time [s]':time_to_write,'sealevel':data_cecoldo['Nivel_mar [m]']},index=None)
        df_to_save=df_to_save.round(3)
        df_to_save.to_csv(f'{self.dict_folders["run"]}{output_filename}',sep='\t',header=None,index=None)
        self.dict_sealevel={'sealevelfilepath':'sealevel.txt'}
        return self.dict_sealevel

    def constant_from_CECOLDO(self,input_filename):
        data_cecoldo=pd.read_csv(f'{self.dict_folders["input"]}{input_filename}',sep='\t',skiprows=[1],
                                 na_values=['-99999.00'])
        data_cecoldo['Fecha'] = pd.to_datetime(data_cecoldo['Fecha [aaaa-mm-dd UT-5]'] + ' ' + data_cecoldo['Hora [hh:mm:ss UT-5]'])
        data_cecoldo.set_index('Fecha',inplace=True)
        data_cecoldo.drop(columns=['Fecha [aaaa-mm-dd UT-5]','Hora [hh:mm:ss UT-5]',
                                'Latitud [deg]','Longitud [deg]','Estacion [#]','QF [IODE]'],inplace=True)
        
        # data_cecoldo = data_cecoldo.resample('1H').ffill()
        data_cecoldo['Nivel_mar [m]'] = data_cecoldo['Nivel_mar [m]']-np.nanmean(data_cecoldo['Nivel_mar [m]'])
        data_cecoldo=data_cecoldo[(data_cecoldo.index >= self.ini_date) & (data_cecoldo.index <= self.end_date)]

        self.dict_sealevel={'sealevelvalue':round(data_cecoldo['Nivel_mar [m]'].values[0],3)}
        return self.dict_sealevel

    def txt_from_user(self):
        """
        Reads sea level parameters from a user-defined file and returns them as a dictionary.
        """
        sealevel_file_path = glob.glob(f'{self.dict_folders["input"]}*.wl')[0]
        sealevel_filename=sealevel_file_path.split('/')[-1]

        if not utils.verify_link(sealevel_filename,f'{self.dict_folders["run"]}/'):
            utils.create_link(sealevel_filename,f'{self.dict_folders["input"]}/',
                                f'{self.dict_folders["run"]}/')

        self.sealevel_info = {"sealevelfilepath":sealevel_filename}
        return self.sealevel_info

    def fill_wl_section(self,dict_sealevel_data):
        """
        Fill the sealevel section of the simulation.
        Returns:
            None
        """
        print (f'\n*** Adding/Editing water level information for domain in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',dict_sealevel_data)  