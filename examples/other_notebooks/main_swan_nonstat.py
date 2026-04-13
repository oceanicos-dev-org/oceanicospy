from oceanicospy.models import swanpy

from datetime import datetime,timedelta
import warnings
warnings.filterwarnings("ignore")

path_case = '/scratchsan/medellin/SWAN_runs/May2023_C6/'

case_name = 'May 2023'
case_number = 6
case_description = 'Calibration of SWAN model for May 2023 in SAI using CMDS'

number_domains = 4

domains = {
    1: {
        "grid": dict(lon_ll_corner=278.2, lat_ll_corner=12.4, x_extent=0.2, y_extent=0.3, nx=222, ny=333),
        "bathy": dict(lon_ll_bat_corner=278.1811, lat_ll_bat_corner=12.372, x_bot=322, y_bot=422, spacing_x=0.0009, spacing_y=0.0009),
        "wind": dict(lon_ll_wind=278, lat_ll_wind=12.3, meshes_x_wind=24, meshes_y_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_wl=278.1811, lat_ll_wl=12.372, meshes_x_wl=322, meshes_y_wl=422, dx_wl=0.0009, dy_wl=0.0009),
        "fric": dict(lon_ll_fric=278.1811, lat_ll_fric=12.372, meshes_x_fric=322, meshes_y_fric=422, dx_fric=0.0009, dy_fric=0.0009),
        "parent": None
    },
    2: {
        "grid": dict(lon_ll_corner=278.2265167, lat_ll_corner=12.4413166, x_extent=0.13185, y_extent=0.1908, nx=293, ny=424),
        "bathy": dict(lon_ll_bat_corner=278.2265167, lat_ll_bat_corner=12.4413166, x_bot=293, y_bot=424, spacing_x=0.00045, spacing_y=0.00045),
        "wind": dict(lon_ll_wind=278, lat_ll_wind=12.3, meshes_x_wind=24, meshes_y_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_wl=278.2265167, lat_ll_wl=12.4413166, meshes_x_wl=293, meshes_y_wl=424, dx_wl=0.00045, dy_wl=0.00045),
        "fric": dict(lon_ll_fric=278.2265167, lat_ll_fric=12.4413166, meshes_x_fric=293, meshes_y_fric=424, dx_fric=0.00045, dy_fric=0.00045),
        "parent": 1
    },
    3: {
        "grid": dict(lon_ll_corner=278.270165, lat_ll_corner=12.550217, x_extent=0.0747, y_extent=0.0747, nx=332, ny=332),
        "bathy": dict(lon_ll_bat_corner=278.270165, lat_ll_bat_corner=12.550217, x_bot=332, y_bot=332, spacing_x=0.000225, spacing_y=0.000225),
        "wind": dict(lon_ll_wind=278, lat_ll_wind=12.3, meshes_x_wind=24, meshes_y_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_wl=278.270165, lat_ll_wl=12.550217, meshes_x_wl=332, meshes_y_wl=332, dx_wl=0.000225, dy_wl=0.000225),
        "fric": dict(lon_ll_fric=278.270165, lat_ll_fric=12.550217, meshes_x_fric=332, meshes_y_fric=332, dx_fric=0.000225, dy_fric=0.000225),
        "parent": 2
    },
    4: {
        "grid": dict(lon_ll_corner=360 - 81.72, lat_ll_corner=12.5, x_extent=0.055, y_extent=0.055, nx=243, ny=243),
        "bathy": dict(lon_ll_bat_corner=360 - 81.72, lat_ll_bat_corner=12.5, x_bot=243, y_bot=243, spacing_x=0.000225, spacing_y=0.000225),
        "wind": dict(lon_ll_wind=278, lat_ll_wind=12.3, meshes_x_wind=24, meshes_y_wind=24, dx_wind=0.025, dy_wind=0.025),
        "wl":   dict(lon_ll_wl=360 - 81.72, lat_ll_wl=12.5, meshes_x_wl=243, meshes_y_wl=243, dx_wl=0.000225, dy_wl=0.000225),
        "fric": dict(lon_ll_fric=360 - 81.72, lat_ll_fric=12.5, meshes_x_fric=243, meshes_y_fric=243, dx_fric=0.000225, dy_fric=0.000225),
        "parent": 2
    }
}

dict_parent_domains = {1:domains[1]["parent"],2:domains[2]["parent"],3:domains[3]["parent"],4:domains[4]["parent"]}

ini_date = datetime(2023,5,7,0)
end_date = datetime(2023,5,31,23)

lat_boundaries_dom01 = [12.40,12.50,12.60,12.70]
lon_boundaries_dom01 = [-81.80,-81.70,-81.60]

ini_case_data=dict(name=case_name,case_number=case_number,case_description=case_description,stat_id=0,
                    number_domains=number_domains,parent_domains=dict_parent_domains)

