import numpy as np
import pandas as pd
import glob as glob

class WindForcing():

    def write_constant_wind(self, ascii_filepath):
        """
        Writes constant wind data to an ASCII file.

        Parameters
        ----------
        ascii_filepath : str
            Path to the output ASCII file.

        Returns
        -------
        dict
            Dictionary containing wind parameters.
        """
        ds = pd.read_csv(f'{self.dict_folders["input"]}{self.input_filename}', delimiter=' ')
        dates = pd.date_range(self.ini_date, self.end_date, freq='1h')
        ds = ds.set_index(dates)
        ds_to_save = ds[['Dir', 'Vel']]
        ds_to_save.index = ds_to_save.index.strftime('%Y%m%d.%H%M%S')

        file = open(f'{self.dict_folders["run"]}{ascii_filepath}', 'w')
        for idx, t in enumerate(ds_to_save.index):
            file.write(t)
            file.write('\n')
            ds_to_save['Dir_to'] = (ds_to_save['Dir'] + 180) % 360
            u10_to_write = ds_to_save['Vel'].iloc[idx] * np.sin(np.deg2rad(ds_to_save['Dir_to'].iloc[idx]))
            v10_to_write = ds_to_save['Vel'].iloc[idx] * np.cos(np.deg2rad(ds_to_save['Dir_to'].iloc[idx]))

            u10_to_write = round(u10_to_write, 2)
            v10_to_write = round(v10_to_write, 2)

            u10_to_write = u10_to_write * np.ones((25, 25))
            v10_to_write = v10_to_write * np.ones((25, 25))

            file.write(pd.DataFrame(u10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))
            file.write(pd.DataFrame(v10_to_write).to_csv(index=False, header=False, na_rep=0, float_format='%7.3f').replace(',', ' '))

        file.close()

        ll_lon_on, ll_lat_on = 4931900, 2799400  # quemado

        self.wind_params = dict(
            lon_ll_wind=ll_lon_on,
            lat_ll_wind=ll_lat_on,
            meshes_x_wind=24,
            meshes_y_wind=24,
            dx_wind=2000,
            dy_wind=2000,
            ini_wind_date=ds_to_save.index[0],
            dt_wind_hours=1,
            end_wind_date=ds_to_save.index[-1],
        )
        return self.wind_params

    def winds_from_user(self):
        wind_file_path = glob.glob(f'{self.dict_folders["input"]}domain_0{self.domain_number}/*.wnd')[0]
        wind_filename = wind_file_path.split('/')[-1]

        if not utils.verify_link(wind_filename, f'{self.dict_folders["run"]}domain_0{self.domain_number}/'):
            utils.create_link(
                wind_filename,
                f'{self.dict_folders["input"]}domain_0{self.domain_number}/',
                f'{self.dict_folders["run"]}domain_0{self.domain_number}/',
            )

        if self.wind_info is not None:
            self.wind_info.update({"winds.wnd": wind_filename})
            return self.wind_info
