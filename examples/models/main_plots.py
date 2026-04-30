import numpy as np
import matplotlib.pyplot as plt
from oceanicospy.models import xbeachpy
from oceanicospy.plots import *
from oceanicospy.observations import RBR
import matplotlib as mp
from matplotlib.colors import TwoSlopeNorm
from matplotlib.animation import FuncAnimation
import os
import datetime as dt
import rasterio
import geopandas as gpd
from datetime import datetime, timedelta

mp.rcParams.update({'font.size': 12})

def save_figure(format,subfolder):
    def decorator(func):
        def wrapper(ds, variable_name, time_index, output_path, *args, **kwargs):
            fig, ax = func(ds, variable_name, time_index, output_path, *args, **kwargs)

            output_path = os.path.join(output_path, subfolder)
            os.makedirs(output_path, exist_ok=True)
            out_file = os.path.join(output_path, f"{variable_name}.{format}")
            fig.savefig(out_file, dpi=400, bbox_inches='tight')
            plt.close(fig)
        return wrapper
    return decorator

def add_sensor_locations(func):
    """
    Decorator to overlay points from ds_point onto the figure created by the plot_variable_contourf function.
    """
    def wrapper(ds, variable_name, time_index, output_path, *args, **kwargs):
        fig,ax = func(ds, variable_name, time_index, output_path, *args, **kwargs)
        points_x = ds_point['pointx'].values
        points_y = ds_point['pointy'].values
        x_offset = 1000 + 4050200
        y_offset = 1100 + 2956700
        ax.scatter(points_x+x_offset, points_y+y_offset, color='red', edgecolors='black', s=20, label='Sensors')
        ax.legend(loc='upper right')
        return fig, ax 
    return wrapper

@save_figure(format='png', subfolder='field')
@add_sensor_locations
def plot_variable_contourf(ds, variable_name, time_index, output_path, cmap='inferno_r', 
                           levels=20, extend=None,norm = None, add_geodata=False):
    """
    Create a contourf plot for a given variable from the dataset.

    Parameters:
    ds (xarray.Dataset): The dataset containing the variable.
    variable_name (str): The name of the variable to plot.
    time_index (int): The time index to use for the plot.
    output_path (str): The file path to save the plot.
    cmap (str): The colormap to use for the plot.
    """

    data = ds[variable_name].values[time_index,:,:]
    ini_date = dt.datetime(2025,5,9,4)
    time = np.array([ini_date + dt.timedelta(seconds=int(s)) for s in ds.globaltime.values])

    # Changing the long_name for specific variables
    if variable_name == 'H':
        ds[variable_name].attrs['long_name'] = 'Hrms'

    elif variable_name == 'zb0':
        ds[variable_name].attrs['long_name'] = 'Initial bed bevel'
        norm = TwoSlopeNorm(vmin=np.nanmin(data), vcenter=0, vmax=np.nanmax(data))
        extend = 'min'

    elif variable_name == 'u':
        ds[variable_name].attrs['long_name'] = 'U-Component Velocity'
        levels = np.arange(-1,1.05,0.05)
        extend = 'both'

    elif variable_name == 'v':
        ds[variable_name].attrs['long_name'] = 'V-Component Velocity'
        levels = np.arange(-1,1,0.05)
        extend = 'both'
    
    elif variable_name == 'zs':
        levels = np.arange(-1,1.05,0.05)
        extend = 'both'

    # Plotting        
    fig, ax = plt.subplots(figsize=(7, 7))
    x_offset = 1000 + 4050200
    y_offset = 1100 + 2956700
    c = ax.contourf(ds.globalx+x_offset, ds.globaly+y_offset, data, 
                    levels=levels, extend=extend,norm=norm, cmap=cmap)

    if add_geodata:
        # Adding satellite image as background
        with rasterio.open("geodata/GoogleSatellite.tiff") as src:
            img = src.read([1, 2, 3])  # RGB
            extent = src.bounds
        ax.imshow(img.transpose(1, 2, 0), extent=[extent.left, extent.right, extent.bottom, extent.top])

        # Adding coastline
        shp_path = "geodata/Shoreline_Paula_50m_MSON.shp"
        shoreline = gpd.read_file(shp_path)
        shoreline.plot(ax=ax, color='k')

    # Customizing colorbar and other details
    pos = ax.get_position()
    cax = fig.add_axes([pos.x1 + 0.02, pos.y0, 0.02, pos.height])  # x, y, width, height (in figure coords)
    fig.colorbar(c, cax=cax, 
                 label=f'{ds[variable_name].long_name} [{ds[variable_name].units}]')
    ax.set_title(f'{ds[variable_name].long_name} at {time[time_index]}', fontsize=14)
    ax.set(xlabel='Easting [m]', ylabel='Northing [m]')

    # Avoid scientific notation offset (e.g., "1e6") on both axes
    ax.ticklabel_format(useOffset=False, style='plain', axis='both')

    return fig, ax

