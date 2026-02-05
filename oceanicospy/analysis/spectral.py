import numpy as np
import pandas as pd

from ..utils import wave_props,constants,extras
from scipy.signal import welch
from PyEMD import EMD,EEMD,CEEMDAN
import pywt
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

class WaveSpectralAnalyzer():
    def __init__(self,measurement_signal,sampling_data):
        """
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
        Attributes
        ----------
        measurement_signal : array-like
            Stores the input measurement signal.
        sampling_data : dict
            Stores the sampling parameters.
        sampling_freq : float
            Sampling frequency extracted from sampling_data.
        anchoring_depth : float
            Anchoring depth extracted from sampling_data.
        sensor_height : float
            Sensor height extracted from sampling_data.
        burst_length_s : float
            Burst length in seconds extracted from sampling_data.
        """

        self.measurement_signal = measurement_signal
        self.sampling_data = sampling_data
        self.sampling_freq = self.sampling_data['sampling_freq']
        self.anchoring_depth = self.sampling_data['anchoring_depth']
        self.sensor_height = self.sampling_data['sensor_height']
        self.burst_length_s = self.sampling_data['burst_length_s']

    def _smooth_psd_spectrum(self,PSD,smoothing_bins):
        """Smooth the power spectral density (PSD) spectrum using a moving average filter."""
        kernel = np.ones(smoothing_bins) / smoothing_bins
        PSD_smoothed = np.convolve(PSD, kernel, mode='same')
        return PSD_smoothed
    
    def _compute_spectrum_for_burst(self, burst_signal, method, kp_correction, window_type, window_length, smoothing_bins):
        """
        Compute spectrum for a single burst signal using specified method.

        Parameters
        ----------
        burst_signal : ndarray
            Signal values for a single burst.
        method : str
            'fft' or 'welch'.
        kp_correction : bool
            Whether to apply Kp correction.
        window_type : str, optional
            Window type for Welch method.
        window_length : int, optional
            Window length for Welch method.
        smoothing_bins : int, optional
            Number of bins for smoothing (Welch only).

        Returns
        -------
        freqs : ndarray
            Frequency array.
        spectrum : ndarray
            Computed spectrum (Kp-corrected if kp_correction=True, else raw).
        """
        if method == 'fft':
            result = self.compute_spectrum_from_direct_fft(burst_signal, kp_correction)
        elif method == 'welch':
            result = self.compute_spectrum_from_welch(burst_signal, kp_correction, window_type, window_length)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'fft' or 'welch'.")

        # Unpack result based on kp_correction
        if kp_correction:
            freqs, spectrum, _ = result  # (freqs, PSD_kp, PSD)
        else:
            freqs, spectrum = result  # (freqs, PSD)

        # Apply smoothing for Welch method
        if method == 'welch' and smoothing_bins is not None:
            spectrum = self._smooth_psd_spectrum(spectrum, smoothing_bins)

        return freqs, spectrum

    def get_wave_params_from_spectrum(self,PSD,freqs):
        """
        This function computes different wave integral parameters from the spectrum
        
        Parameters
        ----------
        PSD : list or ndarray
            Density variance spectrum
        freqs : list or ndarray
            Frequencies of the spectrum
        
        Returns
        -------
        Hs : float
            Significant wave heigth [m]
        Hrms : float
            Root-mean squared wave heigth [m]
        Hmean : float
            Mean wave heigth [m]
        Tp : float
            Peak period [s]
        Tm01 : float
            Mean period - fisrt order [s]
        Tm02 : float
            Mean period - second order [s]
        
        Notes
        -----
        10-Dec-2024 : Origination - Franklin Ayala

        """

        m0 = np.trapz(PSD, freqs.flatten())
        m1 = np.trapz(freqs.flatten()*PSD, freqs.flatten())
        m2 = np.trapz((freqs.flatten()**2)*PSD, freqs.flatten())

        i0 = np.trapz(np.abs(PSD)**4, freqs.flatten())
        i1 = np.trapz(freqs.flatten() * np.abs(PSD)**4, freqs.flatten())

        Hs = 4.004*np.sqrt(m0)
        Hrms = np.sqrt(8*m0)
        Hmean = np.sqrt(2*np.pi*m0)

        # Tp = i0/i1
        Tp = 1/freqs[np.argmax(PSD)]
        Tm01 = m0/m1
        Tm02 = np.sqrt(m0/m2)

        return Hs,Hrms,Hmean,Tp,Tm01,Tm02

    def _compute_hs_ig_band(self,PSD,freqs,freq_split):
        """
        Computes significant wave height in the infragravity band.

        Parameters
        ----------
        PSD : ndarray
            Power spectral density.
        freqs : ndarray
            Frequency array.
        freq_split : float
            Frequency that separates infragravity from wind waves.

        Returns
        -------
        Hs_ig : float
            Significant wave height in the infragravity band [m].
        Hs_sw : float
            Significant wave height in the short wave band [m].
        """
        ig_band_mask = freqs < freq_split
        sw_band_mask = ~ig_band_mask
        m0_ig = np.trapz(PSD[ig_band_mask], freqs[ig_band_mask])
        m0_sw = np.trapz(PSD[sw_band_mask], freqs[sw_band_mask])
        Hm0_ig = 4.004 * np.sqrt(m0_ig)
        Hm0_sw = 4.004 * np.sqrt(m0_sw)
        return Hm0_ig,Hm0_sw

    @extras.timing_decorator
    def compute_spectrum_from_direct_fft(self,signal,kp_correction):
        """
        Computes the density variance spectrum based on the Fast Fourier transform. 
        
        Parameters
        ----------
        signal : list or ndarray
            An array of the signal
        kp_correction : bool
            If True, applies Kp correction to the spectrum.
        sampling_freq : float
            Sampling frequency for the records    
        anchoring_depth : float
            Depth at where the device was settled on the bottom.
        sensor_height: float
            Distance from the sensor to the bottom.        
        
        Returns
        -------
        freqs: ndarray
            Frequency of the spectrum
        PSD : ndarray
            Density variance spectrum    
        PSD_kp : ndarray (optional)
            Density variance spectrum corrected by Kp    

        Notes
        -----
        Based on https://currents.soest.hawaii.edu/ocn_data_analysis/_static/Spectrum.html

        01-Sep-2023 : Origination - Juan Diego Toro

        """
        length_signal = len(signal)
        freqs = np.fft.rfftfreq(length_signal,1/self.sampling_freq)
        fourier = np.fft.rfft(signal)

        # Compute power spectrum: contribution of each frequency to the total variance in the time series (Parseval's theorem)
        amplitude = np.abs(fourier)
        power_spectrum_raw = (amplitude**2)*2
        power_spectrum_norm =  power_spectrum_raw/(length_signal**2) # power per bin

        # Compute the power spectral density (PSD)
        PSD = power_spectrum_norm * length_signal * (1/self.sampling_freq) # power per Hz

        if kp_correction == False:
            return freqs,PSD
        else:
            return self._correction_by_Kp(freqs,PSD)

    @extras.timing_decorator
    def compute_spectrum_from_welch(self,signal,kp_correction,window_type,window_length,overlap=None):
        """
        Compute PSD using Welch method and smooth across frequency bins.

        Parameters
        ----------
        signal : ndarray
            1D numpy array containing the signal.
        kp_correction : bool
            If True, applies Kp correction to the spectrum.
        window_type : str, optional
            Type of window to use (default is 'hamming').
            Can be any window name supported by scipy.signal.windows, e.g., 
            'hann', 'blackman', 'boxcar', etc.
        window_length : int
            Length of the Hamming window in samples.
        overlap: int, optional
            Number of overlapping samples between segments (default is half of window_length).

        Returns
        -------
        freqs : ndarray
            Frequency array.
        PSD : ndarray
            Power spectral density.
        PSD_kp : ndarray (optional)
            Density variance spectrum corrected by Kp
        """

        # Welch PSD
        freqs, PSD = welch(x=signal,fs=self.sampling_freq,window=window_type,
                            nperseg=window_length,
                            noverlap=overlap,
                            scaling='density')
        
        # Estimate degrees of freedom:
        # DOF ≈ (2 × number of segments) × (effective freq bins averaged / total bins)
        # n_segments = 1 + (len(signal) - window_length) // (window_length - overlap)
        # dof = 2 * n_segments * (1 / smoothing_bins)
        
        if kp_correction == False:
            return freqs,PSD
        else:
            return self._correction_by_Kp(freqs,PSD)

    def get_spectra_and_params_for_bursts(self, method, kp_correction=True, ig_split=False, freq_split=None, window_type=None, window_length=None, overlap=None, smoothing_bins=None):
        """
        Compute wave spectra and parameters for each burst in the measurement signal.

        Parameters
        ----------
        method : str
            Spectrum computation method: 'fft' or 'welch'.
        kp_correction : bool, optional
            Whether to apply Kp pressure correction. Default is True.
        ig_split : bool, optional
            Whether to compute infragravity and wind wave Hm0 separately. Default is False.
        freq_split : float, optional
            Frequency that separates infragravity from short waves (required if ig_split is True). Default is None.
        window_type : str, optional
            Window type for Welch method (e.g., 'hamming', 'hann'). Default is None.
        window_length : int, optional
            Window length for Welch method in samples. Default is None.
        overlap : int, optional
            Number of overlapping samples for Welch method. Default is None.
        smoothing_bins : int, optional
            Number of bins for moving-average smoothing (Welch only). Default is None.

        Returns
        -------
        wave_spectra_data : dict
            Dictionary with keys:
            - 'S': ndarray of shape (n_bursts, n_freqs) containing power spectral densities.
            - 'freq': ndarray of frequency values.
            - 'dir': empty list (placeholder for directional info).
            - 'time': DatetimeIndex of hourly timestamps.
        wave_params_data : pd.DataFrame
            Wave parameters indexed by time, with columns:
            - 'Hm0': Zero-moment wave height [m].
            - 'Hrms': Root-mean-square wave height [m].
            - 'Hmean': Mean wave height [m].
            - 'Tp': Peak period [s].
            - 'Tm01': Mean period (first moment) [s].
            - 'Tm02': Mean period (second moment) [s].
            - 'Hm0_ig': Infragravity wave height [m] (if ig_split is True).
            - 'Hm0_sw': Short wave height [m] (if ig_split is True).
        """
        if 'burstId' not in self.measurement_signal.columns:
            raise ValueError("Measurement signal must contain 'burstId' column.")

        hourly_timeindex = self.measurement_signal.index.floor('h').unique().sort_values()
        wave_param_names = ["Hm0", "Hrms", "Hmean", "Tp", "Tm01", "Tm02"]
        
        # Initialize data structures
        wave_params_data = {param: np.zeros(len(hourly_timeindex)) for param in wave_param_names}
        wave_spectra_data = {"S": [], "dir": [], "freq": None, "time": hourly_timeindex}
        wave_params_data["time"] = hourly_timeindex

        # Process each burst
        for idx, burst_id in enumerate(self.measurement_signal["burstId"].unique()):
            burst_series = self.measurement_signal[self.measurement_signal["burstId"] == burst_id]
            burst_signal = burst_series["eta[m]"].values

            # Compute spectrum
            freqs, spectrum = self._compute_spectrum_for_burst(
                burst_signal, method, kp_correction, window_type, window_length, smoothing_bins
            )

            wave_spectra_data["S"].append(spectrum)

            # Compute wave parameters
            wave_params = self.get_wave_params_from_spectrum(spectrum, freqs)
            for param_idx, param_name in enumerate(wave_param_names):
                wave_params_data[param_name][idx] = wave_params[param_idx]

            print(ig_split)
            if ig_split:
                Hm0_ig, Hm0_sw = self._compute_hs_ig_band(spectrum, freqs, freq_split)
                wave_params_data["Hm0_ig"] = wave_params_data.get("Hm0_ig", np.zeros(len(hourly_timeindex)))
                wave_params_data["Hm0_sw"] = wave_params_data.get("Hm0_sw", np.zeros(len(hourly_timeindex)))
                wave_params_data["Hm0_ig"][idx] = Hm0_ig
                wave_params_data["Hm0_sw"][idx] = Hm0_sw
                print(f"Burst {burst_id}: Hm0_ig={Hm0_ig:.2f} m, Hm0_sw={Hm0_sw:.2f} m" )
                
            if idx == 0:
                wave_spectra_data["freq"] = freqs

        # Finalize data structures
        wave_spectra_data["S"] = np.array(wave_spectra_data["S"])

        return wave_spectra_data, wave_params_data

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

