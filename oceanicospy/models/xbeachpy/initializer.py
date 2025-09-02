import subprocess
from . import utils
from pathlib import Path
import shutil
import os
from string import Template

class Initializer():
    """
    XBeach Initializer is a utility class for setting up the directory structure and initial configuration files
    required to run XBeach model simulations. It automates the creation and cleanup
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

    def __init__ (self,root_path,dict_ini_data,ini_date=None,end_date=None):
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
            self.dict_folders[folder_name] = f'{self.root_path}{folder_name}/'

        print('*** Initializing XBeach model ***\n')

    def _generate_baseline_XBeach(self,template_in,template_out,replacement_dict):
        template_text = Path(template_in).read_text()

        # substitute available keys, leave others as-is
        filled_text = Template(template_text).safe_substitute(replacement_dict)

        Path(template_out).write_text(filled_text)


    def create_folders_l1(self):
        print ('\n*** Creating project structure ***\n')
        for folder_name in self.folder_names:
            if not os.path.exists(self.dict_folders[folder_name]):
                subprocess.call(['mkdir','-p',f'{self.dict_folders[folder_name]}'])

    def replace_ini_data(self):
        print ('\n \t *** Copying base XBeach configuration file into run folder ***\n')

        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        for key,value in self.dict_ini_data.items():
            if (type(value)==float) or (type(value)==int):
                self.dict_ini_data[key]=str(value)
            self.dict_ini_data[key]=str(value)

        merged = {**utils.defaults, **self.dict_ini_data}
        self._generate_baseline_XBeach(f'{self.data_dir}/model_config_templates/xbeach/params_base.txt', 
                                             f'{self.dict_folders["run"]}params.txt',merged)