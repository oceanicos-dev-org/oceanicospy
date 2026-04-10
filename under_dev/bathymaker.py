import numpy as np
import glob as glob
from scipy.interpolate import griddata

# TODO: this can be more like a call to gis module to obtain a standardized bathymetry info.

class BathyMaker():

    def convert_xyz2asc(self, nodata_value):
        """
        Converts bathymetry data from XYZ format to ESRI ASCII Grid format.

        Reads a space-delimited `.dat` file, interpolates the scattered data onto a
        regular grid using linear interpolation, and writes the result as an ESRI
        ASCII Grid (`.bot`) file.

        Parameters
        ----------
        nodata_value : float
            Value used to fill cells where interpolation produced NaN.

        Returns
        -------
        dict
            Dictionary with string-valued bathymetry metadata: ``lon_ll_bat_corner``,
            ``lat_ll_bat_corner``, ``x_bot``, ``y_bot``, ``spacing_x``, and ``spacing_y``.
        """
        bathy_xyz_path = glob.glob(f'{self.dict_folders["input"]}*.dat')[0]
        ascfile = f'{self.dict_folders["run"]}{self.filename}.bot'
        np.set_printoptions(formatter={'float_kind': '{:f}'.format})

        # Read bathymetry file
        longitude, latitude, z = np.loadtxt(bathy_xyz_path, delimiter=' ', unpack=True)

        min_longitude = np.min(longitude)
        min_latitude = np.min(latitude)

        max_longitude = np.max(longitude)
        max_latitude = np.max(latitude)

        min_longitude = int(np.ceil(min_longitude / 100) * 100)
        max_longitude = int(np.floor(max_longitude / 100) * 100)
        min_latitude = int(np.ceil(min_latitude / 100) * 100)
        max_latitude = int(np.floor(max_latitude / 100) * 100)

        xmax = max_longitude
        xmin = min_longitude
        ymax = max_latitude
        ymin = min_latitude

        nx_bathy = int((xmax - xmin) / self.dx_bat)
        ny_bathy = int((ymax - ymin) / self.dx_bat)

        # Generate grid with data
        xi, yi = np.mgrid[xmin:xmax:(nx_bathy + 1) * 1j, ymin:ymax:(ny_bathy + 1) * 1j]

        # Interpolate bathymetry. Method can be 'linear', 'nearest' or 'cubic'
        zi = griddata((longitude, latitude), z, (xi, yi), method='linear')
        # Change Nans for values
        zi[np.isnan(zi)] = nodata_value
        # Flip array in the left/right direction
        zi = np.fliplr(zi)
        # Transpose it
        zi = zi.T
        # Write ESRI ASCII Grid file
        zi_str = np.where(zi == nodata_value, str(nodata_value), np.round(zi, 3))
        np.savetxt(ascfile, zi_str, fmt='%8s', delimiter=' ')
        print('File %s saved successfuly.' % ascfile)

        self.grid_info = {
            'lon_ll_bat_corner': min_longitude,
            'lat_ll_bat_corner': min_latitude,
            'x_bot': nx_bathy,
            'y_bot': ny_bathy,
            'spacing_x': self.dx_bat,
            'spacing_y': self.dx_bat,
        }
        for key, value in self.grid_info.items():
            self.grid_info[key] = str(value)
        return self.grid_info