def create_gif(ds, variable_name, output_path, cmap='inferno_r', levels=10, extend=None, norm=None, interval=200):
    """
    Create a GIF animation for a given variable from the dataset.

    Parameters:
    ds (xarray.Dataset): The dataset containing the variable.
    variable_name (str): The name of the variable to animate.
    output_path (str): The file path to save the GIF.
    cmap (str): The colormap to use for the animation.
    interval (int): Delay between frames in milliseconds.
    """

    data = ds[variable_name].values
    ini_date = dt.datetime(2025,5,9,4)
    time = np.array([ini_date + dt.timedelta(seconds=int(s)) for s in ds.globaltime.values])

    # Changing the long_name for specific variables
    if variable_name == 'H':
        ds[variable_name].attrs['long_name'] = 'Hrms'

    elif variable_name == 'zb0':
        ds[variable_name].attrs['long_name'] = 'Initial bed bevel'
        norm = TwoSlopeNorm(vmin=np.nanmin(data), vcenter=0, vmax=np.nanmax(data))
        extend = 'min'

    elif variable_name == 'u':
        ds[variable_name].attrs['long_name'] = 'U-Component Velocity'
        levels = np.arange(-1,1.05,0.05)
        extend = 'both'

    elif variable_name == 'v':
        ds[variable_name].attrs['long_name'] = 'V-Component Velocity'
        levels = np.arange(-1,1,0.05)
        extend = 'both'
    
    elif variable_name == 'zs':
        levels = np.arange(0,1.05,0.05)
        extend = 'both'

    output_path = os.path.join(output_path, 'GIFs')
    os.makedirs(output_path, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 7))
    x_offset = 1000 + 4050200
    y_offset = 1100 + 2956700
    c = ax.contourf(ds.globalx+x_offset, ds.globaly+y_offset, data[0,:,:], 
                    levels=levels, extend=extend,norm=norm, cmap=cmap)

    # adding points
    # points_x = ds_point['pointx'].values
    # points_y = ds_point['pointy'].values
    # ax.scatter(points_x, points_y, color='white',edgecolor='black', s=20, label='Sensors')
    # ax.legend(loc='upper right')

    # Customizing colorbar and other details
    pos = ax.get_position()
    cax = fig.add_axes([pos.x1 + 0.02, pos.y0, 0.02, pos.height])  # x, y, width, height (in figure coords)
    fig.colorbar(c, cax=cax, 
                 label=f'{ds[variable_name].long_name} [{ds[variable_name].units}]')
    ax.set_title(f'{ds[variable_name].long_name} at {time[0]}', fontsize=14)
    ax.set(xlabel='Easting [m]', ylabel='Northing [m]')

    # Avoid scientific notation offset (e.g., "1e6") on both axes
    ax.ticklabel_format(useOffset=False, style='plain', axis='both')

    def update(frame):
        nonlocal c
        for coll in c.collections:
            coll.remove()

        c = ax.contourf(ds.globalx+x_offset, ds.globaly+y_offset, data[frame,:,:], 
                        levels=levels, extend=extend,norm=norm, cmap=cmap)
    
        # adding points
        # points_x = ds_point['pointx'].values
        # points_y = ds_point['pointy'].values
        # ax.scatter(points_x, points_y, color='white',edgecolor='black', s=20, label='Sensors')
        # ax.legend(loc='upper right')

        ax.set_title(f'{ds[variable_name].long_name} at {time[frame]}', fontsize=14)
        ax.set(xlabel='Easting [m]', ylabel='Northing [m]')
        ax.ticklabel_format(useOffset=False, style='plain', axis='both')

        return c

    ani = FuncAnimation(fig, update, frames=100, interval=interval)
    ani.save(f'{output_path}/{variable_name}.gif', writer='Pillow', dpi=100)
    plt.close(fig)

