from .. import utils

class NumericsMaker():
    def __init__(self,init,domain_number):
        self.init = init
        self.domain_number = domain_number

    def define_stopping_criteria(self,stop_criteria=utils.defaults['stop_criteria'],iters=''):
        self.num_line_dict = {'stop_criteria':stop_criteria,'iters':iters}
        return self.num_line_dict

    def fill_numerics_section(self,dict_numerics_data):
        """
        Replaces and updates the .swn file with the numerics configuration for a specific domain.
        """
        print (f'\n \t*** Adding/Editing numerics information for domain {self.domain_number} in configuration file ***\n')

        # Search for the line that starts with 'NUM' in the run.swn file
        swn_file_path = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn'
        with open(swn_file_path, 'r') as file:
            lines = file.readlines()
        num_line = next((line for line in lines if line.strip().startswith('NUM')), None)

        if dict_numerics_data['stop_criteria'] == 'ACCUR':
            new_line = f'NUM {dict_numerics_data['stop_criteria']}'
            if num_line:
                idx = lines.index(num_line)
                lines[idx] = new_line + '\n'
                with open(swn_file_path, 'w') as file:
                    file.writelines(lines)
        else:
            utils.fill_files_2(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn',dict_numerics_data)


