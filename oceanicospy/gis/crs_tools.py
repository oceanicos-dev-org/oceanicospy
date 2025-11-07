import pandas as pd
import geopandas as gpd


class ShapefileReprojector:
    """
    Class for loading point data (shapefile or XYZ-like text file),
    reprojecting coordinates to a target CRS, and exporting as .xyz.

    The class assumes input data are point locations with X, Y and Z
    provided as columns.

    Supported inputs:
    - .shp (point layer; CRS taken from file)
    - .txt / .xyz (space- or comma-delimited; numeric columns may be in scientific notation)

    Typical LiDAR XYZ case:
    - No header
    - Columns = [lon, lat, z] in WGS84 (EPSG:4326)
    - Needs export in UTM17N (EPSG:32617)

    Usage example for LiDAR XYZ:
        reproj = ShapefileReprojector(
            input_path="C:/data/LidarSAfinal.xyz",
            x_col="X",  # longitude
            y_col="Y",  # latitude
            z_col="Z",  # elevation
            source_epsg=4326  # WGS84
        )

        reproj.reproject_to_xyz(
            target_epsg=32617,  # UTM 17N
            output_xyz_path="C:/data/LidarSAfinal_UTM17N.xyz"
        )
    """

    def __init__(self, input_path, x_col="X", y_col="Y", z_col="Z", source_epsg=None):
        """
        Initialize the object and load data.

        Parameters
        ----------
        input_path : str
            Path to input file. Can be:
            - a .shp (point shapefile)
            - a .txt / .xyz (space- or comma-delimited table with X,Y,Z columns)
        x_col, y_col, z_col : str
            Column names that represent X, Y, Z in the input file.
            For header-less .xyz files we will auto-generate these names
            so you can keep the defaults "X","Y","Z".
        source_epsg : int or None
            EPSG code of the source CRS.
            Required if input is .txt / .xyz because those formats
            do not store CRS internally.
            Ignored for .shp (CRS is read from file).
        """

        self.input_path = input_path
        self.x_col = x_col
        self.y_col = y_col
        self.z_col = z_col
        self.source_epsg = source_epsg

        lower_path = input_path.lower()
        if lower_path.endswith(".shp"):
            self._load_from_shapefile()
        elif lower_path.endswith(".txt") or lower_path.endswith(".xyz"):
            self._load_from_text()
        else:
            raise ValueError("Unsupported input type. Use .shp, .txt or .xyz")

        # Sanity check: required coordinate columns must exist
        for col in [self.x_col, self.y_col, self.z_col]:
            if col not in self.gdf.columns:
                raise ValueError(f"Column '{col}' not found in input data.")

    def _load_from_shapefile(self):
        """
        Internal: load data from a shapefile using geopandas.
        Uses the shapefile CRS as source CRS.
        """
        gdf_in = gpd.read_file(self.input_path)

        if gdf_in.crs is None:
            raise ValueError(
                "Input shapefile has no CRS defined. "
                "Define a CRS before using this tool."
            )

        self.gdf = gpd.GeoDataFrame(
            gdf_in.copy(),
            geometry=gpd.points_from_xy(gdf_in[self.x_col], gdf_in[self.y_col]),
            crs=gdf_in.crs
        )

    def _read_text_generic(self):
        """
        Try to read a text/xyz file in a robust way.

        Strategy:
        1. Try reading as whitespace-delimited with no header.
           -> assign default column names ["X","Y","Z","C3","C4",...]
        2. If that fails, try pandas default CSV parser.

        Returns
        -------
        df_in : pandas.DataFrame
        """
        # Attempt 1: whitespace, no header in file
        try:
            df_in = pd.read_csv(
                self.input_path,
                delim_whitespace=True,
                header=None,
                engine="python"
            )

            # Auto-name columns: X,Y,Z,rest...
            base_names = ["X", "Y", "Z"]
            if df_in.shape[1] > 3:
                # give generic names to any extra columns beyond Z
                extra_cols = [f"COL{i}" for i in range(4, df_in.shape[1] + 1)]
                df_in.columns = base_names + extra_cols
            else:
                df_in.columns = base_names[:df_in.shape[1]]
            return df_in

        except Exception:
            pass  # fallback below

        # Attempt 2: generic CSV (comma, etc.) with header detection
        df_in = pd.read_csv(self.input_path)
        return df_in

    def _load_from_text(self):
        """
        Internal: load data from .txt / .xyz into a GeoDataFrame.

        Assumptions for LiDAR XYZ:
        - File may NOT have header.
        - Coordinates may be in scientific notation.
        - Columns: lon, lat, z (WGS84) -> will be named X,Y,Z by _read_text_generic.

        Requirements:
        - self.source_epsg must be provided (e.g. 4326 for WGS84).
        """
        if self.source_epsg is None:
            raise ValueError(
                "source_epsg must be provided for TXT/XYZ inputs "
                "because these files do not contain CRS information."
            )

        df_in = self._read_text_generic()

        # Build GeoDataFrame with declared CRS
        self.gdf = gpd.GeoDataFrame(
            df_in.copy(),
            geometry=gpd.points_from_xy(df_in[self.x_col], df_in[self.y_col]),
            crs=f"EPSG:{self.source_epsg}"
        )

    def reproject_to_xyz(self, target_epsg, output_xyz_path):
        """
        Reproject loaded points to target CRS and export as .xyz.

        Parameters
        ----------
        target_epsg : int
            EPSG code of the desired output CRS, e.g. 32617 for UTM 17N.
        output_xyz_path : str
            Output path for the .xyz file.

        Output format:
        - Space separated
        - No header
        - Columns: X Y Z
        - 6 decimal places
        """
        if self.gdf.crs is None:
            raise ValueError(
                "Current GeoDataFrame has no CRS. Cannot reproject."
            )

        # Reproject to target
        gdf_proj = self.gdf.to_crs(epsg=target_epsg)

        # Build output XYZ dataframe
        df_xyz = pd.DataFrame({
            "X": gdf_proj.geometry.x,
            "Y": gdf_proj.geometry.y,
            "Z": gdf_proj[self.z_col].values
        })

        # Export
        df_xyz.to_csv(
            output_xyz_path,
            sep=" ",
            header=False,
            index=False,
            float_format="%.6f"
        )

        print(
            f"Reprojected XYZ file saved to: {output_xyz_path}\n"
            f"Source CRS: {self.gdf.crs.to_string()}  ->  Target CRS: EPSG:{target_epsg}"
        )

    def reproject_wgs84_xyz_to_utm17n(self, output_xyz_path):
        """
        Convenience helper for the common case in your workflow:
        - Input XYZ in WGS84 (EPSG:4326) lon/lat/z
        - Output XYZ in UTM 17N (EPSG:32617) easting/northing/z

        Parameters
        ----------
        output_xyz_path : str
            Output path for the .xyz file.
        """
        self.reproject_to_xyz(target_epsg=32617, output_xyz_path=output_xyz_path)

