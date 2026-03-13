import pandas as pd
import numpy as np
import glob
import os

pd.set_option('future.no_silent_downcasting', True)

class WeatherStation():
    """
    A class to handle reading and processing the data files recorded by the weather station (DAVIS). 

    Notes
    -----
    10-Dec-2024 : Origination - Franklin Ayala

    """
    def __init__(self,directory_path):
        """
        Initializes the WeatherStation object with the given directory path.

        Parameters
        ----------
        directory_path : str
            Path to the directory where weather station data is stored.

        """
        self.directory_path = directory_path
    
    def read_records(self, file_name):
        """
        Reads weather station records from a specified file and processes the data into a pandas DataFrame.

        Parameters
        ----------
        file_name : str
            The name of the file containing the weather station records.

        Returns
        -------
        df : pandas.DataFrame
            A DataFrame containing the processed weather station data

        Notes
        -----
            - The function assumes that the first two lines of the file are headers or metadata and skips them.
            - The 'AM/PM' column values are replaced with 'AM' and 'PM' for consistency.
        """

        file_path = f"{self.directory_path}/{file_name}"
        with open(file_path, 'r') as file:
            data = file.read().split('\n')[2:-1]
        
        processed_data = [(' '.join(line.split())).split(' ') for line in data]
        
        columns = ['Date', 'time', 'AM/PM', 'Out', 'Temp1', 'Temp2', 'Hum', 'Pt.', 'Speed', 'Dir1', 'Run', 'Speed2', 'Dir2', 
                   'Chill', 'Index1', 'Index2', 'Bar', 'Rain', 'Rate', 'D-D1', 'D-D2', 'Temp4', 'Hum2', 'Dew', 'Heat', 'EMC', 
                   'Density', 'Samp', 'Tx', 'Recept', 'Int.']
        
        df = pd.DataFrame(processed_data, columns=columns)
        df['AM/PM'] = df['AM/PM'].replace({'a': 'AM', 'p': 'PM'})
        
        return df

    def get_clean_records(self):
        """
        Cleans and processes weather station records.
        
        Returns
        -------
        self.clean_records: pd.DataFrame
            A DataFrame with cleaned weather station records, indexed by datetime.
        """
        self.records = self.read_records('weather_station_data.txt')
        self.records.replace('---', np.nan, inplace=True)
        self.records.dropna(axis=1, how='all', inplace=True)
        
        self.records['date'] = pd.to_datetime(self.records['Date'] + ' ' + self.records['time'] + ' ' + self.records['AM/PM'], 
                               format='%m/%d/%y %I:%M %p')
        self.clean_records = self.records.drop(['Date', 'time', 'AM/PM'], axis=1)
        self.clean_records = self.clean_records.set_index('date')
        
        dtypes = {'Speed': float}
        self.clean_records = self.clean_records.astype(dtypes)

        maps_to_degrees = {
                                'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5,
                                'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
                                'S': 180, 'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
                                'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5
                            }

        self.clean_records['Direction'] = self.clean_records['Dir1'].map(maps_to_degrees)

        return self.clean_records
    




class WeatherSensStation:
    """
    A class to handle reading and processing WeatherSens weather station data from Excel files (.xlsx).
    Standardized to be consistent with Davis WeatherStation.

    Notes
    -----
    16-Jul-2025 : Created - Daniela Rosero
    """

    def __init__(self, directory_path):
        """
        Initializes the WeatherSensStationXLSX object with the given directory path.

        Parameters
        ----------
        directory_path : str
            Path to the directory where weather station data is stored.
        """
        self.directory_path = directory_path

    def read_records(self, file_name):
        """
        Reads WeatherSens station records from a specified Excel file.

        Parameters
        ----------
        file_name : str
            Name of the .xlsx file.

        Returns
        -------
        df : pandas.DataFrame
            A DataFrame with the raw data.
        """
        file_path = os.path.join(self.directory_path, file_name)
        df = pd.read_excel(file_path, engine="openpyxl")

        # Replace empty or invalid values with NaN
        df.replace(["", "---", "NaN", "null"], np.nan, inplace=True)
        return df

    def get_clean_records(self):
        """
        Cleans and processes WeatherSens station records to be consistent with Davis.

        Returns
        -------
        self.clean_records : pd.DataFrame
            A cleaned DataFrame indexed by datetime.
        """
        # Find the first .xlsx file in the directory
        files = glob.glob(os.path.join(self.directory_path, "*.xlsx"))
        if not files:
            raise FileNotFoundError("No .xlsx file found in the specified directory.")

        file_name = os.path.basename(files[0])
        self.records = self.read_records(file_name)

        # Standardize column names to Davis style
        column_map = {
            'Date/Time': 'DateTime',
            'Precipitacion (mm)': 'Rain',
            'Temperatura Aire (°C)': 'Temp',
            'Humedad Aire (%)': 'Hum',
            'Presion Barometrica (hPa)': 'Bar',
            'Velocidad Viento (m/s)': 'Speed',
            'Direccion Viento (°)': 'Direction',
        }
        self.records.rename(columns=column_map, inplace=True)

        # Convert DateTime to pandas datetime
        self.records['date'] = pd.to_datetime(self.records['DateTime'], errors='coerce')

        # Drop original DateTime column and set index
        self.clean_records = self.records.drop(['DateTime'], axis=1)
        self.clean_records = self.clean_records.set_index('date')

        # Convert numerical columns to float if possible
        for col in ['Rain', 'Temp', 'Hum', 'Bar', 'Speed', 'Direction']:
            if col in self.clean_records.columns:
                self.clean_records[col] = pd.to_numeric(self.clean_records[col], errors='coerce')

        return self.clean_records
