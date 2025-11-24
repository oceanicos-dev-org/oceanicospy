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

    This class supports two modes:
    - mode="keep"    → keep points INSIDE rectangles (default)
    - mode="exclude" → remove points INSIDE rectangles
    """

    def __init__(self, rectangles: List[AxisAlignedRectangle], mode: str = "keep"):
        """
        Parameters
        ----------
        rectangles : list of AxisAlignedRectangle
            Rectangles representing inclusion/exclusion zones.

        mode : {"keep", "exclude"}, optional
            Determines how rectangles are applied:
            * "keep"    → retain only points inside rectangles.
            * "exclude" → remove points inside rectangles.
        """
        if mode not in ("keep", "exclude"):
            raise ValueError("mode must be either 'keep' or 'exclude'")

        self.rectangles = rectangles
        self.mode = mode

    @classmethod
    def from_dict(cls, rectangles_dict: Dict, mode: str = "keep") -> "XYZRectangleMask":
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

        return cls(rectangles, mode=mode)

    def filter_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter points according to the selected mode.

        mode="keep":
            Keep only points INSIDE any rectangle.
        
        mode="exclude":
            Remove points INSIDE any rectangle.

        Parameters
        ----------
        df : pandas.DataFrame
            Must contain at least ['x', 'y', 'z'].

        Returns
        -------
        pandas.DataFrame
            Filtered DataFrame.
        """
        mask = []

        for _, row in df.iterrows():
            x, y = row["x"], row["y"]
            inside_any = any(rect.contains(x, y) for rect in self.rectangles)

            if self.mode == "keep":
                mask.append(inside_any)       # Keep inside, drop outside
            else:  # mode == "exclude"
                mask.append(not inside_any)   # Keep outside, drop inside

        return df.loc[mask].reset_index(drop=True)
