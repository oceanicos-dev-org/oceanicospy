from wavespectra import read_swan
import numpy as np
import pandas as pd
import re
import os

from .... import utils

class BoundaryConditions:
    """
    Class representing the boundary conditions for a simulation.
    Args:
        input_filename (str): The name of the input file.
        dict_bounds_params (dict): A dictionary containing the boundary parameters.
        list_sides (list): A list of sides.
    Attributes:
        input_filename (str): The name of the input file.
        dict_bounds_params (dict): A dictionary containing the boundary parameters.
    Methods:
        fill_boundaries_section(*args): Fill the boundaries section of the simulation.
    """
    def __init__ (self,init):
        self.init = init
        self.purger()
        print('*** Initializing Boundary Conditions ***')

    def purger(self):
        """
        Purge the boundary conditions.
        """
        print('*** Purging Boundary Conditions ***')
        os.system(f'rm -rf {self.init.dict_folders["run"]}bounds_conds')

    # def create_filelist(self):
    #     """
    #     Create a list of files.
    #     Returns:
    #         list: A list of files.
    #     """
    #     time_s = pd.date_range(self.ini_date,self.end_date, freq='1h')

    #     with open(f'{self.dict_folders["run"]}filelist.txt','w') as f:
    #         f.write('FILELIST \n')
    #         for idx_time in range(len(time_s)):
    #             f.write(f'3600 0.2 spectra8_{idx_time+1:03d}.sp2\n')
    #     f.close()
    #     os.system(f'cp {self.dict_folders["input"]}spectra8*.sp2 {self.dict_folders["run"]}')
    #     dict_boundaries={'bcfilepath':'filelist.txt'}
    #     return dict_boundaries

    # -------------------------------------------------------------------------
    # spectra_from_swan helpers
    # -------------------------------------------------------------------------

    def _load_dataset(self, input_filename,point_indexes=None):
        """
        Load a SWAN spectra output file and restrict it to the simulation time window.

        Parameters
        ----------
        input_filename : str
            Name of the SWAN output file (without extension) located in
            ``self.init.dict_folders["input"]``.

        Returns
        -------
        xarray.Dataset
            Dataset containing the spectral energy ``efth`` and coordinate
            variables ``time``, ``site``, ``lon``, and ``lat``, sliced to
            ``[self.init.ini_date, self.init.end_date]``.

        Raises
        ------
        RuntimeError
            If the loaded dataset does not contain a ``time`` coordinate.
        """
        self.dataset = read_swan(f'{self.init.dict_folders["input"]}{input_filename}')
        if "time" not in self.dataset.coords:
            raise RuntimeError("Loaded dataset has no 'time' coordinate to filter on.")
        start = np.datetime64(self.init.ini_date)
        end = np.datetime64(self.init.end_date)

        if point_indexes is not None:
            self.dataset = self.dataset.isel(site=point_indexes)
        return self.dataset.sel(time=slice(start, end))

    def _write_sp2_header(self, forigin, fdest, lon, lat):
        """
        Copy and transform the header block from a SWAN spectra file into an sp2 file.

        Reads ``forigin`` line-by-line until the ``'date and time'`` sentinel is
        encountered, writing each line to ``fdest`` after applying two in-place
        transformations:

        - **number of locations**: rewrites the location count to ``1`` and retains
          only the coordinate line that matches ``(lon, lat)``.
        - **number of directions**: reads the following 36 direction values and
          offsets each by 270 degrees to convert from SWAN's convention to XBeach's.

        Parameters
        ----------
        forigin : file-like
            Opened ``SpecSWAN.out`` file positioned at the beginning of a
            header block.
        fdest : file-like
            Opened destination ``.sp2`` file to which the transformed header
            is written.
        lon : float
            Longitude of the target site, used to identify its coordinate line
            in the ``'number of locations'`` block.
        lat : float
            Latitude of the target site (formatted to 5 decimal places for
            string matching).

        Notes
        -----
        The function stops reading ``forigin`` as soon as the ``'date and time'``
        line is found, leaving the file cursor positioned immediately after that
        line so that the caller can continue reading the spectral data.
        """
        while True:
            line = forigin.readline()
            if 'date and time' in line:
                break
            if 'number of locations' in line:
                line = re.sub(r'\d+', "1", line)
                for _ in range(self.number_spectrum_locs): # sounds better a while
                    next_line = forigin.readline()
                    print(f"Checking lat {lat:.5f} lon {lon}, line: {next_line}")
                    next_line_list = [float(x) for x in next_line.split('   ') if x]
                    print(f"Parsed line into floats: {next_line_list}")
                    if (lon in next_line_list) and (lat in next_line_list):
                        line = line + next_line
                        print(line)
            line+='This is a comment line added to the header\n'
            if 'number of directions' in line:
                for _ in range(36):
                    next_line = forigin.readline()
                    line = line + str(float(next_line) + 270) + '\n'
            fdest.write(line)

    def _write_sp2_spectrum(self, fdest, spec_matrix, time_str):
        """
        Write the spectral data block to an sp2 file.

        Appends the timestamp, the ``FACTOR`` header with its scaling value,
        and the normalised spectral energy matrix to ``fdest``.

        Parameters
        ----------
        fdest : file-like
            Opened destination ``.sp2`` file, already containing the header
            block written by :meth:`_write_sp2_header`.
        spec_matrix : numpy.ndarray, shape (n_freq, n_dir)
            Spectral energy array normalised by the FACTOR value (``0.1E-05``),
            so that each element is written as a rounded integer.
        time_str : str
            Timestamp string in SWAN format ``'YYYYMMDD.HHMMSS'``.
        """
        fdest.write(time_str + '\n')
        fdest.write('FACTOR\n')
        fdest.write('0.1E-05\n')
        for row in spec_matrix:
            np.savetxt(fdest, row, fmt='%5.0f')

    def _write_sp2_file(self, site_idx, time_idx, lon, lat):
        """
        Write a single ``.sp2`` file for one site/time-step combination.

        Opens the source ``SpecSWAN.out`` and the destination ``.sp2`` file,
        then delegates to :meth:`_write_sp2_header` and
        :meth:`_write_sp2_spectrum` to produce a self-contained SWAN spectra
        file for a single location and timestamp.

        Parameters
        ----------
        site_idx : int
            Index of the boundary site within ``self.dataset.site``.
        time_idx : int
            Index of the time step within ``self.dataset.time``.
        lon : float
            Longitude of the site, forwarded to :meth:`_write_sp2_header`
            for location-line matching.
        lat : float
            Latitude of the site, forwarded to :meth:`_write_sp2_header`
            for location-line matching.

        Notes
        -----
        The output file is written to
        ``<run>/bounds_conds/point_<site_idx>/spec_time<time_idx>_point<site_idx>.sp2``.
        The spectral energy is normalised by ``0.1E-05`` before being passed
        to :meth:`_write_sp2_spectrum`.
        """
        spec_matrix = np.array(self.data_spectra[time_idx, site_idx, :, :]) / 0.1e-5
        time_str = pd.to_datetime(self.dataset.time.values[time_idx]).strftime('%Y%m%d.%H%M%S')
        sp2_path = (
            f"{self.init.dict_folders['run']}"
            f"bounds_conds/point_{site_idx}/spec_time{time_idx}_point{site_idx}.sp2"
        )
        with open(f"{self.init.dict_folders['input']}SpecSWAN.out") as forigin:
            with open(sp2_path, "w") as fdest:
                self._write_sp2_header(forigin, fdest, lon, lat)
                self._write_sp2_spectrum(fdest, spec_matrix, time_str)

    def _write_site_filelist(self, site_idx):
        """
        Create the output directory and ``filelist_<site_idx>.txt`` for one boundary site.

        For each time step in ``self.dataset.time``, calls :meth:`_write_sp2_file`
        to produce the individual ``.sp2`` spectra files and then records each
        entry (duration, directional spreading, relative path) in the filelist.

        Parameters
        ----------
        site_idx : int
            Index of the boundary site within ``self.dataset.site``.  Must be
            greater than or equal to 3 (sites 0–2 are reserved and skipped by
            :meth:`spectra_from_swan`).

        Notes
        -----
        The output directory ``<run>/bounds_conds/point_<site_idx>/`` is created
        with ``exist_ok=True``, so re-running is safe.  The filelist is written to
        ``<run>/bounds_conds/filelist_<site_idx>.txt`` with one entry per time step
        in the format expected by XBeach (``3600 0.2 '<relative_sp2_path>'``).
        """
        bounds_conds_path = os.path.join(
            self.init.dict_folders["run"], "bounds_conds", f"point_{site_idx}"
        )
        os.makedirs(bounds_conds_path, exist_ok=True)

        self.lon = self.dataset.lon[site_idx]
        self.lat = self.dataset.lat[site_idx]
        filelist_path = f"{self.init.dict_folders['run']}bounds_conds/filelist_{site_idx}.txt"

        with open(filelist_path, "w") as filelist:
            filelist.write('FILELIST\n')
            for idx_time in range(len(self.dataset.time)):
                self._write_sp2_file(site_idx, idx_time, self.lon.values, self.lat.values)
                filelist.write(
                    f"3600 0.2 'bounds_conds/point_{site_idx}/"
                    f"spec_time{idx_time}_point{site_idx}.sp2'\n"
                )

    def _write_loclist(self, offshore_points):
        """
        Write ``loclist.txt`` mapping each active boundary site to its filelist.

        Iterates over all sites with index >= 3 and writes one entry per site
        to ``<run>/bounds_conds/loclist.txt``.  If ``offshore_points`` is
        provided, only the listed site indices are included.

        Parameters
        ----------
        offshore_points : list of int or None
            Subset of site indices to include in the loclist.  When ``None``
            all sites with index >= 3 are written.  Site positions are placed
            at ``x = 0`` and ``y = -(site_idx) * 100``.
        """
        loclist_path = f"{self.init.dict_folders['run']}bounds_conds/loclist.txt"
        with open(loclist_path, "w") as floc:
            floc.write('LOCLIST\n')
            for idx_site in range(self.number_spectrum_locs):
                if offshore_points is not None and idx_site not in offshore_points:
                    continue
                floc.write(f"0 {-(idx_site) * 100} 'bounds_conds/filelist_{idx_site}.txt'\n")

    def spectra_from_swan(self, input_filename, point_indexes=None, offshore_points=None):
        self.dataset = self._load_dataset(input_filename,point_indexes)
        self.data_spectra = self.dataset.efth
        self.number_spectrum_locs = len(self.dataset.site)

        if self.number_spectrum_locs == 1:
            print('delete the loclist section and the nspectrumloc command')
        else:
            self.dict_boundaries = {
                'w_bc_version': 3,
                'n_spectrum_loc': self.number_spectrum_locs,
                'bcfilepath': 'bounds_conds/loclist.txt',
            }

        for idx_site in range(self.number_spectrum_locs):
            self._write_site_filelist(idx_site)

        self._write_loclist(offshore_points)

    def fill_boundaries_section(self):
        """
        """
        for param in self.dict_boundaries:
            self.dict_boundaries[param]=str(self.dict_boundaries[param])

        print (f'\n*** Adding/Editing boundary information for domain in configuration file ***\n')
        utils.fill_files(f'{self.init.dict_folders["run"]}params.txt',self.dict_boundaries)
