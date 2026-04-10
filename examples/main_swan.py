from swanpy.init_setup import InitialSetup
from swanpy.preprocess import *
from swanpy.execution import *
import datetime as dt

import warnings
warnings.filterwarnings("ignore")

# User changes start here

path_case = '/home/fayalacruz/runs/swan_guajira/matthew2016/'

case_name = 'Termoguajira'
case_number= 1
case_description = 'Matthew 2016'
ini_date=dt.datetime(2016,9,27)
peak_date=dt.datetime(2016,10,1)
end_date=dt.datetime(2016,10,4)

ini_case_data=dict(name=case_name,case_number=case_number,case_description=case_description,stat_id=0)

comp_data_nonstat=dict(ini_output_date=ini_date.strftime('%Y%m%d.%H%M%S'),output_res_min=60,stat_comp=0,
                            ini_comp_date=ini_date.strftime('%Y%m%d.%H%M%S'),dt_minutes=10,end_comp_date=end_date.strftime('%Y%m%d.%H%M%S'))

# User changes end here

case = InitialSetup(root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case.create_folders_l1()
case.replace_ini_data()

case_grid=MakeGrid(dx=100,dy=100,
                   root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case_grid.fill_grid_section()

case_bathy=MakeBathy(filename='bathymetry',dx_bat=100,
                     root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
dict_bathy=case_bathy.xyz2asc(nodata_value=-9999)
case_bathy.fill_bathy_section(dict_bathy)

case_winds=WindForcing(input_filename='statCases.dat',root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case_winds.write_ERA5_ascii(era5_filepath='windparams_1980_2023.nc',ascii_filepath='winds.wnd')
case_winds.fill_wind_section()

case_bounds=BoundaryConditions(input_filename='waveparams_1980_2023.nc',list_sides=['N','E','W'],
                               root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case_bounds.tpar_from_ERA5_wave_data(output_filename='boundaries.tpar')
case_bounds.fill_boundaries_section('boundaries.tpar')

case_output=RunCase(dict_comp_data=comp_data_nonstat,root_path=path_case,dic_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case_output.output_definition('SalidasSWAN.txt')
case_output.fill_computation_section()