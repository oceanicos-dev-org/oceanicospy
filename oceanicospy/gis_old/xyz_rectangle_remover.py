from dataclasses import dataclass
from typing import Tuple, Dict, List, Iterable

@dataclass(frozen=True)
class AxisAlignedRectangle:
    """Represents an axis-aligned rectangle defined by two opposite corners (x, y)."""
    p1: Tuple[float, float]
    p2: Tuple[float, float]

    def contains(self, x: float, y: float) -> bool:
        """Return True if (x, y) is inside or on the rectangle boundary."""
        min_x = self.p1[0] if self.p1[0] <= self.p2[0] else self.p2[0]
        max_x = self.p2[0] if self.p2[0] >= self.p1[0] else self.p1[0]
        min_y = self.p1[1] if self.p1[1] <= self.p2[1] else self.p2[1]
        max_y = self.p2[1] if self.p2[1] >= self.p1[1] else self.p1[1]
        return (min_x <= x <= max_x) and (min_y <= y <= max_y)


def _parse_rectangles(rectangles_dict: Dict) -> List[AxisAlignedRectangle]:
    """
    Parse and validate the rectangles dictionary.
    Expected schema:
        {
            "count": <int>,
            "rectangles": [
                {"p1": (x1, y1), "p2": (x2, y2)},
                ...
            ]
        }
    Returns a list of AxisAlignedRectangle objects.
    """
    if not isinstance(rectangles_dict, dict):
        raise ValueError("rectangles_dict must be a dictionary.")

    if "count" not in rectangles_dict or "rectangles" not in rectangles_dict:
        raise ValueError("rectangles_dict must contain 'count' and 'rectangles' keys.")

    rect_list = rectangles_dict["rectangles"]
    if not isinstance(rect_list, Iterable):
        raise ValueError("'rectangles' must be an iterable of corner pairs.")

    if rectangles_dict["count"] != len(rect_list):
        raise ValueError("'count' does not match the number of provided rectangles.")

    rectangles: List[AxisAlignedRectangle] = []
    for idx, item in enumerate(rect_list, start=1):
        try:
            p1 = item["p1"]
            p2 = item["p2"]
            rect = AxisAlignedRectangle(p1=(float(p1[0]), float(p1[1])),
                                        p2=(float(p2[0]), float(p2[1])))
            rectangles.append(rect)
        except Exception as exc:
            raise ValueError(f"Invalid rectangle at position {idx}: {exc}") from exc
    return rectangles


def remove_points_in_rectangles_xyz(input_xyz_path: str,
                                    output_xyz_path: str,
                                    rectangles_dict: Dict,
                                    delimiter: str = None) -> int:
    """
    Remove points from an .xyz file whose (x,y) fall inside any of the given rectangles.

    Parameters
    ----------
    input_xyz_path : str
        Full path to the input .xyz file (including filename).
    output_xyz_path : str
        Full path to the output .xyz file (including filename).
    rectangles_dict : Dict
        Dictionary describing rectangles. Expected schema:
            {
                "count": <int>,
                "rectangles": [
                    {"p1": (x1, y1), "p2": (x2, y2)},
                    ...
                ]
            }
        Rectangles are axis-aligned; points on the boundary are considered inside (removed).
    delimiter : str, optional
        Column separator for reading/writing. If None, any whitespace is treated as a separator.
        Use a single character (e.g., ' ' or '\t') if you want to enforce an output delimiter.

    Returns
    -------
    int
        Number of points written to the output file (i.e., kept after filtering).

    Notes
    -----
    - The function streams line-by-line to handle large files.
    - Preserves extra columns beyond z (e.g., RGB) by writing the original line back.
    - Skips empty or malformed lines quietly (does not write them).
    """
    rectangles = _parse_rectangles(rectangles_dict)

    kept_count = 0
    with open(input_xyz_path, "r", encoding="utf-8") as fin, \
         open(output_xyz_path, "w", encoding="utf-8") as fout:

        for raw_line in fin:
            line = raw_line.strip()
            if not line:
                # Skip empty lines
                continue

            # Split using whitespace if delimiter is None; otherwise use the provided delimiter
            parts = line.split() if delimiter is None else line.split(delimiter)

            # Require at least x, y, z; keep extra fields untouched
            if len(parts) < 3:
                # Malformed line; skip
                continue

            try:
                x = float(parts[0])
                y = float(parts[1])
            except ValueError:
                # Non-numeric x or y; skip
                continue

            # Check if the point (x, y) is inside any rectangle
            inside_any = any(rect.contains(x, y) for rect in rectangles)

            if not inside_any:
                # Keep original formatting if delimiter is None; else rejoin with the delimiter
                if delimiter is None:
                    fout.write(raw_line)
                else:
                    fout.write(delimiter.join(parts) + "\n")
                kept_count += 1

    return kept_count
