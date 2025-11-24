#from wavespectra import read_swan
import numpy as np
import pandas as pd
import xarray as xr
import subprocess
import re
import os

from .. import utils

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
    Methods:
        fill_boundaries_section(*args): Fill the boundaries section of the simulation.
    """
    def __init__ (self,init,input_filename=None,dict_bounds_params=None):
        self.init = init
        self.input_filename=input_filename
        self.dict_bounds_params=dict_bounds_params
        print('*** Initializing Boundary Conditions ***')

    def create_filelist(self):
        """
        Create a list of files.
        Returns:
            list: A list of files.
        """
        time_s = pd.date_range(self.ini_date,self.end_date, freq='1h')

        with open(f'{self.dict_folders["run"]}filelist.txt','w') as f:
            f.write('FILELIST \n')
            for idx_time in range(len(time_s)):
                f.write(f'3600 0.2 spectra8_{idx_time+1:03d}.sp2\n')
        f.close()
        os.system(f'cp {self.dict_folders["input"]}spectra8*.sp2 {self.dict_folders["run"]}')
        dict_boundaries={'bcfilepath':'filelist.txt'}
        return dict_boundaries

    def jonswap_from_swan(self,input_filename):
        """
        Get the wave parameters from SWAN.
        Returns:
            None
        """
        # Create the filelist
        points = pd.read_csv(f'{self.dict_folders["input"]}{input_filename}.out', skiprows=7, sep='     ', 
                                names=['Time', 'Xp', 'Yp', 'Depth', 'X-Windv','Y-Windv', 'Hsig', 'TPsmoo', 'Tm01', 'Tm02', 'Dir'],
                         dtype={'Time': str, 'Xp': float, 'Yp': float, 'Depth': float, 'X-Windv': float, 'Y-Windv': float, 'Hsig': float, 'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float})

        points['Time'] = pd.to_datetime(points['Time'], format='%Y%m%d.%H%M%S')

        number_of_points = np.arange(0, 12, 1)
        dict_data_hs = {}
        dict_data_tp = {}
        dict_data_dir = {}
        for point in number_of_points:
            hs_point_serie = points['Hsig'][point::len(number_of_points)]
            dict_data_hs[f'punto {point+1}'] = hs_point_serie
            tp_point_serie = points['TPsmoo'][point::len(number_of_points)]
            dict_data_tp[f'punto {point+1}'] = tp_point_serie
            dir_point_serie = points['Dir'][point::len(number_of_points)]
            dict_data_dir[f'punto {point+1}'] = dir_point_serie
            if point==1:
                time = points['Time'][point::len(number_of_points)]

        for point in number_of_points:
            dict_data_hs[f'punto {point+1}']=np.array(dict_data_hs[f'punto {point+1}'])
            dict_data_tp[f'punto {point+1}']=np.array(dict_data_tp[f'punto {point+1}'])
            dict_data_dir[f'punto {point+1}']=np.array(dict_data_dir[f'punto {point+1}'])
            df_point = pd.DataFrame({'Hsig':dict_data_hs[f'punto {point+1}'],'TPsmoo':dict_data_tp[f'punto {point+1}'],'Dir':dict_data_dir[f'punto {point+1}']},index=time)
            df_point = df_point[(df_point.index >= self.ini_date) & (df_point.index <= self.end_date)]
            df_point['Gamma']=np.ones(len(df_point))*3.3
            df_point['Spr']=np.ones(len(df_point))*10
            df_point['Dur']=np.ones(len(df_point))*3600
            df_point['random']=np.ones(len(df_point))*1

            if point in [0,2,3,4]:
                df_point_numpy=df_point.to_numpy()
                np.savetxt(f'{self.dict_folders["run"]}jonswap_{point:03d}.txt', df_point_numpy, fmt='%6s', delimiter=' ')
        
        pos={'0':[4954777.912, 2803030.289], '2':[20,0], '3':[4954535.456, 2803057.517], '4':[20,250]}
        
        with open(f'{self.dict_folders["run"]}loclist.txt','w') as f:
                f.write('LOCLIST \n')                   
                for idx in [0,3]:
                    # Create loclist
                    str_point = f'{pos[str(idx)][0]} {pos[str(idx)][1]}' 
                    if idx == 3:
                        f.write(f'{str_point} jonswap_{idx:03d}.txt')
                    else:
                        f.write(f'{str_point} jonswap_{idx:03d}.txt\n')
                f.close()
        self.dict_boundaries={'bcfilepath':'loclist.txt'}
        return self.dict_boundaries

    def params_from_swan(self,input_filename):
        points = pd.read_csv(f'{self.dict_folders["input"]}{input_filename}.out', skiprows=7, sep='     ', 
                                names=['Time', 'Xp', 'Yp', 'Depth', 'X-Windv','Y-Windv', 'Hsig', 'TPsmoo', 'Tm01', 'Tm02', 'Dir'],
                         dtype={'Time': str, 'Xp': float, 'Yp': float, 'Depth': float, 'X-Windv': float, 'Y-Windv': float, 'Hsig': float, 'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float})

        points['Time'] = pd.to_datetime(points['Time'], format='%Y%m%d.%H%M%S')

        number_of_points = np.arange(0, 12, 1)
        dict_data_hs = {}
        dict_data_tp = {}
        dict_data_dir = {}
        for point in number_of_points:
            hs_point_serie = points['Hsig'][point::len(number_of_points)]
            dict_data_hs[f'punto {point+1}'] = hs_point_serie
            tp_point_serie = points['TPsmoo'][point::len(number_of_points)]
            dict_data_tp[f'punto {point+1}'] = tp_point_serie
            dir_point_serie = points['Dir'][point::len(number_of_points)]
            dict_data_dir[f'punto {point+1}'] = dir_point_serie
            if point==1:
                time = points['Time'][point::len(number_of_points)]

        for point in number_of_points:
            dict_data_hs[f'punto {point+1}']=np.array(dict_data_hs[f'punto {point+1}'])
            dict_data_tp[f'punto {point+1}']=np.array(dict_data_tp[f'punto {point+1}'])
            dict_data_dir[f'punto {point+1}']=np.array(dict_data_dir[f'punto {point+1}'])
            df_point = pd.DataFrame({'Hsig':dict_data_hs[f'punto {point+1}'],'TPsmoo':dict_data_tp[f'punto {point+1}'],'Dir':dict_data_dir[f'punto {point+1}']},index=time)
            df_point = df_point[(df_point.index >= self.ini_date) & (df_point.index < self.end_date)]
            df_point = df_point.round(3)
            if point == 0:
                self.dict_boundaries=dict(hsig_value=df_point['Hsig'].values[0],tp_value=df_point['TPsmoo'].values[0],dir_value=df_point['Dir'].values[0])
        return self.dict_boundaries
    
    def spectra_from_swan(self,input_filename):
        self.dataset = read_swan(f'{self.init.dict_folders["input"]}{input_filename}.out')

        # restrict dataset to requested time window
        start = np.datetime64(self.init.ini_date)
        end = np.datetime64(self.init.end_date)
        if "time" not in self.dataset.coords:
            raise RuntimeError("Loaded dataset has no 'time' coordinate to filter on.")
        self.dataset = self.dataset.sel(time=slice(start, end))

        self.data_spectra = self.dataset.efth
        self.number_spectrum_locs = len(self.dataset.site)
        if self.number_spectrum_locs == 1:
            print('delete the loclist section and the nspectrumloc command')
        else:
            self.dict_boundaries={'w_bc_version': 3,'n_spectrum_loc': self.number_spectrum_locs-3,'bcfilepath':'bounds_conds/loclist.txt'}

        for idx_site in range(self.number_spectrum_locs):

            if idx_site >= 3:
                bounds_conds_path = os.path.join(self.init.dict_folders["run"], "bounds_conds",f'point_{idx_site}')
                if not os.path.exists(bounds_conds_path):
                    os.makedirs(bounds_conds_path)

                lon = self.dataset.lon[idx_site]
                lat = self.dataset.lat[idx_site]
                with open(f"{self.init.dict_folders['run']}bounds_conds/filelist_{idx_site}.txt", "w") as filelist:
                    filelist.write('FILELIST'+'\n')
                    for idx_time,time in enumerate(self.dataset.time):
                        self.spec_to_save = np.matrix(self.data_spectra[idx_time,idx_site,:,:])/0.1e-5
                        time_specific = pd.to_datetime(self.dataset.time.values[idx_time])
                        time_to_write = time_specific.strftime('%Y%m%d.%H%M%S')
                        with open(f"{self.init.dict_folders['input']}SpecSWAN.out") as forigin:
                                with open(f"{self.init.dict_folders['run']}bounds_conds/point_{idx_site}/spec_time{idx_time}_point{idx_site}.sp2", "w") as fdest:
                                    while True:
                                        line = forigin.readline()
                                        if 'date and time' not in line:
                                            if 'number of locations' in line:
                                                line = re.sub(r'\d+',"1", line)
                                                for _ in range(self.number_spectrum_locs):
                                                    next_line = forigin.readline()
                                                    if ((f"{lon}" in next_line) and (f"{lat:.5f}" in next_line)):
                                                        line = line + next_line
                                            if 'number of directions' in line:
                                                for _ in range(36):
                                                    next_line = forigin.readline()
                                                    new_line = str(float(next_line) + 270) + '\n'
                                                    line = line + new_line
                                            fdest.write(line)
                                        else:
                                            break

                                    fdest.write(time_to_write + '\n')
                                    fdest.write('FACTOR' + '\n')
                                    fdest.write('0.1E-05' + '\n')
                                    for line in self.spec_to_save:
                                        np.savetxt(fdest, line, fmt='%5.0f')
                                fdest.close()
                        filelist.write(f"3600 0.2 'bounds_conds/point_{idx_site}/spec_time{idx_time}_point{idx_site}.sp2' \n")
                filelist.close()

        with open(f"{self.init.dict_folders['run']}bounds_conds/loclist.txt", "w") as floc:
            floc.write('LOCLIST'+'\n')
            for idx_site in range(self.number_spectrum_locs):
                if idx_site >= 3:
                    floc.write(f"0 {-idx_site*100} 'bounds_conds/filelist_{idx_site}.txt' \n")
        floc.close()

        return self.dict_boundaries

    def fill_boundaries_section(self,dict_boundaries):
        """
        Fill the boundaries section of the simulation.
        Args:
            *args: Variable length argument list.
        Returns:
            None
        """
        for param in dict_boundaries:
            dict_boundaries[param]=str(dict_boundaries[param])
        
        print (f'\n*** Adding/Editing boundary information for domain in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',dict_boundaries)