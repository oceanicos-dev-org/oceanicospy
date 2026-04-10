import pandas as pd
import numpy as np
import glob as glob
from datetime import datetime
from scipy.signal import detrend

<<<<<<< HEAD
from pathlib import Path

from .... import utils
from ....retrievals import *

class WaterLevelForcing():
    def __init__ (self,init,domain_number,dict_info=None,filename=None,share_wl=True,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.dict_info = dict_info
        self.filename = filename
=======
from .. import utils
from ....retrievals import *

class WaterLevelForcing():
    def __init__ (self,init,domain_number,wl_info=None,input_filename=None,share_wl=True,use_link=None):
        self.init = init
        self.domain_number = domain_number
        self.wl_info = wl_info
        self.input_filename = input_filename
>>>>>>> 5d48c5cb29036c1269753c1321a4ce9d6bc43c90
        self.share_wl = share_wl
        self.use_link = use_link
        print(f'\n*** Initializing water levels for domain {self.domain_number} ***\n')

<<<<<<< HEAD
    def _download_UHSLC(self,station_id,filepath):
        filepath = Path(filepath)

        UHSLCDownloader_obj = UHSLCDownloader(
                            station_id=station_id,
                            output_path=filepath.parent,
                            output_filename=filepath.name,
                            start_datetime_local=self.init.ini_date.strftime('%Y-%m-%d %H:%M:%S'),
                            end_datetime_local=self.init.end_date.strftime('%Y-%m-%d %H:%M:%S'),
                            difference_from_UTC=-5
                            )
        UHSLCDownloader_obj.download()
        df_clean = UHSLCDownloader_obj.clean_data(filepath)

        
        print('\t UHSLC water level data was successfully downloaded')
        return df_clean
    
    def _load_bathymetry(self) -> np.ndarray:
        """
        Load the bathymetry grid for the current domain from the ``*.bot`` file.

        Returns
        -------
        numpy.ndarray
            2-D array of water depths.  Positive values indicate wet cells;
            zero or negative values indicate dry/land cells.

        Raises
        ------
        IndexError
            If no ``*.bot`` file is found in the domain input directory.
        """
        bot_files = glob.glob(
            f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.bot'
        )
        return np.genfromtxt(bot_files[0])

    def _build_wl_grid(self, bathymetry_grid: np.ndarray, wl_value: float) -> np.ndarray:
        """
        Create a 2-D water-level grid that matches the bathymetry layout.

        Wet cells (``bathymetry_grid >= 0``) are assigned *wl_value*; all
        other cells receive the SWAN no-data fill value ``-9999``.

        Parameters
        ----------
        bathymetry_grid : numpy.ndarray
            2-D depth array returned by :meth:`_load_bathymetry`.
        wl_value : float
            Water-surface elevation in metres to assign to wet cells.

        Returns
        -------
        numpy.ndarray
            2-D float array of the same shape as *bathymetry_grid*.
        """
        water_level = np.full(bathymetry_grid.shape, -9999.0)
        water_level[bathymetry_grid >= 0] = wl_value
        return water_level

    def _match_wl_to_bathy(self) -> np.ndarray:
        """
        Build a static water-level grid using the first value in the
        filtered water-level dataset.

        The method reads the domain bathymetry and stamps the first
        ``depth[m]`` value from :attr:`dataset_filtered` onto all wet
        cells, leaving dry/land cells at ``-9999``.

        Returns
        -------
        numpy.ndarray
            2-D float array with the static water-level field, shaped
            like the domain bathymetry grid.

        Raises
        ------
        AttributeError
            If :attr:`dataset_filtered` has not been populated yet
            (call :meth:`_UHSLC_csv_to_ascii` first).
        """
        bathymetry_grid = self._load_bathymetry()
        wl_value = float(self.dataset_filtered["depth[m]"].iloc[0])
        return self._build_wl_grid(bathymetry_grid, wl_value)

    def _UHSLC_csv_to_ascii(
        self,
        UHSLC_dataframe: pd.DataFrame,
        ascii_filename: str,
        detrend_wl: bool = False,
    ) -> None:
        """
        Parse a raw UHSLC hourly CSV file, clean the water-level series,
        and write a time-varying water-level file in SWAN ASCII format.

        Processing steps applied to the raw data:

        1. Delegate CSV parsing, UTC→local (UTC−5) conversion, and mm→m
           conversion to :meth:`~oceanicospy.retrievals.UHSLCDownloader.clean_data`.
        2. Flag UHSLC fill values (``depth[m] < -30.0``) as ``NaN``.
        3. Apply a station datum correction of ``-2.0 m`` for the local-time
           period 1997-01-01 00:00 – 2018-12-31 18:00 (≡ 1997-01-01 05:00 –
           2018-12-31 23:00 UTC).
        4. Optionally detrend the water-level signal.
        5. Trim the series to ``[ini_date, end_date]``.
        6. Write one timestamp header + a full spatial grid per time step.

        The cleaned full series is stored in :attr:`dataset` and the
        simulation-window subset in :attr:`dataset_filtered`.

        Parameters
        ----------
        UHSLC_dataframe : pd.DataFrame
            The cleaned UHSLC data as a pandas DataFrame.
        ascii_filename : str
            Name of the SWAN water-level ASCII output file to create in
            the same input directory (e.g. ``"water_levels.wl"``).
        detrend_wl : bool, optional
            If ``True``, apply :func:`scipy.signal.detrend` to the
            ``depth[m]`` column after conversion.  ``NaN`` gaps are
            excluded from the detrending and reinserted afterwards.
            Default is ``False``.

        Returns
        -------
        None

        Raises
        ------
        FileNotFoundError
            If *UHSLC_filename* or the domain ``*.bot`` file cannot be
            found.
        """
        domain_dir = Path(self.init.dict_folders["input"]) / f"domain_0{self.domain_number}"


        UHSLC_dataframe.loc[UHSLC_dataframe["depth[m]"] < -30.0, "depth[m]"] = np.nan

        # --- Optional linear detrending (NaN-safe) ---
        if detrend_wl:
            valid_mask = np.isfinite(UHSLC_dataframe["depth[m]"])
            detrended = np.full(len(UHSLC_dataframe), np.nan)
            detrended[valid_mask.values] = detrend(
                UHSLC_dataframe.loc[valid_mask, "depth[m]"].values
            )
            UHSLC_dataframe["depth[m]"] = detrended

        self.dataset = UHSLC_dataframe
        self.dataset_filtered = UHSLC_dataframe.loc[
            (UHSLC_dataframe.index >= self.init.ini_date) & (UHSLC_dataframe.index <= self.init.end_date)
        ]

        bathymetry_grid = self._load_bathymetry()
        out_path = domain_dir / ascii_filename
        with open(out_path, "w") as fh:
            for date, row in self.dataset_filtered.iterrows():
                fh.write(f"{date.strftime('%Y%m%d %H%M%S')}\n")
                water_level = self._build_wl_grid(
                    bathymetry_grid, float(row["depth[m]"])
                )
                np.savetxt(fh, water_level, fmt="%10.4f")

    def get_waterlevel_from_UHSLC(self,station_id):
        filepath = f"{self.init.dict_folders['input']}domain_0{self.domain_number}/h{station_id}.csv"
        file_exists = utils.verify_file(filepath)

        if not self.share_wl:
            if not file_exists:
                df_waterlevel = self._download_UHSLC(station_id, filepath=filepath)
            else:
                reader = UHSLCDownloader(station_id=station_id,
                                        output_path=None,
                                        output_filename=None)
                df_waterlevel = reader.clean_data(filepath)
                print("\t UHSLC water level data already exists, skipping download")
        else:
            if self.domain_number == 1:
                if not file_exists:
                    df_waterlevel = self._download_UHSLC(station_id, filepath=filepath)
                else:
                    reader = UHSLCDownloader(station_id=station_id,
                                            output_path=None,
                                            output_filename=None)
                    df_waterlevel = reader.clean_data(filepath)
                    print("\t UHSLC water level data already exists, skipping download")
            else:
                    filepath_domain1 = f"{self.init.dict_folders['input']}domain_01/h{station_id}.csv"
                    reader = UHSLCDownloader(station_id=station_id,
                                            output_path=None,
                                            output_filename=None)
                    df_waterlevel = reader.clean_data(filepath_domain1)
                    print("\t UHSLC water level data already exists in domain 1, skipping download")
        return df_waterlevel

    def write_UHSLC_ascii(self,UHSLC_dataframe,ascii_filename):
        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        origin_domain_dir = f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/'

        # verification of file existence and conversion to ascii format if needed 
        if not self.share_wl:
            self._UHSLC_csv_to_ascii(UHSLC_dataframe, ascii_filename)
            print('\t UHSLC water level data converted to ASCII format and saved as', ascii_filename)
        else:
            if self.domain_number == 1:
                self._UHSLC_csv_to_ascii(UHSLC_dataframe, ascii_filename)
                print('\t UHSLC water level data converted to ASCII format and saved as', ascii_filename)
            else:
                origin_domain_dir = f'{self.init.dict_folders["input"]}domain_01/'
                print(f"\t UHSLC water level data converted to ASCII format and saved as {ascii_filename} in domain 01, linking to domain {self.domain_number}")
        
        # validation of file creation and deployment to run directory
        utils.deploy_input_file(ascii_filename, origin_domain_dir, run_domain_dir, self.use_link)

        if self.dict_info!=None:
            if not self.share_wl:
                self.dict_info.update({"wl_file":f"../../input/domain_0{self.domain_number}/{ascii_filename}"})
            else:
                self.dict_info.update({"wl_file":f"../../input/domain_01/{ascii_filename}"})
            return self.dict_info
        return None

    def fill_wl_section(self):
        """
        Replaces and updates the .swn file with the water level configuration for a specific domain.
        """

        if self.dict_info == None:
            raise ValueError(f'Water level information is not provided for domain {self.domain_number}.')

        print (f'\n \t*** Adding/Editing water level information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.dict_info)
=======
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
>>>>>>> 5d48c5cb29036c1269753c1321a4ce9d6bc43c90
