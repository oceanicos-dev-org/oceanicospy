import numpy as np
import pandas as pd
from .weather_station_base import WeatherStationBase

class WeatherSens(WeatherStationBase):
    """
    """
    
    def _load_raw_dataframe(self):
        df = pd.read_excel(self.filepath, engine="openpyxl")

        # Replace empty or invalid values with NaN
        df.replace(["", "---", "NaN", "null"], np.nan, inplace=True)

    def _standardize_columns(self, df):
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
        df.rename(columns=column_map, inplace=True)

        # Convert DateTime to pandas datetime
        df['date'] = pd.to_datetime(df['DateTime'], errors='coerce')

        # Drop original DateTime column and set index
        df = df.drop(['DateTime'], axis=1)
        df = df.set_index('date')

        # Convert numerical columns to float if possible
        for col in ['Rain', 'Temp', 'Hum', 'Bar', 'Speed', 'Direction']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _compute_direction_degrees(self, df):
        # Assuming 'Direction' is already in degrees, if not, implement conversion logic here
        return df