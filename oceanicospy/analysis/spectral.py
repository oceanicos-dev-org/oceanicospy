import logging
import numpy as np
import pandas as pd
import pywt
from scipy.signal import find_peaks,welch

from ..utils import wave_props,extras

class WaveSpectralAnalyzer():
    def __init__(self,measurement_signal,sampling_data,surface_level_column='eta[m]',logger=True):
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
        surface_level_column : str
            Column name in measurement_signal that contains the surface level data (default is 'eta[m]').
        logger : bool
            If True, initializes a logger for the class (default is True).

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

        Notes
        -----
        01-Oct-2025 : Origination - Franklin Ayala
        #TODO: adding history line for modules
        """

        self.measurement_signal = measurement_signal
        self.sampling_data = sampling_data
        self.sampling_freq = self.sampling_data['sampling_freq']
        self.anchoring_depth = self.sampling_data['anchoring_depth']
        self.sensor_height = self.sampling_data['sensor_height']
        self.burst_length_s = self.sampling_data['burst_length_s']
        self.surface_level_column = surface_level_column

        if logger:
            self.logfile = 'wave_spectral_analyzer.log'
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.setLevel(logging.INFO)

            if not self.logger.handlers:
                handler = logging.FileHandler(self.logfile)
                formatter = logging.Formatter(
                    "%(asctime)s - %(message)s"
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

    def _check_burst_length(self,burst_series):
        # Create a time index for each expected burst based on the sampling frequency and burst length
        burst_start_time = burst_series.index[0]
        burst_end_time = burst_series.index[-1]
        expected_times = pd.date_range(start=burst_start_time, end=burst_end_time, 
                                       freq=pd.Timedelta(seconds=1/self.sampling_data['sampling_freq']))

        # Find which expected times are missing in the burst
        missing_times = expected_times.difference(burst_series.index)
        if not missing_times.empty:
            raise ValueError(f"Missing timestamps in burst {burst_series}: {missing_times}")
        else:
            return None

    def _compute_spectrum_for_burst(self, burst_signal, method, kp_correction, window_type, window_length, smoothing_bins):
        # calculating the spectrum for the burst using the specified method and applying Kp correction if needed
        if not self._check_burst_length(burst_signal):
            burst_signal = burst_signal.values
            if method == 'fft':
                result = self.compute_spectrum_from_direct_fft(burst_signal, kp_correction)
            elif method == 'welch':
                # welch's method requires at least 2 segments, so we set the default overlap to 50% of the window length if not provided
                result = self.compute_spectrum_from_welch(burst_signal, kp_correction, window_type, window_length)
            else:
                raise ValueError(f"Unknown method: {method}. Use 'fft' or 'welch'.")

            if kp_correction:
                freqs, spectrum, _ = result  # (freqs, PSD_kp, PSD)
            else:
                freqs, spectrum = result  # (freqs, PSD)

            # If using Welch's method and smoothing_bins is provided, apply smoothing to the PSD
            if method == 'welch' and smoothing_bins is not None:
                spectrum = self._smooth_psd_spectrum(spectrum, smoothing_bins)
            return freqs, spectrum

    def _smooth_psd_spectrum(self,PSD,smoothing_bins):
        #Smooth the power spectral density (PSD) spectrum using a moving average filter.
        kernel = np.ones(smoothing_bins) / smoothing_bins
        PSD_smoothed = np.convolve(PSD, kernel, mode='same')
        return PSD_smoothed

    def _compute_nonadaptive_Kp(self,freqs):
        # Compute non-adaptive Kp correction factor based on linear wave theory
        total_depth = self.anchoring_depth + self.sensor_height
        L = np.array([wave_props.wavelength(1/f, total_depth) for f in freqs])
        k = 2*np.pi/L
        Kp = np.cosh(k * self.sensor_height) / np.cosh(k * total_depth)
        if freqs[0]==0:
            Kp[0] = 1

        Kp_min = (np.cosh(np.pi/(total_depth - self.sensor_height)*self.sensor_height)) / \
                (np.cosh(np.pi/(total_depth - self.sensor_height)*total_depth))
        Kp = np.clip(Kp, Kp_min, 1)
        return Kp
    
    def _compute_adaptive_Kp(self,freqs,PSD):
        # Compute adaptive Kp correction factor based on the spectrum shape
        total_depth = self.anchoring_depth + self.sensor_height
        L = np.array([wave_props.wavelength(1/f, total_depth) for f in freqs])
        k = 2*np.pi/L
        Kp = np.cosh(k * self.sensor_height) / np.cosh(k * total_depth)
        Kp_min = (np.cosh(np.pi/(total_depth - self.sensor_height)*self.sensor_height)) / \
                (np.cosh(np.pi/(total_depth - self.sensor_height)*total_depth))

        if freqs[0] == 0:
            Kp[0] = 1

        PSD_Kp = PSD / (Kp**2)
        PSD_Kp_smoothed = self._smooth_psd_spectrum(PSD_Kp,24)
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
        return Kp_final
    
    def correction_by_Kp(self,freqs,PSD,kp_method='adaptive'):
        """Apply Kp correction to the power spectral density (PSD) based on the specified method.
        
        Parameters
        ----------
        freqs : ndarray
            Frequency array corresponding to the PSD.
        PSD : ndarray
            Power spectral density to be corrected.
        kp_method : str, optional
            Method for Kp correction: 'adaptive' or 'nonadaptive'. Default is 'adaptive'
            
        Notes
        -----
        Based on https://doi.org/10.1016/j.cageo.2017.06.010
        """
        
        if kp_method == 'nonadaptive':
            Kp = self._compute_nonadaptive_Kp(freqs)
        else:
            Kp = self._compute_adaptive_Kp(freqs,PSD)
        PSD_Kp = PSD / (Kp**2)

        return freqs, PSD_Kp, PSD

    def _compute_hs_ig_band(self,PSD,freqs,freq_split):
        # Computes significant wave height in the infragravity and short-wave band.
        freq_upper_sw = 0.2
        freq_lower_ig = 0.
        ig_band_mask = (freqs >= freq_lower_ig) & (freqs <= freq_split)
        sw_band_mask = (freqs > freq_split) & (freqs <= freq_upper_sw)
        m0_ig = np.trapezoid(PSD[ig_band_mask], freqs[ig_band_mask])
        m0_sw = np.trapezoid(PSD[sw_band_mask], freqs[sw_band_mask])
        Hm0_ig = 4.004 * np.sqrt(m0_ig)
        Hm0_sw = 4.004 * np.sqrt(m0_sw)

        return Hm0_ig,Hm0_sw

    @extras.timing_decorator
    def _compute_wavelet_scalogram_for_burst(self,burst_signal,window_length,overlap,mother_wavelet,scales):
        """Compute wavelet scalogram for a single burst signal using overlapping windows.
        
        Parameters
        ----------
        burst_signal : ndarray
            The signal for which to compute the wavelet scalogram.
        window_length : int
            The length of each window.
        overlap : float
            The overlap between consecutive windows.
        mother_wavelet : str
            The mother wavelet to use.
        scales : ndarray
            The scales for the wavelet transform.

        Returns
        -------
        stitched : ndarray
            The stitched wavelet scalogram.
        freqs : ndarray
            The corresponding frequencies.

        Notes
        -----
        10-Dec-2025 : Origination - Franklin Ayala
        """

        step = int(window_length * (1 - overlap))
        if len(burst_signal)==window_length:
            n_segments =1
        else:
            n_segments = (len(burst_signal) - window_length) // step + 1
        window = np.hanning(window_length)

        stitched = np.zeros((len(scales), len(burst_signal)))
        weight = np.zeros(len(burst_signal))

        for idx_seg in range(n_segments):
            start = idx_seg * step
            end = start + window_length
            segment = burst_signal[start:end]
            coef, freqs = pywt.cwt(segment, scales, mother_wavelet, sampling_period=1/self.sampling_freq)
            coef_mag = np.abs(coef) * window  # Apply window to smooth overlap
            stitched[:, start:end] += coef_mag
            weight[start:end] += window

        stitched /= np.maximum(weight, 1e-8)
        return stitched,freqs

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

        m0 = np.trapezoid(PSD, freqs.flatten())
        m1 = np.trapezoid(freqs.flatten()*PSD, freqs.flatten())
        m2 = np.trapezoid((freqs.flatten()**2)*PSD, freqs.flatten())

        Hs = 4.004*np.sqrt(m0)
        Hrms = np.sqrt(8*m0)
        Hmean = np.sqrt(2*np.pi*m0)

        Tp = 1/freqs[np.argmax(PSD)]
        Tm01 = m0/m1
        Tm02 = np.sqrt(m0/m2)

        return Hs,Hrms,Hmean,Tp,Tm01,Tm02

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
        10-Dec-2025 : Refactorization - Franklin Ayala
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

        Notes
        -----
        10-Dec-2025 : Origination - Franklin Ayala
        """

        freqs, PSD = welch(x=signal,fs=self.sampling_freq,window=window_type,
                            nperseg=window_length,
                            noverlap=overlap,
                            scaling='density')
                
        if kp_correction == False:
            return freqs,PSD
        else:
            return self._correction_by_Kp(freqs,PSD)

    def get_spectra_and_params_for_bursts(self, method, kp_correction=True, ig_split=False, freq_split=None, 
                                          window_type=None, window_length=None, overlap=None, smoothing_bins=None):
        """
        Compute wave spectra and integral parameters for each burst in the measurement signal.

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
        
        wave_params_data = {param: np.zeros(len(hourly_timeindex)) for param in wave_param_names}
        wave_spectra_data = {"S": [], "dir": [], "freq": None, "time": hourly_timeindex}
        wave_params_data["time"] = hourly_timeindex

        for idx, burst_id in enumerate(self.measurement_signal["burstId"].unique()):
            burst_series = self.measurement_signal[self.measurement_signal["burstId"] == burst_id]
            burst_signal = burst_series[self.surface_level_column]

            freqs, spectrum = self._compute_spectrum_for_burst(burst_signal, method, 
                                                               kp_correction, window_type, 
                                                               window_length, smoothing_bins)

            wave_spectra_data["S"].append(spectrum)

            # Compute wave parameters
            wave_params = self.get_wave_params_from_spectrum(spectrum, freqs)
            for param_idx, param_name in enumerate(wave_param_names):
                wave_params_data[param_name][idx] = wave_params[param_idx]

            if ig_split:
                Hm0_ig, Hm0_sw = self._compute_hs_ig_band(spectrum, freqs, freq_split)
                wave_params_data["Hm0_ig"] = wave_params_data.get("Hm0_ig", np.zeros(len(hourly_timeindex)))
                wave_params_data["Hm0_sw"] = wave_params_data.get("Hm0_sw", np.zeros(len(hourly_timeindex)))
                wave_params_data["Hm0_ig"][idx] = Hm0_ig
                wave_params_data["Hm0_sw"][idx] = Hm0_sw
                
            if idx == 0:
                wave_spectra_data["freq"] = freqs

        wave_spectra_data["S"] = np.array(wave_spectra_data["S"])

        return wave_spectra_data, wave_params_data

    def compute_wavelet_scalograms_for_bursts(self,window_length,overlap,mother_wavelet,points_scale):
        """Compute wavelet scalograms for all bursts in the measurement signal.
        
        Parameters
        ----------
        window_length : int
            The length of each window.
        overlap : float
            The overlap between consecutive windows.
        mother_wavelet : str
            The mother wavelet to use.
        points_scale : int
            The number of scales to compute.

        Returns
        -------
        coefs_all : ndarray
            The computed wavelet scalograms for all bursts.
        freqs : ndarray
            The corresponding frequencies.
        """
        hourly_timeindex = self.measurement_signal.index.floor('h').unique().sort_values()
        frequencies = np.logspace(np.log10(0.001), np.log10(self.sampling_freq/2), points_scale)
        # scales = np.arange(self.sampling_freq*0.5, maximum_scale, 20*int(self.sampling_freq))
        f_c = pywt.central_frequency(mother_wavelet)
        dt = 1 / self.sampling_freq
        scales = f_c / (frequencies * dt)

        # scale = np.arange(self.sampling_freq*0.5,maximum_scale,20*int(self.sampling_freq))
        coefs_all = np.zeros((len(hourly_timeindex),len(scales),self.burst_length_s))

        if 'burstId' in self.measurement_signal.columns:
            for idx,burst in enumerate(self.measurement_signal["burstId"].unique()):
                burst_series = self.measurement_signal[self.measurement_signal['burstId'] == burst]
                coefs,freqs = self._compute_wavelet_scalogram_for_burst(burst_series[self.surface_level_column].values,window_length,overlap,
                                                                            mother_wavelet,scales)
                coefs_all[idx,:,:] = coefs
        return coefs_all,freqs

    @extras.timing_decorator
    def compute_wavelet_scalogram(self,mother_wavelet,points_scale):
        """Compute wavelet scalogram for the entire measurement signal without windowing.
        
        Parameters
        ----------
        mother_wavelet : str
            The mother wavelet to use.
        points_scale : int
            The number of scales to compute.
        
        Returns
        -------
        coefs_mag : ndarray
            The magnitude of the computed wavelet coefficients.
        freqs : ndarray
            The corresponding frequencies.
        """

        frequencies = np.logspace(np.log10(0.001), np.log10(self.sampling_freq/2), points_scale)
        f_c = pywt.central_frequency(mother_wavelet)
        dt = 1 / self.sampling_freq
        scales = f_c / (frequencies * dt)       
        coeffs, freqs = pywt.cwt(self.measurement_signal[self.surface_level_column].values,scales,
                                 wavelet=mother_wavelet, sampling_period=1/self.sampling_freq)
        coeffs_mag = np.abs(coeffs)
        return coeffs_mag,freqs

