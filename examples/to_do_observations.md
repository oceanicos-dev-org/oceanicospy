**Main questions are:**

1. **what do we interpret as raw dataframe from a sensor? (minimal readable? or with some tweaks?)**
2. **what we do interpret as a clean dataframe (minimal ready to use?)**
3. **How do we deal with the directory/file paths as parameters for the classes?**

- AWAC

  - It is quite weird that the single wad file does not start at 00:00 (minutes/seconds)
  - To check the way how the direction is computed
- Weather stations: standardize the dataframes

  - correct dtypes per column
  - same names across the weather stations
  - same pd.datetimeindex for all the dataframes
  - the get_raw_dataframe should get the data and replace nans for missing data
  - the get_clean_records should standardize the columns with the same name and so on.
- CTD: should we create a common method to append/merge another CTD measurements to host them all in one particular centralized dataframe?
- HOBO: did they work together or reading only one is more granular and efficient?
