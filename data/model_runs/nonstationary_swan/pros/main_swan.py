import warnings
warnings.filterwarnings('ignore')

from datetime import datetime, timedelta

from oceanicospy.models.swanpy import Initializer
from oceanicospy.models.swanpy.preprocess import (
    GridMaker,
    BathyMaker,
    BottomFrictionProcessor,
    WindForcing,
    WaterLevelForcing,
    BoundaryConditions,
)
from oceanicospy.models.swanpy.execution import CaseRunner

# ---------------------------------------------------------------------------
# Domain definitions
# ---------------------------------------------------------------------------
domains = {
    1: {
        "grid": dict(lon_ll_corner=278.2, lat_ll_corner=12.4, x_extent=0.2, y_extent=0.3, nx=222, ny=333),
        "bathy": dict(lon_ll_corner_bot=278.1811, lat_ll_corner_bot=12.372, nx_bot=322, ny_bot=422, dx_bot=0.0009, dy_bot=0.0009),
        "fric": dict(lon_ll_corner_fric=278.1811, lat_ll_corner_fric=12.372, nx_fric=322, ny_fric=422, dx_fric=0.0009, dy_fric=0.0009),
        "wind": dict(lon_ll_corner_wind=278, lat_ll_corner_wind=12.3, nx_wind=24, ny_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_corner_wl=278.1811, lat_ll_corner_wl=12.372, nx_wl=322, ny_wl=422, dx_wl=0.0009, dy_wl=0.0009),
        "parent": None
    },
    2: {
        "grid": dict(lon_ll_corner=278.2265167, lat_ll_corner=12.4413166, x_extent=0.13185, y_extent=0.1908, nx=293, ny=424),
        "bathy": dict(lon_ll_corner_bot=278.2265167, lat_ll_corner_bot=12.4413166, nx_bot=293, ny_bot=424, dx_bot=0.00045, dy_bot=0.00045),
        "wind": dict(lon_ll_corner_wind=278, lat_ll_corner_wind=12.3, nx_wind=24, ny_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_corner_wl=278.2265167, lat_ll_corner_wl=12.4413166, nx_wl=293, ny_wl=424, dx_wl=0.00045, dy_wl=0.00045),
        "fric": dict(lon_ll_corner_fric=278.2265167, lat_ll_corner_fric=12.4413166, nx_fric=293, ny_fric=424, dx_fric=0.00045, dy_fric=0.00045),
        "parent": 1
    },
    3: {
        "grid": dict(lon_ll_corner=278.270165, lat_ll_corner=12.550217, x_extent=0.0747, y_extent=0.0747, nx=332, ny=332),
        "bathy": dict(lon_ll_corner_bot=278.270165, lat_ll_corner_bot=12.550217, nx_bot=332, ny_bot=332, dx_bot=0.000225, dy_bot=0.000225),
        "wind": dict(lon_ll_corner_wind=278, lat_ll_corner_wind=12.3, nx_wind=24, ny_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_corner_wl=278.270165, lat_ll_corner_wl=12.550217, nx_wl=332, ny_wl=332, dx_wl=0.000225, dy_wl=0.000225),
        "fric": dict(lon_ll_corner_fric=278.270165, lat_ll_corner_fric=12.550217, nx_fric=332, ny_fric=332, dx_fric=0.000225, dy_fric=0.000225),
        "parent": 2
    },
    4: {
        "grid": dict(lon_ll_corner=360 - 81.72, lat_ll_corner=12.5, x_extent=0.055, y_extent=0.055, nx=243, ny=243),
        "bathy": dict(lon_ll_corner_bot=360 - 81.72, lat_ll_corner_bot=12.5, nx_bot=243, ny_bot=243, dx_bot=0.000225, dy_bot=0.000225),
        "wind": dict(lon_ll_corner_wind=278, lat_ll_corner_wind=12.3, nx_wind=24, ny_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_corner_wl=360 - 81.72, lat_ll_corner_wl=12.5, nx_wl=243, ny_wl=243, dx_wl=0.000225, dy_wl=0.000225),
        "fric": dict(lon_ll_corner_fric=360 - 81.72, lat_ll_corner_fric=12.5, nx_fric=243, ny_fric=243, dx_fric=0.000225, dy_fric=0.000225),
        "parent": 2
    }
}

# ---------------------------------------------------------------------------
# Case parameters
# ---------------------------------------------------------------------------
path_case = '../'

ini_date = datetime(2023, 5, 7, 0)
end_date = datetime(2023, 5, 31, 23)

