import subprocess
from pathlib import Path
from . import utils
import shutil
import os

class Initializer():
    """
    SWANInitializer is a utility class for setting up the directory structure and initial configuration files
    required to run SWAN (Simulating WAves Nearshore) model simulations. It automates the creation and cleanup
    of project folders, domain-specific subfolders, and the initialization of configuration files for each domain.

    Attributes
    ----------
    root_path : str
        The root directory path where the project structure will be created.
    dict_ini_data : dict
        Dictionary containing initialization data and configuration parameters for the SWAN model.
    ini_date : str or None
        The initial date for the model run (optional).
    end_date : str or None
        The end date for the model run (optional). 
    """
        
    def __init__(self,root_path,dict_ini_data,ini_date=None,end_date=None):
        """
        Initialize the Initializer instance with the specified root path, initialization data,
        and optional start and end dates for the model run.

        Parameters
        ----------
        root_path : str
            The root directory path where the project structure will be created.
        dict_ini_data : dict
            Dictionary containing initialization data and configuration parameters for the SWAN model.
        ini_date : str or None, optional
            The initial date for the model run (default is None).
        end_date : str or None, optional
            The end date for the model run (default is None).
        """

        self.root_path = root_path
        self.ini_date = ini_date
        self.end_date = end_date
        self.dict_ini_data = dict_ini_data
        self.folder_names = ['input','pros','run','output']
        self.dict_folders = {}
        for folder_name in self.folder_names:
            self.dict_folders[folder_name]=f'{self.root_path}{folder_name}/'
        
        print('*** Initializing SWAN model ***\n')

    def create_folders_l1(self):
        """
        Creates the primary project folder structure and cleans specific directories.
        """
        
        print ('\n \t *** Creating top-level project structure ***\n')
        for folder_name in self.folder_names:
            if not os.path.exists(self.dict_folders[folder_name]):
                subprocess.call(['mkdir','-p',f'{self.dict_folders[folder_name]}'])
            else:
                if folder_name in ['output','run']:
                    os.system(f'rm -rf {self.dict_folders[folder_name]}*')


    def create_folders_l2(self):
        """
        Creates and prepares output and run directories for each computational domain.
        Directories are named as `domain_0{domain}` and are created under the paths specified in
        `output` and `run` directories.
        """

        print ('\n \t *** Creating subfolders per each domain ***\n')

        for domain in range(1,self.dict_ini_data["number_domains"]+1):
            if not os.path.exists(f'{self.dict_folders["output"]}domain_0{domain}/'):
                subprocess.call(['mkdir','-p',f'{self.dict_folders["output"]}domain_0{domain}/'])
            else:
                os.system(f'rm -rf {self.dict_folders["output"]}domain_0{domain}/*')
                
            if not os.path.exists(f'{self.dict_folders["run"]}domain_0{domain}/'):
                subprocess.call(['mkdir','-p',f'{self.dict_folders["run"]}domain_0{domain}/'])
            else:
                os.system(f'rm -rf {self.dict_folders["run"]}domain_0{domain}/*')


    def replace_ini_data(self):
        """
        Replaces and updates the SWAN model initialization data and configuration files for each domain.
        """

        if self.dict_ini_data['stat_id']==0:
            self.stat_label='NONSTAT'
        else:
            self.stat_label='STAT'
        self.dict_ini_data['stat_label']=self.stat_label

        print ('\n \t *** Copying base swan configuration file into run folder ***\n')

        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        for domain in range(1,self.dict_ini_data["number_domains"]+1):
                shutil.copy(f'{self.data_dir}/model_config_templates/swan/run_base_{self.stat_label.lower()}.swn', f'{self.dict_folders["run"]}domain_0{domain}/run.swn')
                utils.fill_files(f'{self.dict_folders["run"]}domain_0{domain}/run.swn',self.dict_ini_data)

