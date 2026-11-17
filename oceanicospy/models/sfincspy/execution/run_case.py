import shutil
from pathlib import Path

from .... import utils


class CaseRunner:
    """
    Write the SLURM script that runs a built SFINCS case on an HPC cluster
    through a Singularity container.

    Follows ``xbeachpy.execution.CaseRunner.fill_slurm_file``, with its own
    template (``data/hpc_slurm_templates/launcher_sfincs_cecc_base.slurm``).
    SFINCS runs with OpenMP inside the container, without ``mpirun``, and
    writes its output (``sfincs_map.nc``, ``sfincs_his.nc``, ``sfincs.log``)
    in the ``run/`` folder; only the SLURM log files go to ``output/``.

    Parameters
    ----------
    dict_folders : dict
        Case folders, with at least the keys ``"run"`` and ``"output"``
        (see :class:`~oceanicospy.models.sfincspy.Initializer`).

    Notes
    -----
    SFINCS reads ``sfincs.inp`` from the working directory, so the template
    changes to the run folder before calling the executable.
    """

    def __init__(self, dict_folders: dict) -> None:
        self.dict_folders = dict_folders
        print('\n*** Initializing SFINCS Case Runner ***\n')

    def fill_slurm_file(
        self,
        case_name: str,
        ntasks: int,
        image_name: str = "sfincs-cpu_sfincs-v2.3.0-mt-Faber-Release.sif",
    ) -> str:
        """
        Copy the SFINCS SLURM template to the case ``run/`` folder and fill it.

        Parameters
        ----------
        case_name : str
            Case name, used as ``--job-name``.
        ntasks : int
            Tasks per node (``--ntasks-per-node``), i.e. the OpenMP threads
            available to SFINCS.
        image_name : str, optional
            Singularity image in ``/localapps`` on the cluster. Default is
            the SFINCS v2.3.0 "Faber" CPU image.

        Returns
        -------
        str
            Path of the ``.slurm`` script, ready for ``sbatch``.
        """
        script_dir = Path(__file__).resolve().parent.parent.parent.parent
        data_dir = script_dir.parent / 'data'

        template_path = data_dir / 'hpc_slurm_templates' / 'launcher_sfincs_cecc_base.slurm'
        out_path = Path(self.dict_folders['run']) / 'launcher_sfincs.slurm'

        shutil.copy(template_path, out_path)

        launch_dict = dict(
            case_name=case_name,
            run_path_case=f'{self.dict_folders["run"]}',
            output_path_case=f'{self.dict_folders["output"]}',
            number_tasks=ntasks,
            image_name=image_name,
        )
        utils.fill_files(str(out_path), launch_dict)

        return str(out_path)
