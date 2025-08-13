import glob as glob
import os

from .. import utils

class BottomFrictionProcessor():
    def __init__(self,init,domain_number,friction_info=None,input_filename=None,use_link=True):
        self.init = init
        self.domain_number = domain_number
        self.friction_info = friction_info
        self.input_filename = input_filename
        self.use_link = use_link
        print(f'\n*** Initializing BottomFrictionProcessor for domain {self.domain_number} ***\n')

    def get_from_user(self):
        """
        Handles the selection and linking or copying of a friction file for the current domain.
        This method searches for a `.fric` bottom friction file in the input directory for the specified domain.

        Returns:
        --------
            dict or None: The updated `friction_info` dictionary if it exists, otherwise None.
        """
    
        friction_filepaths = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.fric')
        if not friction_filepaths:
            raise FileNotFoundError(f'Friction file not found in {self.init.dict_folders["input"]}domain_0{self.domain_number}/ or file extension is not .fric')
        friction_filepath = friction_filepaths[0]
        friction_filename = friction_filepath.split('/')[-1]

        run_domain_dir = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/'
        if self.use_link:
            if utils.verify_file(f'{run_domain_dir}{friction_filename}'):
                os.remove(f'{run_domain_dir}{friction_filename}')
            if not utils.verify_link(friction_filename, run_domain_dir):
                utils.create_link(
                    friction_filename,
                    f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/',
                    run_domain_dir
                )
        else:
            if utils.verify_link(friction_filename, run_domain_dir):
                utils.remove_link(friction_filename, run_domain_dir)
            os.system(
                f'cp {self.init.dict_folders["input"]}domain_0{self.domain_number}/{friction_filename} '
                f'{run_domain_dir}'
            )

        if self.friction_info!=None:
            self.friction_info.update({"friction.fric":friction_filename})
            return self.friction_info


    def fill_friction_section(self,dict_fric_data):
        """
        Replaces and updates the .swn file with the bottom friction configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing friction information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_fric_data)