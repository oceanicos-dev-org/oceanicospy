
from oceanicospy.models import xbeachpy

import datetime as dt
import warnings
warnings.filterwarnings("ignore")

# User changes start here 

path_case = '/scratchsan/medellin/XBeach_runs/SB_May2025_C1/'


case_description = '2D sound bay - C1.1'
ini_date = dt.datetime(2025,5,9,4)
end_date = dt.datetime(2025,5,19,18)

wind_dict = dict(lon_ll_wind=278, lat_ll_wind=12.3, meshes_x_wind=24, meshes_y_wind=24, dx_wind=0.025,dy_wind=0.025)

ini_case_data = dict(case_description=case_description,act_morf=0,act_sedtrans=0,act_wavemodel=1,dims=2)

comp_data_nonstat = dict(ini_comp_date=ini_date.strftime('%Y%m%d.%H%M%S'),
                         end_comp_date=end_date.strftime('%Y%m%d.%H%M%S'),
                         tint_value=3600,
                         tintg_value=3600,
                         D50_value=0.0003)

case = xbeachpy.Initializer(root_path=path_case,dict_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case.create_folders_l1()
case.replace_ini_data()

case_grid = xbeachpy.preprocess.GridMaker(init=case,dx=10,dy=10)
dict_grid = case_grid.rectangular(source_file='XBeach_domain.shp')
case_grid.fill_grid_section(dict_grid)

case_bathy = xbeachpy.preprocess.BathyMaker(init=case,filename='bathymetry')
dict_bathy = case_bathy.xyz2asc()
case_bathy.fill_bathy_section(dict_bathy)

case_winds = xbeachpy.preprocess.WindForcing(init=case,wind_info=wind_dict,use_link=False)
case_winds.get_winds_from_ERA5(difference_to_UTC=-5)
dict_winds = case_winds.write_ERA5_ascii('winds_era5.nc','winds.wnd',-81.706, 12.5204) # specific site for interpolation has to be added
case_winds.fill_wind_section(dict_winds)
 
case_wl = xbeachpy.preprocess.WaterLevelForcing(init=case,use_link=False)
case_wl.get_waterlevel_from_UHSLC(station_code=737)
dict_wl = case_wl.write_UHSLC_ascii('h737.csv','water_levels.wl')
case_wl.fill_wl_section(dict_wl)

case_bounds = xbeachpy.preprocess.BoundaryConditions(init=case)
bounds_dict = case_bounds.spectra_from_swan(input_filename='SpecSWAN')
case_bounds.fill_boundaries_section(bounds_dict)

case_output = xbeachpy.execution.CaseRunner(init=case,dict_comp_data=comp_data_nonstat)
case_output.write_output_file(filename='SoundBay2D.nc')
case_output.write_output_points(filename='points_output.txt')
case_output.fill_slurm_file(case_name='May2025_C1')
case_output.select_global_vars(list_vars=['zs','hh','zb0','H','u','v'])
case_output.select_point_vars(list_vars=['zs','hh','zb0','H','u','v'])
case_output.fill_computation_section()