#     def compute_wavelet_scalogram(self,signal,mother_wavelet,maximum_scale):
#         coefficients, frequencies = pywt.cwt(signal, scales, mother_wavelet, sampling_period=1/self.sampling_freq)
#         return coefficients,frequencies

#     def compute_wavelet_scalogram_windowed(self,signal,window_length,overlap,mother_wavelet,maximum_scale):
#         step = int(window_length * (1 - overlap))
#         if len(signal)==window_length:
#             n_segments =1
#         else:
#             n_segments = (len(signal) - window_length) // step + 1
#         window = np.hanning(window_length)

#         scales = np.arange(1, maximum_scale, 20)
#         stitched = np.zeros((len(scales), len(signal)))
#         weight = np.zeros(len(signal))

#         for idx_seg in range(n_segments):
#             start = idx_seg * step
#             end = start + window_length
#             segment = signal[start:end]
#             coef, freqs = pywt.cwt(segment, scales, mother_wavelet, sampling_period=1/self.sampling_freq)
#             coef_mag = np.abs(coef) * window  # Apply window to smooth overlap
#             stitched[:, start:end] += coef_mag
#             weight[start:end] += window

#         stitched /= np.maximum(weight, 1e-8)
#         return stitched,freqs

#     def compute_all_wavelet_scalograms(self,window_length,overlap,mother_wavelet,maximum_scale):
#         hourly_timeindex = self.measurement_signal.index.floor('h').unique().sort_values()
#         scale = np.arange(1,maximum_scale,20)
#         coefs_all = np.zeros((len(hourly_timeindex),len(scale),self.burst_length_s))

