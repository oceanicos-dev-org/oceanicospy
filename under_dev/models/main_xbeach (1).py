# Importing libraries
from oceanicospy.models import xbeachpy
import os
import datetime as dt
import warnings
warnings.filterwarnings("ignore")

# ============================================================================
# Case configuration 
# ============================================================================
path_case = "/scratchsan/medellin/lroserom/tesis/runs/xbeach/calibration/MayJun2025_C1/"
case_description = "MayJun 2025 – Case C1"

ini_date = dt.datetime(2025, 5, 11, 13)
end_date = dt.datetime(2025, 5, 16, 13)

ini_case_data = dict(case_description=case_description, act_morf=0, act_sedtrans=0, act_wavemodel=1, dims=1)

comp_data_nonstat = dict(ini_comp_date=ini_date.strftime("%Y%m%d.%H%M%S"),
                         end_comp_date=end_date.strftime("%Y%m%d.%H%M%S"),
                         tint_value=3600,
                         tintg_value=3600,
                         D50_value=0.0003)
# --------------------------------------------------------------------------
# Grid geometry
# --------------------------------------------------------------------------
dx_profile = 5.0  # spacing in x-direction
profile_filename = "profile.csv" 

# --------------------------------------------------------------------------
# Bathymetry input 
# --------------------------------------------------------------------------
use_profile_file = True  # True: use (x,z) file

# --------------------------------------------------------------------------
# Forcing & output
# --------------------------------------------------------------------------

start_xy = (278.326063,  12.567536)
uhslc_station_code = 737
swan_spec_basename = "SpecSWAN"
output_filename = "profile1D_MayJun2025.nc"

# ============================================================================
# Case initialization
# ============================================================================
case = xbeachpy.Initializer(root_path=path_case, dict_ini_data=ini_case_data, ini_date=ini_date, end_date=end_date)
case.create_folders_l1()
case.replace_ini_data()

# ============================================================================
# Grid
# ============================================================================
case_grid = xbeachpy.preprocess.GridMaker(init=case, dx=dx_profile, profile_csv=profile_filename)
dict_grid = case_grid.rectangular()
case_grid.fill_grid_section(dict_grid)

# ============================================================================
# Bathymetry
# ============================================================================
case_bathy = xbeachpy.preprocess.BathyMaker(init=case, filename="bed.dep")

profile_df = case_bathy.build_1d_profile_from_file(
    profile_filename=profile_filename,
    x_grd_name=dict_grid["xfilepath"],
    dep_name="bed.dep",
)

dict_bathy = dict(
    depfilepath="bed.dep",
    x_bot=dict_grid["meshes_x"],
    y_bot=0,
    spacing_x=0.0,
    spacing_y=0.0,
)

case_bathy.fill_bathy_section(dict_bathy)

# ============================================================================
# Water level
# ============================================================================
case_wl = xbeachpy.preprocess.WaterLevelForcing(init=case, use_link=False)
case_wl.get_waterlevel_from_UHSLC(station_code=uhslc_station_code)
dict_wl = case_wl.write_UHSLC_ascii(f"h{uhslc_station_code}.csv", "water_levels.wl")
case_wl.fill_wl_section(dict_wl)

# ============================================================================
# Waves (SWAN)
# ============================================================================
case_bounds = xbeachpy.preprocess.BoundaryConditions(init=case)
bounds_dict = case_bounds.spectra_from_swan(input_filename=swan_spec_basename,offshore_points=[21])
case_bounds.fill_boundaries_section(bounds_dict)

# ============================================================================
# Wind
# ============================================================================

# Create wind forcing object
case_wind = xbeachpy.preprocess.WindForcing(init=case, use_link=False)

# Wind point location (1D: single point is enough)
lon_wind = start_xy[0]
lat_wind = start_xy[1]

# Wind grid metadata 
case_wind.wind_info = dict(lon_ll_wind=lon_wind, lat_ll_wind=lat_wind, meshes_x_wind=1, meshes_y_wind=1, dx_wind=0.25,dy_wind=0.25)

# Download ERA5 wind
case_wind.get_winds_from_ERA5(
    difference_to_UTC=-5,
    filename="winds_era5.nc",
    override=False,
)

# Write XBeach ASCII wind file 
dict_wind = case_wind.write_ERA5_ascii(
    era5_filename="winds_era5.nc",
    ascii_filename="winds.wnd",
    lon_target=lon_wind,
    lat_target=lat_wind,
)

# Fill wind section in params.txt
case_wind.fill_wind_section(dict_wind)

# ============================================================================
# Output & execution
# ============================================================================
case_output = xbeachpy.execution.CaseRunner(init=case, dict_comp_data=comp_data_nonstat)
case_output.write_output_file(filename=output_filename)
case_output.write_output_points(filename="*points*.txt")
case_output.select_global_vars(["zs", "hh", "zb0", "H", "u"])
case_output.select_point_vars(["zs", "hh", "zb0", "H", "u"])
case_name = os.path.basename(path_case.rstrip("/"))
case_output.fill_slurm_file(case_name)
case_output.fill_computation_section()
