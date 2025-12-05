import xarray as xr

class OutputReader():
    def __init__(self,filepath):
        self.filepath = filepath
        self.ds = xr.open_dataset(self.filepath)

    def read_field_output(self):
        """Read XBeach field output and return a xarray Dataset."""
        self.field_ds = self.ds[[var for var in self.ds.data_vars if self.ds[var].ndim > 2]]
        self._display_dataset_info(self.field_ds)
        return self.field_ds

    def read_point_output(self):
        """Read XBeach point output and return a xarray Dataset."""
        self.point_ds = self.ds[[var for var in self.ds.data_vars if self.ds[var].ndim == 2]]
        self._display_dataset_info(self.point_ds)
        return self.point_ds
    
    def _display_dataset_info(self, ds: xr.Dataset):
        """Display basic information about the dataset."""
        print("Dataset dimensions:", ds.dims)
        print("Dataset variables:", list(ds.data_vars))
        print("Dataset coordinates:", list(ds.coords)) 