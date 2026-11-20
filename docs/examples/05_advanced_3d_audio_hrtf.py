# -*- coding: utf-8 -*-
"""Example 05 (Advanced): 3D Spatial Bearing & Distance Utilities."""
from pyaudiogaming.utils import clock_direction, distance_3d


def describe_target(px, py, pz, tx, ty, tz):
    dist = distance_3d(px, py, pz, tx, ty, tz)
    hour = clock_direction(tx - px, ty - py)
    return f"Target at {hour} o'clock, {dist:.1f} meters away."


if __name__ == "__main__":
    print(describe_target(0, 0, 0, 6, 2, 0))
