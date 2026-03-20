
**Main questions are: what do we interpret as raw dataframe from a sensor? (minimal readable? or with some tweaks?)**

**what we do interpret as a clean dataframe (minimal ready to use?)**

- checking the bouy class
- Check AWAC measurements and modify the required things for the class and guide
- standardize all the dataframes for weather stations:

  - correct dtypes per column
  - same names across the weather stations
  - same pd.datetimeindex for all the dataframes
  - the get_raw_dataframe should get the data and replace nans for missing data
  - the get_clean_records should standardize the columns with the same name and so on.
