import os
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


class ProfileBuilder:
    """
    Class to generate a 1D bathymetric/topographic profile along a polyline path
    from a scattered XYZ point cloud.
    """

    def __init__(self, xyz_path: str):
        if not os.path.isfile(xyz_path):
            raise FileNotFoundError(f"XYZ file not found: {xyz_path}")
        self.xyz_path = xyz_path
        self.df_xyz = self.read_xyz_file()

    def read_xyz_file(self) -> pd.DataFrame:
        df = pd.read_csv(
            self.xyz_path,
            delim_whitespace=True,
            header=None,
            comment="#",
            engine="python"
        )
        df = df.iloc[:, :3]  # First 3 columns
        df.columns = ["X", "Y", "Z"]
        df = df.apply(pd.to_numeric, errors="coerce").dropna()
        return df

    def generate_profile(self,
                         path_coords: list,
                         dx: float,
                         output_path: str,
                         auto_adjust_end: bool = False,
                         invert_z: bool = False,
                         z_is_positive_down: bool = True) -> pd.DataFrame:
        """
        Generate a profile along a polyline defined by path_coords.

        Parameters:
        - path_coords: list of (x, y) tuples
        - dx: spacing between points
        - output_path: path to save output file
        - auto_adjust_end: if True, adjusts total length to fit dx spacing
        - invert_z: flips Z values
        - z_is_positive_down: assumes Z is positive downward if True
        """
        if len(path_coords) < 2:
            raise ValueError("At least two points are required to define a profile path.")

        X_full, Y_full, S_full = [], [], []
        s_total = 0.0

        for i in range(len(path_coords) - 1):
            p0 = np.array(path_coords[i])
            p1 = np.array(path_coords[i + 1])
            vec = p1 - p0
            length = np.linalg.norm(vec)
            if length == 0:
                continue

            n_points = int(np.floor(length / dx))
            if i == len(path_coords) - 2 and auto_adjust_end:
                n_points = int(np.ceil(length / dx))

            s_local = np.linspace(0, length, n_points, endpoint=False)
            X_seg = p0[0] + vec[0] / length * s_local
            Y_seg = p0[1] + vec[1] / length * s_local
            S_seg = s_total + s_local

            X_full.extend(X_seg)
            Y_full.extend(Y_seg)
            S_full.extend(S_seg)

            s_total += length

        # Add final point explicitly if auto_adjust_end
        if auto_adjust_end:
            X_full.append(path_coords[-1][0])
            Y_full.append(path_coords[-1][1])
            S_full.append(s_total)

        Xq = np.array(X_full)
        Yq = np.array(Y_full)
        S = np.array(S_full)

        # Interpolation using KDTree
        tree = cKDTree(self.df_xyz[["X", "Y"]].values)
        _, idx = tree.query(np.column_stack((Xq, Yq)), k=1)
        Zq = self.df_xyz.iloc[idx]["Z"].values

        if invert_z:
            Zq = -Zq
        if not z_is_positive_down:
            Zq = -Zq

        profile_df = pd.DataFrame({"x": S, "z": Zq})

        # Save to file
        ext = os.path.splitext(output_path)[1].lower()
        sep = "," if ext == ".csv" else " "
        profile_df.to_csv(output_path, sep=sep, index=False, float_format="%.3f")

        print(f"Profile saved to: {output_path}")
        return profile_df
