import warnings
warnings.filterwarnings('ignore')

from oceanicospy.models.swanpy import Initializer
from oceanicospy.models.swanpy.preprocess import GridMaker, BathyMaker, WindForcing, BottomFrictionProcessor, BoundaryConditions
from oceanicospy.models.swanpy.execution import CaseRunner

path_case = '../'

dict_ini_data = dict(
    name            = 'Stationary case for San Andres',
    case_number     = 1,
    case_description= 'Example',
    stat_id         = 1,
    number_domains  = 1
)

case = Initializer(
    root_path    = path_case,
    dict_ini_data= dict_ini_data,
)

case.create_folders()    # creates all project folders (data/, output/, etc.)
case.replace_ini_data()     # writes run.swn from the STAT template

DOMAIN_ID = 1   # domain identifier (1-indexed)

#--------- Grid information ------------#

case_grid = GridMaker(
    init         = case,
    domain_number= DOMAIN_ID,
    dict_info    = {'lon_ll_corner': 278.2265167, 
                    'lat_ll_corner': 12.4413166, 
                    'x_extent': 0.13185, 
                    'y_extent': 0.1908, 
                    'nx': 293,
                    'ny': 424},
)

print(f'The grid info dictionary for domain {DOMAIN_ID} is: {case_grid.dict_info}')
case_grid.fill_grid_section()

#--------- Bathymetry information ------------#

case_bathy = BathyMaker(
    init         = case,
    domain_number= DOMAIN_ID,
    dict_info   = {'lon_ll_corner_bot': 278.2265167, 'lat_ll_corner_bot': 12.4413166,
                    'nx_bot': 293, 'ny_bot': 424, 
                    'dx_bot': 0.00045, 'dy_bot': 0.00045},     
)

case_bathy.use_ascii_file_from_user()

print(f'The bathymetry info dictionary for domain {DOMAIN_ID} is: {case_bathy.dict_info}')
case_bathy.fill_bathy_section()

# -------- Bottom friction information ------------#

case_bottom_friction = BottomFrictionProcessor(
    init         = case,
    domain_number= DOMAIN_ID,
    dict_info    = 
        {'lon_ll_corner_fric': 278.2265167, 'lat_ll_corner_fric': 12.4413166,
         'nx_fric': 293, 'ny_fric': 424,
         'dx_fric': 0.00045, 'dy_fric': 0.00045}
    )  # using grid info to fill friction section

case_bottom_friction.use_ascii_file_from_user()
print(case_bottom_friction.dict_info)
case_bottom_friction.fill_friction_section()

# -------- Wind forcing information ------------#

case_winds = WindForcing(
    init         = case,
    domain_number= DOMAIN_ID,
)

case_winds.use_constant_wind(wind_speed=12.8, wind_dir=90)
print(f'The wind info dictionary for domain {DOMAIN_ID} is: {case_winds.dict_info}')
case_winds.fill_wind_section()

# -------- Boundary conditions information ------------#

case_boundary = BoundaryConditions(
    init        = case,
    domain_number= DOMAIN_ID,
    dict_info   = {"boundary_type": "side"})

case_boundary.create_boundary_line(list_sides=["N"],wave_params={'hs': 1.7, 'tp': 9, 'dir': 90 , 'spread':2})
case_boundary.fill_boundaries_section()

comp_data_stat = dict(
    stat_comp        = 1,               # 1 → stationary
)

# --------- Run section------------#
case_run = CaseRunner(
    init         = case,
    domain_number= DOMAIN_ID,
    dict_comp_data= comp_data_stat
)

# define point output locations from a CSV with X, Y columns
case_run.define_output_from_file(filename='output_points.csv')

# Write the COMPUTE command and clean up any remaining template placeholders
case_run.fill_computation_section()