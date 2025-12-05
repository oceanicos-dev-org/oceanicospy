from .. import utils

class PhysicsMaker():
    def __init__(self,init,domain_number):
        self.init = init
        self.domain_number = domain_number
    
    def define_generation(self,cds1='',delta=''):
        self.gen_line = {'cds1':cds1,
                         'delta':delta}
        return self.gen_line
    
    def fill_physics_section(self,dict_physics_data):
        """
        Replaces and updates the .swn file with the physics configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing physics information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files_2(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_physics_data)


