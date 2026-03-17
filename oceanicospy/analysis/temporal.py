import numpy as np
import pandas as pd
from PyEMD import CEEMDAN,EEMD,EMD
from scipy.signal import resample,detrend

from ..utils import wave_props

class WaveTemporalAnalyzer:
    def __init__(self,measured_signal,sampling_data,surface_level_column='eta[m]'): 
        """"
        Initializes the analysis object with measurement signal and sampling data.

        Parameters
        ----------
        measurement_signal : array-like
            The input signal data to be analyzed.
        sampling_data : dict
            Dictionary containing sampling parameters with the following keys:
                - 'sampling_freq' (float): Sampling frequency of the signal.
                - 'anchoring_depth' (float): Depth at which the sensor is anchored.
                - 'sensor_height' (float): Height of the sensor above the bottom.
                - 'burst_length_s' (float): Duration of each burst in seconds.
        surface_level_column : str, optional
            The name of the column in measurement_signal that contains surface level data (default is 'eta[m]').

        Notes
        -----

        23-Feb-2014 : First Matlab version - Daniel Peláez
        01-Sep-2023 : First Python version - Alejandro Henao
        10-Dec-2024 : Polishing            - Franklin Ayala 

        """
        self.measured_signal = measured_signal
        self.sampling_data = sampling_data
        self.surface_level_column = surface_level_column

    def compute_params_from_zero_upcrossing(self):
        """
        Calculate wave parameters from zero-crossing analysis of pressure data.


        Returns
        -------
        pandas.DataFrame
            DataFrame with wave parameters indexed by time, containing columns:
            - 'H1/3': Significant wave height (H1/3).
            - 'Tmean': Mean wave period (Tmean).
        """
        wave_params=["time","H1/3","Tmean"]
        wave_params_data={param:[] for param in wave_params}

        for i in self.measured_signal['burstId'].unique()[:2]:
            burst_signal = self.measured_signal[self.measured_signal['burstId'] == i]

            # TODO: validate this step, detrend option is already given in the observations. What if the data is coming from another source?
            burst_signal_detrended = burst_signal.iloc[:,:-1].apply(lambda x: detrend(x,type='constant'), axis=0)
            burst_signal_detrended[self.measured_signal.columns[-1]] = burst_signal.iloc[:, -1]
            print(burst_signal_detrended)

            H_top_third, Hmax, Tmean, Lmean = self.apply_zero_upcrossing_burst(burst_signal_detrended['pressure[bar]'], self.sampling_data['sampling_freq'],
                                    self.sampling_data['anchoring_depth'], self.sampling_data['sensor_height'])

            wave_params_data['time'].append(burst_signal_detrended.index[0])
            wave_params_data['H1/3'].append(H_top_third)
            wave_params_data['Tmean'].append(Tmean)
            print(wave_params_data['time'])

        wave_params_data=pd.DataFrame(wave_params_data).set_index('time')

        return wave_params_data

    def apply_zero_upcrossing_burst(self, burst_signal, sampling_freq, anchoring_depth, sensor_height):
        """
        This function calculates the significant wave height, the period and the wavelength
        with the zero-crossing method.
        
        Parameters
        ----------
        burst_signal : array_like
            A series of data without trend.
        sampling_freq : float
            The sampling frequency.
        anchoring_depth : float
            The measurement depth.
        sensor_height : float
            The distance from the bottom to the sensor.

        Returns
        -------
        H_top_third : float
            The significant wave height (top third).
        Hmax : float
            The maximum wave height.
        Tmean : float
            The mean period.
        Lmean : float
            The mean wavelength.
        """

        # tt = np.arange(1,len(burst_signal)+1,1/sampling_freq)
        ratio = 10
        # Resample the signal with certain ratio to increase the resolution of zero-crossing detection
        burst_signal_upsampled = resample(burst_signal, len(burst_signal) * ratio)
        time = np.linspace(1, len(burst_signal), len(burst_signal_upsampled)) 
        sign = np.sign(burst_signal_upsampled)
        idxs_cross = np.where(np.diff(sign) > 0)[0] # indices of zero-crossings (up-crossings)

        H_cross = []
        T = []

        # Loop through pairs of consecutive up-crossings to calculate wave heights and periods
        for idx_cross in range(0,len(idxs_cross)-1):
            first_up = idxs_cross[idx_cross] 
            second_up = idxs_cross[idx_cross+1]
            wave = burst_signal_upsampled[first_up:second_up+1]
            H_cross.append(np.max(wave) - np.min(wave))
            T.append(time[second_up] - time[first_up])
        H_cross = np.array(H_cross)
        T = np.array(T)

        # Determine the wavenumber based on the dispersion relation
        L = np.array([wave_props.wavelength(t, anchoring_depth) for t in T], dtype=np.float64) # total or anchoring_depth?
        k = 2.*np.pi/L

        # computing non-adaptive transference factor Kp
        Kp = np.cosh(k * sensor_height) / np.cosh(k * anchoring_depth) # total or anchoring_depth?
        Kp_min = (np.cosh(np.pi/(anchoring_depth - sensor_height)*sensor_height)) / \
                (np.cosh(np.pi/(anchoring_depth - sensor_height)*anchoring_depth)) # total or anchoring_depth?
        # Clip Kp to avoid unrealistic amplification of wave heights for very long waves
        Kp = np.clip(Kp, Kp_min, 1)

        H = H_cross/(Kp)
        n = len(H) // 3 

        H_sorted = np.sort(H)
        H_top_third = np.nanmean(H_sorted[-n:])  # top third
        Hmax = H_sorted[-1]
        Tmean = np.nanmean(T)
        Lmean= np.nanmean(L)

        return H_top_third,Hmax,Tmean,Lmean

#     def decompose_into_IMFs_for_bursts(self,emd_type,maximum_IMFs,number_ensembles=None,amplitude_noise_std=None):
#         hourly_timeindex = self.measurement_signal.index.floor('h').unique().sort_values()
#         time_seconds = np.arange(0,self.burst_length_s,1)

#         IMFs_all = np.zeros((len(hourly_timeindex),maximum_IMFs,self.burst_length_s))

#         if 'burstId' in self.measurement_signal.columns:
#             for idx,burst in enumerate(self.measurement_signal["burstId"].unique()):
#                 burst_series = self.measurement_signal[self.measurement_signal['burstId'] == burst]
#                 if emd_type == 'EMD':
#                     emd = EMD()
#                     IMFs = emd(burst_series['eta[m]'].values, time_seconds, max_imf=maximum_IMFs)[:maximum_IMFs, :]
#                 elif emd_type == 'EEMD':
#                     eemd = EEMD(trials=number_ensembles, epsilon=amplitude_noise_std)
#                     IMFs = eemd(burst_series['eta[m]'].values, time_seconds, max_imf=maximum_IMFs)[:maximum_IMFs, :]
#                 else:
#                     ceemd = CEEMDAN(DTYPE=np.float16,trials=number_ensembles,epsilon=amplitude_noise_std,parallel=True,processes=48)
#                     IMFs = ceemd(burst_series['eta[m]'].values,time_seconds,max_imf=maximum_IMFs)[:maximum_IMFs,:]
#                 IMFs_all[idx,:,:] = IMFs
#         return IMFs_all

