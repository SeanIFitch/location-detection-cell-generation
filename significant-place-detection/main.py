from datetime import timedelta
from MapPlot import MapPlot
import webbrowser
from StopRegion import StopRegion
from Trajectory import Trajectory
import os
import numpy as np


def full_path(filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, filename)
    return path


def show_map(regions, trajectory):
    map_plot = MapPlot()
    if trajectory is not None:
        map_plot.add_curve(trajectory.points)
    if regions is not None:
        map_plot.add_regions(regions)
    map_file_path = full_path('map.html')
    map_plot.save(map_file_path)
    webbrowser.open(map_file_path)


def get_regions(trajectory):
    labels = trajectory.get_labels(stop_threshold=0.5, calculated_threshold=0.25)

    regions = trajectory.get_stop_regions(labels, distance_threshold=500, accuracy_error=30)
    regions = StopRegion.recursive_merge(regions, distance_threshold=10)

    return regions


if __name__ == '__main__':
    file_path = full_path("../data/andrew-device-locations-all2.csv")
    traj = Trajectory.from_file(file_path)

    # Produce one map for each day in the data
    start, end = traj.get_date_range()
    current = start
    while current <= end:
        current += timedelta(days=1)
        day_traj = traj.filter_by_date(current)
        if len(day_traj.points) <= 1:
            continue
        stop_regions = get_regions(day_traj)
        mask = np.array([r.longer_than(duration=300) for r in stop_regions])
        stop_regions = np.asarray(stop_regions)[mask]
        show_map(stop_regions, day_traj)
