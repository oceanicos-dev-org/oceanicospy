import subprocess
from . import utils
from pathlib import Path
import shutil
import os
from string import Template

class Initializer():
    """
    Set up the directory structure and base configuration for an XBeach simulation.

    ``Initializer`` is the entry point for every XBeach case.  It builds the
    standard four-folder layout (``input/``, ``pros/``, ``run/``, ``output/``),
    and stamps the bundled ``params_base.txt`` template with the user-supplied
    case flags via :meth:`replace_ini_data`.

    Parameters
    ----------
    root_path : str
        Root directory of the case.  All sub-folders are created inside this
        path.  Must end with a trailing slash (e.g. ``'path/to/case/'``).
    dict_ini_data : dict
        Case-level flags that override the package defaults in
        ``xbeachpy/utils/defaults.py`` and are substituted into
        ``params.txt``.  Typical keys:

        - ``case_description`` — free-form label (not used by XBeach)
        - ``act_morf`` — morphological updating (``0`` = off)
        - ``act_sedtrans`` — sediment transport (``0`` = off)
        - ``act_wavemodel`` — spectral wave model (``1`` = surfbeat)
        - ``dims`` — number of dimensions (``2`` = 2D)

    ini_date : datetime, optional
        Simulation start date.  Used downstream by preprocessing and
        execution classes to slice forcing datasets and compute ``tstop``.
    end_date : datetime, optional
        Simulation end date.  Same usage as ``ini_date``.
    """

    def __init__(self, root_path, dict_ini_data, ini_date=None, end_date=None):

        self.root_path = root_path
        self.ini_date = ini_date
        self.end_date = end_date
        self.dict_ini_data = dict_ini_data
        self.folder_names = ['input','pros','run','output']
        self.dict_folders = {}
        for folder_name in self.folder_names:
            self.dict_folders[folder_name] = f'{self.root_path}{folder_name}/'

        print('*** Initializing XBeach model ***\n')

    def _generate_baseline_XBeach(self, template_in, template_out, replacement_dict):
        """
        Render a ``$placeholder`` template file and write the result to disk.

        Reads ``template_in``, applies :class:`string.Template.safe_substitute`
        with ``replacement_dict`` (leaving any unmatched placeholders untouched),
        and writes the rendered text to ``template_out``.

        Parameters
        ----------
        template_in : str or Path
            Path to the source template file containing ``$key`` placeholders.
        template_out : str or Path
            Destination path for the rendered output file.
        replacement_dict : dict
            Mapping of placeholder names to replacement values.  Keys not
            present in the template are silently ignored; placeholders without
            a matching key are left as-is.
        """
        template_text = Path(template_in).read_text()

        # substitute available keys, leave others as-is
        filled_text = Template(template_text).safe_substitute(replacement_dict)

        Path(template_out).write_text(filled_text)

    def create_folders(self):
        """
        Create the standard XBeach folder structure under ``root_path``.

        Creates ``input/``, ``pros/``, ``run/``, and ``output/`` directories.
        If ``run/`` already exists it is **deleted and re-created** to avoid
        stale files from a previous attempt.  All other folders are left
        untouched if they already exist.
        """
        print('\n*** Creating project structure ***\n')
        for folder_name in self.folder_names:
            if not os.path.exists(self.dict_folders[folder_name]):
                subprocess.call(['mkdir','-p',f'{self.dict_folders[folder_name]}'])
            else:
                if folder_name=='run':
                    print (f'\n \t *** Cleaning existing run folder: {self.dict_folders[folder_name]} ***\n')
                    shutil.rmtree(self.dict_folders[folder_name])
                    subprocess.call(['mkdir','-p',f'{self.dict_folders[folder_name]}'])

    def replace_ini_data(self):
        """
        Copy the base ``params.txt`` template into ``run/`` and substitute case flags.

        Locates the bundled ``params_base.txt`` template (under
        ``data/model_config_templates/xbeach/``), merges the package defaults
        from ``xbeachpy/utils/defaults.py`` with the user-supplied
        ``dict_ini_data`` (user values take precedence), and writes the
        rendered file to ``<run>/params.txt``.

        All values in ``dict_ini_data`` are cast to ``str`` before substitution
        as required by the :class:`string.Template` engine.

        Must be called after :meth:`create_folders` so that ``run/`` exists.
        """
        print('\n\t*** Copying base XBeach configuration file into run folder ***\n')

        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        for key,value in self.dict_ini_data.items():
            if (type(value)==float) or (type(value)==int):
                self.dict_ini_data[key]=str(value)
            self.dict_ini_data[key]=str(value)

        merged = {**utils.defaults, **self.dict_ini_data}
        self._generate_baseline_XBeach(f'{self.data_dir}/model_config_templates/xbeach/params_base.txt', 
                                             f'{self.dict_folders["run"]}params.txt',merged)