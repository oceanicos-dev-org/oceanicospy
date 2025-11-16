from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict

import pandas as pd


@dataclass(frozen=True)
class AxisAlignedRectangle:
    """
    Axis-aligned rectangle defined by two opposite corners (p1, p2).

    Notes
    -----
    - The order of p1 and p2 is irrelevant; min/max are computed internally.
    - This geometry operates purely in the XY plane and does not involve CRS logic.
    """
    p1: Tuple[float, float]
    p2: Tuple[float, float]

    def contains(self, x: float, y: float) -> bool:
        """Return True if (x, y) lies inside or on the rectangle boundary."""
        min_x = min(self.p1[0], self.p2[0])
        max_x = max(self.p1[0], self.p2[0])
        min_y = min(self.p1[1], self.p2[1])
        max_y = max(self.p1[1], self.p2[1])
        return (min_x <= x <= max_x) and (min_y <= y <= max_y)


class XYZRectangleMask:
    """
    Apply axis-aligned rectangular masks to XYZ data.

    This class supports in-memory DataFrame filtering and can be used
    by higher-level modules such as xyz_tile or xyz_merger.
    """

    def __init__(self, rectangles: List[AxisAlignedRectangle]):
        """
        Parameters
        ----------
        rectangles : list of AxisAlignedRectangle
            Rectangles representing exclusion zones.
        """
        self.rectangles = rectangles

    @classmethod
    def from_dict(cls, rectangles_dict: Dict) -> "XYZRectangleMask":
        """
        Build a mask from a dictionary specification.

        Expected format
        ---------------
        {
            "count": N,
            "rectangles": [
                {"p1": [x1, y1], "p2": [x2, y2]},
                ...
            ]
        }
        """
        rect_list = rectangles_dict.get("rectangles", [])

        if not isinstance(rect_list, Iterable):
            raise ValueError("'rectangles' must be an iterable.")

        if rectangles_dict.get("count", len(rect_list)) != len(rect_list):
            raise ValueError("'count' does not match the number of provided rectangles.")

        rectangles: List[AxisAlignedRectangle] = []
        for item in rect_list:
            p1 = item["p1"]
            p2 = item["p2"]
            rect = AxisAlignedRectangle(
                p1=(float(p1[0]), float(p1[1])),
                p2=(float(p2[0]), float(p2[1]))
            )
            rectangles.append(rect)

        return cls(rectangles)

    def filter_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove points inside any rectangle.

        Parameters
        ----------
        df : pandas.DataFrame
            Must contain at least ['x', 'y', 'z'].

        Returns
        -------
        pandas.DataFrame
            Filtered DataFrame containing only points outside all rectangles.
        """
        mask = []
        for _, row in df.iterrows():
            x, y = row["x"], row["y"]
            inside_any = any(rect.contains(x, y) for rect in self.rectangles)
            mask.append(not inside_any)

        return df.loc[mask].reset_index(drop=True)
