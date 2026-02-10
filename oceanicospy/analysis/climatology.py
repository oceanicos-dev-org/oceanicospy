import numpy as np
import pandas as pd

def compute_annual_cycle(data, time):
    """
    Compute the annual cycle of a given time series data.

    Parameters
    ----------
    data : numpy.ndarray or pandas.Series
        The input time series data. Must be a 1D array or Series.
    time : array-like
        The corresponding time values for the data. Must be convertible to datetime.
        
    Returns
    -------
    numpy.ndarray
        The computed annual cycle, with the mean values for each month.
        
    Raises
    ------
    ValueError
        If the input data is not a 1D numpy array or a pandas Series.
    """
    if data.ndim == 1:
        if isinstance(data, pd.Series):
            dataset = pd.DataFrame(data, columns=['data'], index=time)
        else:
            time_index = pd.to_datetime(time)
            dataset = pd.DataFrame(data, columns=['data'], index=time_index)
        
        dataset['month'] = dataset.index.month
        annual_cycle = dataset.groupby('month')['data'].mean() # The column is called 'data'
        return annual_cycle.values
    else:
        raise ValueError('The input data must be a 1D np array or a pandas Series.')


def compute_climatology(data, time, period):
    """
    Compute the climatology of a given time series data for a specified period.

    Parameters
    ----------
    data : numpy.ndarray or pandas.Series
        The input time series data. Must be a 1D array or Series.
    time : array-like
        The corresponding time values for the data. Must be convertible to datetime.
    period : str
        The period for which to compute the climatology (e.g., 'DJF', 'MAM', 'JJA', 'SON').
        
    Returns
    -------
    numpy.ndarray
        The computed climatology for the specified period.
        
    Raises
    ------
    ValueError
        If the input data is not a 1D numpy array or a pandas Series, or if the period is invalid.
    """
    if data.ndim == 1:
        if isinstance(data, pd.Series):
            dataset = pd.DataFrame(data, columns=['data'], index=time)
        else:
            time_index = pd.to_datetime(time)
            dataset = pd.DataFrame(data, columns=['data'], index=time_index)
        
        dataset['month'] = dataset.index.month
        
        if period == 'DJF':
            climatology = dataset[dataset['month'].isin([12, 1, 2])].groupby('month')['data'].mean()
        elif period == 'MAM':
            climatology = dataset[dataset['month'].isin([3, 4, 5])].groupby('month')['data'].mean()
        elif period == 'JJA':
            climatology = dataset[dataset['month'].isin([6, 7, 8])].groupby('month')['data'].mean()
        elif period == 'SON':
            climatology = dataset[dataset['month'].isin([9, 10, 11])].groupby('month')['data'].mean()
        else:
            raise ValueError('Invalid period. Use one of: DJF, MAM, JJA, SON.')
        
        return climatology.values
    else:
        raise ValueError('The input data must be a 1D np array or a pandas Series.')