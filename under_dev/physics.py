from .. import utils

class PhysicsMaker():
    """
    PhysicsMaker is a utility class for generating and managing the physics information for SWAN.

    Parameters
    ----------
    init : object
        An initialization object containing configuration data and folder paths.
    domain_number : int
        Identifier for the domain being processed.
    dict_info : dict or None, optional
        User-provided physics information dictionary.
        If the dict_info dictionary is passed it should contain the following keys:
        ``cds1``: drag coefficient
        ``delta``: delta parameter for wave breaking
    """

    def __init__(self, init, domain_number, dict_info=None):
        self.init = init
        self.domain_number = domain_number
        self.dict_info = dict_info
        print(f'\n*** Initializing PhysicsMaker for domain {self.domain_number} ***\n')

    def define_generation(self, cds1='', delta=''):
        self.dict_info = {'cds1': cds1, 'delta': delta}
        return self.dict_info

    def fill_physics_section(self):
        """
        Replaces and updates the .swn file with the physics configuration for a specific domain.

        Raises
        ------
        ValueError
            If no physics information was provided at initialization or via define_generation().
        """

        if self.dict_info is None:
            raise ValueError(f'Physics information is not provided for domain {self.domain_number}. '
                             'Please provide dict_info or call define_generation() first.')

        print(f'\n \t*** Adding/Editing physics information for domain {self.domain_number} in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}domain_0{self.domain_number}/run.swn', self.dict_info)
