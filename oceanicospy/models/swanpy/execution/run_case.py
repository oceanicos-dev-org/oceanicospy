import shutil
import subprocess
import pandas as pd
from pathlib import Path
import os

from .. import utils
from ..preprocess import GridMaker

class CaseRunner():
    def __init__(self,init,domain_number,dict_comp_data,all_domains):
        self.init = init
        self.dict_comp_data = dict_comp_data
        self.domain_number = domain_number
        self.all_domains = all_domains
        print(f'\n*** Initializing Case Runner for domain {self.domain_number} ***\n')  

    def define_output_from_file(self,filename=None):
        """
        Reads a CSV file containing point coordinates, adjusts negative longitude values,
        and writes the processed coordinates to a .loc file for SWAN model output.
        
        Parameters
        ----------
        filename : str, optional
            Name of the CSV file to read, located in the input folder for the current domain.
            The file must contain at least 'X' and 'Y' columns representing coordinates.
            If not provided, defaults to 'points.csv'.
        """

        ds = pd.read_csv(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/{filename}',delimiter=',')
        ds = ds[['X','Y']]
        if (ds['X'] < 0).any():
            ds.loc[ds['X'] < 0, 'X'] += 360
        ds.to_csv(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/points.loc',index=False, header=False, na_rep=0, float_format='%7.7f',sep=' ')
    
    def write_nest_section(self):
        dict_parent_doms = self.init.dict_ini_data["parent_domains"]
        nested_doms = [child for child,parent in dict_parent_doms.items() if parent==self.domain_number]
        if len(nested_doms)==0:
            utils.delete_line(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn','NESTOUT')
            utils.delete_line(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn','NGRID')
        else:
            nested_doms_info = []
            for nest_dom in nested_doms:
                nested_doms_info.append(self.all_domains[nest_dom]["grid"])

            if len(nested_doms)>1:
                utils.duplicate_lines(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn', 55)
            for nested_dom_id,nested_dom_info in zip(nested_doms,nested_doms_info):
                nested_dom_info_=dict()
                for key in nested_dom_info.copy().keys():
                    nested_dom_info_[f'child_{key}']= nested_dom_info[key]
                nested_dom_info_.update(nest_id=f'n0{self.domain_number}_0{nested_dom_id}',nest_grid_file=f'child0{self.domain_number}_0{nested_dom_id}.NEST')
                utils.fill_files_only_once(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',nested_dom_info_)

    def fill_slurm_file(self):
        """
        Fills the SLURM script with the necessary parameters for running the SWAN model.
        This includes paths, simulation name, number of domains, and parent domains.
        """
        self.script_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        shutil.copy(f'{self.data_dir}/model_config_templates/swan/launcher_base_nest_cecc.slurm',
                    f'{self.init.dict_folders["run"]}launcher_swan.slurm')
        
        bash_code = "declare -a bash_dict\n"
        for key, value in self.init.dict_ini_data["parent_domains"].items():
            bash_value = "" if value is None else value
            bash_code += f'bash_dict[{key}]={bash_value}\n'

        launch_dict = {
            'path_case': self.init.root_path,
            'simulation_name': self.init.dict_ini_data["name"].replace(" ", "_"),
            'number_domains': self.init.dict_ini_data["number_domains"],
            'parent_domains': bash_code
        }
        utils.fill_files(f'{self.init.dict_folders["run"]}launcher_swan.slurm', launch_dict, strict=False)

    def fill_computation_section(self):
        if self.dict_comp_data['stat_comp'] in (0,"0"): # If the computation is non-stationary
            self.stat_label = 'NONSTAT'
            self.string_comp = f'COMP {self.stat_label} {self.dict_comp_data["ini_comp_date"]} {self.dict_comp_data["dt_min"]} MIN {self.dict_comp_data["end_comp_date"]}'
        else:
            self.stat_label = 'STAT'
            self.string_comp = ''
            for idx,date in enumerate(self.dict_comp_data['comp_dates']):
                self.date=date.strftime('%Y%m%d.%H%M%S')
                if idx == len(self.dict_comp_data['comp_dates']) - 1:
                    self.string_comp += f'COMP {self.stat_label} {self.date}'
                else:
                    if self.dict_comp_data['init_intermediate']:
                        self.string_comp += f'COMP {self.stat_label} {self.date}\nINIT\n'
                    else:
                        self.string_comp += f'COMP {self.stat_label} {self.date}\n'

        self.dict_comp_data['string_comp'] = self.string_comp
        self.dict_comp_data['stat_label_comp'] = self.stat_label
        for param in self.dict_comp_data:
            self.dict_comp_data[param] = str(self.dict_comp_data[param])

        # print(self.dict_comp_data) # More keys than needed
        print (f'\n \t*** Adding/Editing compilation information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',self.dict_comp_data)

        # subprocess.run([f'rm -rf {self.dict_folders["run"]}run.erf-*'],shell=True)
