# Gridmaker

now there are two ways to pass the grid information:

- directly from the user through a info dict. Technically is not required creating a method for this and it can be directly accessed from the ***fill_grid_section*** which are the benefits of using that method?
- read from the bathymetry file (this can be better implemented in the GIS module)

# Bathymaker

- Convert_xyz2asc should be exmplified through any guide.

Bathymaker and bottomfrictionprocessor:

- the use_link logic can be sent to utils because is repeated across multiple modules

A way has to be found to make the correction mask for big jumps in the time series easier to apply: see def_UHSLC_csv_to_ascii(
