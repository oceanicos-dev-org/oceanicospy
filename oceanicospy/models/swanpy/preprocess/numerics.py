from .. import utils

class NumericsMaker():
    """
    NumericsMaker is a utility class for generating and managing the numerics information for SWAN.

    Parameters
    ----------
    init : object
        An initialization object containing configuration data and folder paths.
    domain_number : int
        Identifier for the domain being processed.
    dict_info : dict or None, optional
        User-provided numerics information dictionary.
        If the dict_info dictionary is passed it should contain the following keys:
        ``stop_criteria``: stopping criteria for the simulation
        ``iters``: number of iterations
    """

    def __init__(self, init, domain_number, dict_info=None):
        self.init = init
        self.domain_number = domain_number
        self.dict_info = dict_info
        print(f'\n*** Initializing NumericsMaker for domain {self.domain_number} ***\n')

    def define_stopping_criteria(self, stop_criteria=utils.defaults['stop_criteria'], iters=''):
        self.dict_info = {'stop_criteria': stop_criteria, 'iters': iters}
        return self.dict_info

    def fill_numerics_section(self):
        """
        Replaces and updates the .swn file with the numerics configuration for a specific domain.

        Raises
        ------
        ValueError
            If no numerics information was provided at initialization or via define_stopping_criteria().
        """

        if self.dict_info is None:
            raise ValueError(f'Numerics information is not provided for domain {self.domain_number}. '
                             'Please provide dict_info or call define_stopping_criteria() first.')

        print(f'\n \t*** Adding/Editing numerics information for domain {self.domain_number} in configuration file ***\n')

        # Search for the line that starts with 'NUM' in the run.swn file
        swn_file_path = f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn'
        with open(swn_file_path, 'r') as file:
            lines = file.readlines()
        num_line = next((line for line in lines if line.strip().startswith('NUM')), None)

        if self.dict_info['stop_criteria'] == 'ACCUR':
            new_line = f"NUM {self.dict_info['stop_criteria']}"
            if num_line:
                idx = lines.index(num_line)
                lines[idx] = new_line + '\n'
                with open(swn_file_path, 'w') as file:
                    file.writelines(lines)
        else:
            utils.fill_files_2(swn_file_path, self.dict_info)