#         if 'burstId' in self.measurement_signal.columns:
#             for idx,burst in enumerate(self.measurement_signal["burstId"].unique()):
#                 burst_series = self.measurement_signal[self.measurement_signal['burstId'] == burst]
#                 coefs,freqs = self.compute_wavelet_scalogram_windowed(burst_series['eta[m]'].values,window_length,overlap,
#                                                                             mother_wavelet,maximum_scale)
#                 coefs_all[idx,:,:] = coefs
#         return coefs_all,freqs

    def _compute_nonadaptive_Kp(self,freqs):
        total_depth = self.anchoring_depth + self.sensor_height
        L = np.array([wave_props.wavelength(1/f, total_depth) for f in freqs])
        k = 2*np.pi/L
        Kp = np.cosh(k * self.sensor_height) / np.cosh(k * total_depth)
        if freqs[0]==0:
            Kp[0] = 1

        Kp_min = (np.cosh(np.pi/(total_depth - self.sensor_height)*self.sensor_height)) / \
                (np.cosh(np.pi/(total_depth - self.sensor_height)*total_depth))
        Kp = np.clip(Kp, Kp_min, 1)

        # fmax_Kp = 1/(2*np.pi)*np.sqrt(9.8*(np.pi/(total_depth - self.sensor_height))*np.tanh(np.pi/(total_depth-self.sensor_height)*total_depth))
        # freqs_to_modify = freqs <= fmax_Kp

        return Kp
    
    def _compute_adaptive_Kp(self,freqs,PSD):
        total_depth = self.anchoring_depth + self.sensor_height
        L = np.array([wave_props.wavelength(1/f, total_depth) for f in freqs])
        k = 2*np.pi/L
        Kp = np.cosh(k * self.sensor_height) / np.cosh(k * total_depth)
        Kp_min = (np.cosh(np.pi/(total_depth - self.sensor_height)*self.sensor_height)) / \
                (np.cosh(np.pi/(total_depth - self.sensor_height)*total_depth))

        if freqs[0] == 0:
            Kp[0] = 1

        PSD_Kp = PSD / (Kp**2)
        PSD_Kp_smoothed = self.smooth_psd_spectrum(PSD_Kp,24)
        minima_idx, _ = find_peaks(-np.log(PSD_Kp_smoothed),prominence=0.5)
        last_min_idx = minima_idx[-1]
        f_maxpcorr = freqs[last_min_idx]

        # Assuming f_maxpcorr is always lower than fcmax and fmax_Kp
        total_depth = self.anchoring_depth + self.sensor_height
        L_max = wave_props.wavelength(1/f_maxpcorr, total_depth)
        k_max = 2*np.pi/L_max
        Kp_min = np.cosh(k_max * self.sensor_height) / np.cosh(k_max * total_depth)

        Kp_final = Kp.copy()
        Kp_final[0:last_min_idx] =  Kp[0:last_min_idx]
        Kp_final[last_min_idx:] = Kp_min

        # plt.figure()
        # plt.loglog(freqs, PSD_Kp_smoothed, label='corrected')
        # plt.axvline(freqs[last_min_idx])
        # plt.savefig('/scratchsan/medellin/ffayalac/IG_analysis/src/field_analysis/plot_one_spectra.png')
        return Kp_final
    
    def _correction_by_Kp(self,freqs,PSD,kp_method='adaptive'):
        "Based on https://doi.org/10.1016/j.cageo.2017.06.010"
        if kp_method == 'nonadaptive':
            Kp = self._compute_nonadaptive_Kp(freqs)
        else:
            Kp = self._compute_adaptive_Kp(freqs,PSD)
        PSD_Kp = PSD / (Kp**2)

        return freqs, PSD_Kp, PSD
    

    # def _check_burst_length(self,burst_series):
    #     # Create a time index for each expected burst based on the sampling frequency and burst length
    #     burst_start_time = burst_series.index[0]
    #     burst_end_time = burst_series.index[-1]
    #     expected_times = pd.date_range(start=burst_start_time, end=burst_end_time, freq=pd.Timedelta(seconds=1/self.sampling_data['sampling_freq']))

    #     # Find which expected times are missing in the burst
    #     missing_times = expected_times.difference(burst_series.index)
    #     if not missing_times.empty:
    #         print(f"Missing timestamps in burst {hourly_timeindex[idx]}: {missing_times}")