dict_ini_data = dict(
    name             = 'Non-stationary case for San Andres',
    case_number      = 2,
    case_description = 'Example non-stat',
    stat_id          = 0,
    number_domains   = len(domains),
    parent_domains   = {d: cfg["parent"] for d, cfg in domains.items()},
)

# Boundary sample points (domain 1 only)
lat_boundaries_dom01 = [12.40, 12.50, 12.60, 12.70]
lon_boundaries_dom01 = [-81.80, -81.70, -81.60]

# ---------------------------------------------------------------------------
# Compilation data per domain
# ---------------------------------------------------------------------------
_common = dict(
    ini_output_date = (ini_date + timedelta(days=5)).strftime('%Y%m%d.%H%M%S'),
    output_res_min  = 60,
    stat_comp       = 0,
    dt_min          = 10,
    end_comp_date   = end_date.strftime('%Y%m%d.%H%M%S'),
)

compilation_data = {
    1: {**_common, "ini_comp_date": ini_date.strftime('%Y%m%d.%H%M%S'),
                   "ini_nest_date": (ini_date + timedelta(days=2)).strftime('%Y%m%d.%H%M%S')},
    2: {**_common, "ini_comp_date": (ini_date + timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
                   "ini_nest_date": (ini_date + timedelta(days=2)).strftime('%Y%m%d.%H%M%S')},
    3: {**_common, "ini_comp_date": (ini_date + timedelta(days=2)).strftime('%Y%m%d.%H%M%S')},
    4: {**_common, "ini_comp_date": (ini_date + timedelta(days=2)).strftime('%Y%m%d.%H%M%S')},
}

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
case = Initializer(
    root_path     = path_case,
    dict_ini_data = dict_ini_data,
    ini_date      = ini_date,
    end_date      = end_date,
)

case.create_folders()
case.replace_ini_data()

# ---------------------------------------------------------------------------
# Single loop over all domains
# ---------------------------------------------------------------------------
for domain_id, config in domains.items():

    # ----- Grid information -----
    case_grid = GridMaker(init=case, domain_number=domain_id, dict_info=config["grid"])
    case_grid.fill_grid_section()

    # ----- Bathymetry information -----
    case_bathy = BathyMaker(init=case, domain_number=domain_id, dict_info=config["bathy"])
    case_bathy.use_ascii_file_from_user()
    case_bathy.fill_bathy_section()

    # ----- Bottom friction information -----
    case_fric = BottomFrictionProcessor(init=case, domain_number=domain_id, dict_info=config["fric"])
    case_fric.use_ascii_file_from_user()
    case_fric.fill_friction_section()

    # ----- Wind forcing (ERA5) -----
    case_wind = WindForcing(init=case, domain_number=domain_id, dict_info=config["wind"])
    case_wind.get_winds_from_ERA5(difference_to_UTC=-5)
    case_wind.write_ERA5_ascii('winds_era5.nc', 'winds.wnd')
    case_wind.fill_wind_section()

    # ----- Water level forcing (UHSLC) -----
    case_wl = WaterLevelForcing(init=case, domain_number=domain_id, dict_info=config["wl"])
    df_wl = case_wl.get_waterlevel_from_UHSLC(station_id=737)

    correction_mask = (
        (df_wl.index >= datetime(1997, 1, 1, 0)) &
        (df_wl.index <= datetime(2018, 12, 31, 18))
    )
    df_wl.loc[correction_mask, "depth[m]"] -= 2.0

    case_wl.write_UHSLC_ascii(df_wl, 'water_levels.wl')
    case_wl.fill_wl_section()

    # ----- Boundary conditions (ERA5 TPAR for domain 1, nested for the rest) -----
    case_boundary = BoundaryConditions(
        init          = case,
        domain_number = domain_id,
        dict_info     = {'bound_type': 'side', 'variable_bound': False},
    )
    case_boundary.get_waves_from_ERA5(difference_to_UTC=-5, wind_info_dict=config["wind"])
    case_boundary.tpar_from_ERA5(points_lat=lat_boundaries_dom01, points_lon=lon_boundaries_dom01)
    case_boundary.create_boundary_line(
        list_sides=['N', 'S', 'E', 'W'],
        points_lon=lon_boundaries_dom01,
        points_lat=lat_boundaries_dom01,
    )
    case_boundary.fill_boundaries_section()

    # ----- Run / output configuration -----
    case_runner = CaseRunner(
        init           = case,
        domain_number  = domain_id,
        dict_comp_data = compilation_data[domain_id],
        all_domains    = domains,
    )
    case_runner.define_output_from_file(filename='SalidasSWAN.txt')
    case_runner.write_nest_section()
    case_runner.fill_computation_section()
