import numpy as np
import glob as glob

# TODO: a call to gis module should be implemented here to obtain a standardized bathymetry info.

class GridMaker():

    def get_info_from_bathy(self):
        """
        Extracts grid parameters from the bathymetry file for the specified domain.

        Reads the `.dat` bathymetry file, computes the geographic extents, and derives
        the number of grid cells in each direction based on `dx` and `dy`.

        Returns
        -------
        dict
            Dictionary with string-valued grid parameters: ``lon_ll_corner``,
            ``lat_ll_corner``, ``x_extent``, ``y_extent``, ``nx``, and ``ny``.
        """

        bathy_file_path = glob.glob(f'{self.init.dict_folders["input"]}domain_0{self.domain_number}/*.dat')[0]

        data = np.loadtxt(bathy_file_path)
        longitude = data[:, 0]
        latitude = data[:, 1]

        min_longitude = np.min(longitude)
        min_latitude = np.min(latitude)

        max_longitude = np.max(longitude)
        max_latitude = np.max(latitude)
        min_longitude = int(np.ceil(min_longitude / 100) * 100)
        max_longitude = int(np.floor(max_longitude / 100) * 100)
        min_latitude = int(np.ceil(min_latitude / 100) * 100)
        max_latitude = int(np.floor(max_latitude / 100) * 100)

        x_extent = max_longitude - min_longitude
        y_extent = max_latitude - min_latitude

        nx = int(x_extent / self.dx)
        ny = int(y_extent / self.dy)

        self.grid_info = {
            'lon_ll_corner': min_longitude,
            'lat_ll_corner': min_latitude,
            'x_extent': x_extent,
            'y_extent': y_extent,
            'nx': nx,
            'ny': ny,
        }
        for key, value in self.grid_info.items():
            self.grid_info[key] = str(value)

        return self.grid_info
