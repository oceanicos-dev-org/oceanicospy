import shutil
import subprocess
import pandas as pd
import datetime as dt
import numpy as np
import glob as glob
import scipy.interpolate
from pathlib import Path

from .. import utils

class CaseRunner():
    def __init__(self,init,dict_comp_data):
        self.init = init
        self.dict_comp_data = dict_comp_data
        print(f'\n*** Initializing Case Runner ***\n')  

    def write_output_file(self,filename=None):
        self.dict_comp_data['outputfilepath']=f'{filename}'
    
    def write_output_points(self,filename=None):
        try:
            points_file = glob.glob(f'{self.init.dict_folders["input"]}{filename}')[0] # the file has to be named with the word points
        except IndexError:
            points_file = None
            
        if points_file:
            date_points = np.loadtxt(points_file)
            self.dict_comp_data['len_points']=len(date_points)
            string_points=[f'{point[0]} {point[1]}\n' for point in date_points]
            string_points[-1]=string_points[-1].strip()  # remove last new line
            self.dict_comp_data['string_points']=''.join(string_points)
        else:
            self.dict_comp_data['len_points'] = 0
            self.dict_comp_data['string_points'] = '' 

    def select_global_vars(self,list_vars=[]):
        if list_vars:
            string_list_vars = '\n'.join(str(var) for var in list_vars)
            self.dict_comp_data['len_global_vars'] = len(list_vars)
            self.dict_comp_data['global_vars'] = string_list_vars
        else:
            string_list_vars = ''

    def select_point_vars(self,list_vars=[]):
        if list_vars:
            string_list_vars = '\n'.join(str(var) for var in list_vars)
            self.dict_comp_data['len_point_vars'] = len(list_vars)
            self.dict_comp_data['point_vars'] = string_list_vars
        else:
            self.dict_comp_data['len_point_vars'] = 0
            self.dict_comp_data['point_vars'] = ''

    def fill_slurm_file(self,case_name):
        """
        Fills the SLURM script with the necessary parameters for running the XBeach model.
        This includes paths, simulation name, number of domains, and parent domains.
        """
        self.script_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        shutil.copy(f'{self.data_dir}/model_config_templates/xbeach/launcher_xbeach_base.slurm',
                    f'{self.init.dict_folders["run"]}launcher_xbeach.slurm')
        
        launch_dict = dict(output_path_case=f'{self.init.dict_folders["output"]}',case_name=case_name)

        utils.fill_files(f'{self.init.dict_folders["run"]}launcher_xbeach.slurm', launch_dict,strict=False)


    def fill_computation_section(self): 
        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent.parent.parent.parent / 'data'

        ini_comp_date = dt.datetime.strptime(self.dict_comp_data['ini_comp_date'], '%Y%m%d.%H%M%S')
        end_comp_date = dt.datetime.strptime(self.dict_comp_data['end_comp_date'], '%Y%m%d.%H%M%S')

        seconds = (end_comp_date - ini_comp_date).total_seconds()
        self.dict_comp_data['tstop_value'] = int(seconds)
        for param in self.dict_comp_data:
            self.dict_comp_data[param]=str(self.dict_comp_data[param])

        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',self.dict_comp_data)