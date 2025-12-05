import pandas as pd
import numpy as np
import glob as glob
from datetime import datetime
from scipy.signal import detrend

from .. import utils
from ....retrievals import *

class WaterLevelForcing():
    def __init__ (self,init,domain_number,wl_info=None,input_filename=None,share_wl=True,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.wl_info = wl_info
        self.input_filename = input_filename
        self.share_wl = share_wl
        self.use_link = use_link
        print(f'\n*** Initializing water levels for domain {self.domain_number} ***\n')

    def _download_UHSLC(self,station_code,filepath):
        UHSLCDownloader_obj = UHSLCDownloader(
                            station_code=station_code,
                            output_path=filepath,
                            )
        UHSLCDownloader_obj.download()
        print('\t UHSLC water level data was successfully downloaded')
    
    def _UHSLC_csv_to_ascii(self,UHSLC_filename,ascii_filename,detrend_wl=False):
        self.dataset = pd.read_csv(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{UHSLC_filename}',header=None,
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

        # Replace values in 'water_level' more negative than -2 with linear interpolation between neighbors
        # wl = self.dataset_filtered['water_level'].values
        # mask = wl < -2
        # for idx in np.where(mask)[0]:
        #     if 0 < idx < len(wl) - 1:
        #         wl[idx] = (wl[idx - 1] + wl[idx + 1]) / 2
        # self.dataset_filtered['water_level'] = wl

        bathymetry_grid = np.genfromtxt(glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.bot')[0])

        file = open(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{ascii_filename}','w')

        for date in self.dataset_filtered.index:
            file.write("%s\n" % date.strftime("%Y%m%d %H%M%S"))
            water_level=np.full(np.shape(bathymetry_grid),-9999).astype(float)
            water_level[bathymetry_grid>=0]=float(self.dataset_filtered['depth[m]'][date])
            np.savetxt(file,water_level,fmt='%10.4f')
        file.close()

    def get_waterlevel_from_UHSLC(self,station_code):
        filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/h{station_code}.csv"
        file_exists = utils.verify_file(filepath)

        if not self.share_wl:
            if not file_exists:
                self._download_UHSLC(station_code, filepath=filepath)
            else:
                print("\t UHSLC water level data already exists, skipping download")
        else:
            if self.domain_number == 1:
                if not file_exists:
                    self._download_UHSLC(station_code, filepath=filepath)
                else:
                    print("\t UHSLC water level data already exists, skipping download")
            else:
                    print("\t UHSLC water level data already exists in domain 1, skipping download") 

    def write_UHSLC_ascii(self,UHSLC_filename,ascii_filename):
        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

        if not self.share_wl:
            self._UHSLC_csv_to_ascii(UHSLC_filename, ascii_filename)
            print('\t UHSLC water level data converted to ASCII format and saved as', ascii_filename)
        else:
            if self.domain_number == 1:
                self._UHSLC_csv_to_ascii(UHSLC_filename, ascii_filename)
                print('\t UHSLC water level data converted to ASCII format and saved as', ascii_filename)
            else:
                origin_domain_dir = f'{self.init.dict_folders["input"]}domain_01/'
                print(f"\t UHSLC water level data converted to ASCII format and saved as {ascii_filename} in domain 01, linking to domain {self.domain_number}")

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

        if self.wl_info!=None:
            if not self.share_wl:
                self.wl_info.update({"wl_file":f"../../input/domain_0{self.domain_number}/{ascii_filename}"})
            else:
                self.wl_info.update({"wl_file":f"../../input/domain_01/{ascii_filename}"})
            return self.wl_info
        return None

    def fill_wl_section(self,dict_wl_data):
        """
        Replaces and updates the .swn file with the water level configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing water level information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_wl_data)

    # def waterlevel_from_user(self):
    #     wl_file_path = glob.glob(f'{self.dict_folders["input"]}domain_0{self.domain_number}/*.wl')[0]
    #     wl_filename=wl_file_path.split('/')[-1]

    #     os.system(f'cp {self.dict_folders["input"]}domain_0{self.domain_number}/{wl_filename}\
    #                              {self.dict_folders["run"]}domain_0{self.domain_number}/')

    #     if self.wl_info!=None:
    #         self.wl_info.update({"water_levels.wl":wl_filename})
    #         return self.wl_info