import shutil
from pathlib import Path
from string import Template
from . import utils


class Initializer:
    """
    Utility class for setting up the directory structure and baseline configuration
    files required to run XBeach model simulations.

    It automates the creation and cleanup of the project folder tree and the
    generation of a ``params.txt`` file from a template stamped with user-supplied
    configuration flags.

    The directory layout produced by this class is:

    .. code-block:: text

        root_path/
        ├── input/      ← place your static input files here before running
        ├── pros/
        ├── run/
        │   └── params.txt     ← generated from the bundled template
        └── output/

    Parameters
    ----------
    root_path : str
        Root directory path where the project structure is created.
    dict_ini_data : dict
        Dictionary with case metadata and configuration parameters for XBeach.
        Expected keys:

        * ``case_description`` (*str*) – free-text description of the case.
        * ``act_morf`` (*int*) – morphological updating flag (``0`` = off).
        * ``act_sedtrans`` (*int*) – sediment transport flag (``0`` = off).
        * ``act_wavemodel`` (*int*) – spectral wave model flag (``1`` = surfbeat).
        * ``dims`` (*int*) – dimensionality (``2`` = 2D).

    ini_date : datetime or None
        Start date of the model run. Default is ``None``.
    end_date : datetime or None
        End date of the model run. Default is ``None``.
    """

    def __init__(self, root_path, dict_ini_data, ini_date=None, end_date=None):
        self.root_path = root_path
        self.ini_date = ini_date
        self.end_date = end_date
        self.dict_ini_data = dict_ini_data
        self.folder_names = ['input', 'pros', 'run', 'output']
        self.dict_folders = {
            name: f'{self.root_path}{name}/' for name in self.folder_names
        }

        print('*** Initializing XBeach model ***\n')

    def _generate_baseline_XBeach(self, template_in, template_out, replacement_dict):
        """
        Render an XBeach configuration template and write the result to disk.

        Uses :class:`string.Template` with ``safe_substitute`` so that any
        placeholder not present in *replacement_dict* is left unchanged rather
        than raising an error.

        Parameters
        ----------
        template_in : str or Path
            Path to the source template file (e.g. ``params_base.txt``).
        template_out : str or Path
            Destination path for the rendered file (e.g. ``run/params.txt``).
        replacement_dict : dict
            Key-value pairs used to fill ``$key`` placeholders inside the template.
            Unmapped placeholders are preserved as-is.
        """
        template_text = Path(template_in).read_text()
        filled_text = Template(template_text).safe_substitute(replacement_dict)
        Path(template_out).write_text(filled_text)

    def create_folders(self):
        """
        Create the full project folder structure.

        **Step 1 – top-level directories**

        Creates the four standard sub-directories under ``root_path``:
        ``input/``, ``pros/``, ``run/``, and ``output/``.  On a re-run,
        ``run/`` and ``output/`` are wiped with ``shutil.rmtree`` before being
        recreated so that stale files from a previous execution do not pollute
        the new case.  ``input/`` and ``pros/`` are always left untouched.

        All directories are created with ``Path.mkdir(parents=True,
        exist_ok=True)``, so missing intermediate paths are handled
        automatically.
        """
        print('\n\t*** Creating project folder structure ***\n')

        for folder_name in self.folder_names:
            folder_path = Path(self.dict_folders[folder_name])
            if folder_name in ['output', 'run'] and folder_path.exists():
                shutil.rmtree(folder_path)
            folder_path.mkdir(parents=True, exist_ok=True)

    def replace_ini_data(self):
        """
        Generate the ``params.txt`` file from the bundled XBeach template.

        Reads the base template ``params_base.txt`` from the package data
        directory, fills it using :meth:`_generate_baseline_XBeach` with
        ``dict_ini_data`` merged on top of the package defaults (user values
        take precedence), and writes the result to ``run/params.txt``.
        """
        print('\n\t*** Copying base XBeach configuration file into run folder ***\n')

        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent.parent.parent / 'data'

        str_ini_data = {k: str(v) for k, v in self.dict_ini_data.items()}
        merged = {**utils.defaults, **str_ini_data}

        self._generate_baseline_XBeach(
            f'{self.data_dir}/model_config_templates/xbeach/params_base.txt',
            f'{self.dict_folders["run"]}params.txt',
            merged
        )