compilation_data = {
    1: {
        "ini_output_date":(ini_date+timedelta(days=5)).strftime('%Y%m%d.%H%M%S'),
        "output_res_min":60,
        "stat_comp":0,
        "ini_nest_date":(ini_date+timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
        "ini_comp_date":ini_date.strftime('%Y%m%d.%H%M%S'),
        "dt_min":10,
        "end_comp_date":end_date.strftime('%Y%m%d.%H%M%S')
    },
    2: {
        "ini_output_date":(ini_date+timedelta(days=5)).strftime('%Y%m%d.%H%M%S'),
        "output_res_min":60,
        "stat_comp":0,
        "ini_nest_date":(ini_date+timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
        "ini_comp_date":(ini_date+timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
        "dt_min":10,
        "end_comp_date":end_date.strftime('%Y%m%d.%H%M%S')
    },
    3: {
        "ini_output_date":(ini_date+timedelta(days=5)).strftime('%Y%m%d.%H%M%S'),
        "output_res_min":60,
        "stat_comp":0,
        "ini_comp_date":(ini_date+timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
        "dt_min":10,
        "end_comp_date":end_date.strftime('%Y%m%d.%H%M%S')
    },
    4: {
        "ini_output_date":(ini_date+timedelta(days=5)).strftime('%Y%m%d.%H%M%S'),
        "output_res_min":60,
        "stat_comp":0,
        "ini_comp_date":(ini_date+timedelta(days=2)).strftime('%Y%m%d.%H%M%S'),
        "dt_min":10,
        "end_comp_date":end_date.strftime('%Y%m%d.%H%M%S')
    }   
}

case = swanpy.Initializer(root_path=path_case,dict_ini_data=ini_case_data,ini_date=ini_date,end_date=end_date)
case.create_folders_l1()
case.create_folders_l2()
case.replace_ini_data()

if number_domains>=1:
    for domain_id,config in domains.items():
        
        domain_grid_dict = config["grid"]
        domain_bathy_dict = config["bathy"]
        domain_wind_dict = config["wind"]
        domain_wl_dict = config["wl"]
        domain_fric_dict = config["fric"]
        parent_domain = config["parent"]
        dict_comp_data_nonstat= compilation_data[domain_id]

        #--------- Grid information ------------#
        case_grid = swanpy.preprocess.GridMaker(init=case,domain_number=domain_id,grid_info=domain_grid_dict)
        dict_grid = case_grid.params_from_user()
        case_grid.fill_grid_section(dict_grid)

        #--------- Bathymetry information ------------#
        case_bathy = swanpy.preprocess.BathyMaker(init=case,domain_number=domain_id,bathy_info=domain_bathy_dict)
        dict_bathy = case_bathy.get_from_user()
        case_bathy.fill_bathy_section(dict_bathy)

        #--------- Winds information ------------#
        case_winds = swanpy.preprocess.WindForcing(init=case,domain_number=domain_id,wind_info=domain_wind_dict)
        case_winds.get_winds_from_CMDS(difference_to_UTC=-5)
        dict_winds = case_winds.write_CMDS_ascii('winds_cmds.nc','winds.wnd')
        case_winds.fill_wind_section(dict_winds)

        #--------- Water level information ------------#
        case_wl = swanpy.preprocess.WaterLevelForcing(init=case,domain_number=domain_id,wl_info=domain_wl_dict)
        case_wl.get_waterlevel_from_UHSLC(station_code=737)
        dict_wl = case_wl.write_UHSLC_ascii('h737.csv','water_levels.wl')
        case_wl.fill_wl_section(dict_wl)

        #--------- Friction information ------------#
        case_friction = swanpy.preprocess.BottomFrictionProcessor(init=case,domain_number=domain_id,friction_info=domain_fric_dict)
        dict_friction=case_friction.get_from_user()
        case_friction.fill_friction_section(dict_friction)

        #--------- Boundaries information ------------#
        case_bounds = swanpy.preprocess.BoundaryConditions(init=case,domain_number=domain_id,list_sides=['N','S','E','W'])
        case_bounds.get_waves_from_CMDS(difference_to_UTC=-5,wind_info_dict=domain_wind_dict)
        case_bounds.tpar_from_CMDS(points_lon=lon_boundaries_dom01,
                                   points_lat=lat_boundaries_dom01)
        case_bounds.fill_boundaries_section()

        #--------- Physics information ------------#
        case_physics = swanpy.preprocess.PhysicsMaker(init=case,domain_number=domain_id)
        dict_physics = case_physics.define_generation(cds1=6.3,delta=0.5)
        case_physics.fill_physics_section(dict_physics)

        #--------- Run section -----------------------#
        case_output = swanpy.execution.CaseRunner(init=case,domain_number=domain_id,dict_comp_data=dict_comp_data_nonstat,all_domains=domains)
        case_output.define_output_from_file('SalidasSWAN.txt')
        case_output.write_nest_section()
        case_output.fill_slurm_file()
        case_output.fill_computation_section()
else:
     print('Error: Number of domains must be greater than 0')