def plot_time_series(ds,dict_time_records,dict_spectral_records,output_path,tide_series=None):
    """
    Plot time series for all point variables in the dataset.

    Parameters:
    ds (xarray.Dataset): The dataset containing point variables.
    output_path (str): The file path to save the plots.
    """
    point_vars = [var for var in ds.data_vars if ds[var].ndim == 2]

    output_path = os.path.join(output_path, 'time_series')
    os.makedirs(output_path, exist_ok=True)

    for var in point_vars:
        if var == 'point_H':
            ds[var].attrs['long_name'] = 'Hrms'

        elif var == 'point_zb0':
            ds[var].attrs['long_name'] = 'Initial bed bevel'

        elif var == 'point_u':
            ds[var].attrs['long_name'] = 'U-Component Velocity'

        elif var == 'point_v':
            ds[var].attrs['long_name'] = 'V-Component Velocity'

        ini_date = dt.datetime(2025,5,9,4)
    
        dict_point_names={'0':'RBR2','1':'RBR1 - AQ2','2':'AQ1'}

        fig, ax = plt.subplots(3,1,figsize=(10, 9),sharex=True)

        t = np.array([ini_date + dt.timedelta(seconds=int(s)) for s in ds.pointtime.values])

        for i in range(ds.sizes['points']):
            ax[i].plot(t, ds[var][:, i].values,color='darkorange', label='Modelled')

            if var == 'point_H':
                index_sensor = i
                ax[i].plot(dict_spectral_records[metadata_list[::-1][index_sensor]]['time'], 
                               dict_time_records[metadata_list[::-1][index_sensor]]['Hrms'],color='dimgray',label='Observed')
                if i == 1:
                    index_sensor = i + 1
                    ax[i].plot(dict_spectral_records[metadata_list[::-1][index_sensor]]['time'], 
                               dict_time_records[metadata_list[::-1][index_sensor]]['Hrms'],color='dimgray',ls='--',label='Observed')
                ylims = (0,1.5)
            elif 'point_zs' in var:
                if i == 0:
                    print(tide_series)
                    ax[i].plot(tide_series)
                ylims = (-0.2,1)
            else:
                ylims = (None,None)
            
            if i == 0: 
                ax[i].set_title(f'Time Series of {ds[var].long_name}', fontsize=16)
            if i == 2:
                ax[i].set_xlabel('Time', fontsize=14)

            ax[i].set(ylabel=f'{ds[var].long_name} [{ds[var].units}]',ylim=ylims)

            ax[i].text(0.98, 0.05, f'Sensor: {dict_point_names[str(i)]}', transform=ax[i].transAxes, fontsize=12, ha='right', va='bottom')
            ax[i].grid(True,alpha=0.4)
            ax[i].legend()
        plt.savefig(f'{output_path}/{var}_time_series.png', dpi=400, bbox_inches='tight')
    return fig, ax

# cmap_variables = {'zs':'RdYlBu_r','H':'inferno_r','hh':'Blues','zb0':'BrBG_r','u':'seismic','v':'seismic'}
cmap_variables = {'zs':'RdYlBu_r'}

processed_data_path = '/scratchsan/medellin/ffayalac/IG_analysis/data/processed/fft_welch'
metadata_list=['AQ1_May_2025_SB','AQ2_May_2025_SB','RBR1_May_2025_SB','RBR2_May_2025_SB']
dict_spectra = dict()
dict_integral_params = dict()

# -- Tide records ---- #
sampling_RBR2 = dict(anchoring_depth=1,sensor_height=0.2,sampling_freq=2,
                            start_time=datetime(2025,5,9,10,0,0),end_time=datetime(2025,5,19,18,0,0)-timedelta(minutes=1))

RBR_ = RBR('/scratchsan/medellin/ffayalac/IG_analysis/data/raw/RBR1/RBR1_SoundBay_ReefBall_Out_serial95/234695_20250520_1211/',
           sampling_RBR2)
RBR_raw_data = RBR_.get_raw_records()
RBR_clean_data = RBR_.get_clean_records()
RBR_clean_data['eta'] = RBR_clean_data['depth[m]']- RBR_clean_data['depth[m]'].mean()
tide_records = RBR_clean_data['eta'].resample('15T').mean()
# --- Tide records ---- #

spectrum_type = 'welch'

for id in metadata_list:
    spectra_data_path = f'{processed_data_path}/{id}_spectra_{spectrum_type}_wKp.npz'
    integral_params_data_path =  f'{processed_data_path}/{id}_params_{spectrum_type}_wKp.npz'
    dict_spectra[id] = np.load(spectra_data_path)
    dict_integral_params[id] = np.load(integral_params_data_path)

for id in [1,4]:
    output_reader = xbeachpy.postprocess.OutputReader(
        filepath=f'/scratchsan/medellin/ffayalac/IG_analysis/runs/SB_May2025_C{id}/output/SoundBay2D.nc')

    ds_field = output_reader.read_field_output()
    ds_point = output_reader.read_point_output()

    # for variable, cmap in cmap_variables.items():
    #     plot_variable_contourf(ds_field, variable, 
    #                            time_index=18, 
    #                            output_path=f'/scratchsan/medellin/ffayalac/IG_analysis/figures/runs_processing/SB_May2025_C{id}/', 
    #                            cmap=cmap,add_geodata=True)
        # if variable == 'zs':
        #     create_gif(ds_field, variable, output_path=f'/scratchsan/medellin/ffayalac/IG_analysis/figures/runs_processing/SB_May2025_C{id}/',extend='max')

    plot_time_series(ds_point,dict_integral_params,dict_spectra,
                        output_path=f'/scratchsan/medellin/ffayalac/IG_analysis/figures/model_runs/SB_May2025_C{id}/',
                        tide_series=tide_records)
