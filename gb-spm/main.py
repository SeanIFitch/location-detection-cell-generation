from utils import absolute_path
from position_fix_utils import position_fix_from_csv, filter_by_date, smooth_trajectory
from MapPlot import MapPlot
import webbrowser
from datetime import datetime
from gb_spm import characteristic_indices, significant_place_mining
import numpy as np


def silhouette_comparison():
    # Get trajectory
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path, accuracy_threshold=80)

    means = []
    test_values = [1e-11, 1e-12, 1e-13, 1e-14, 1e-15]
    for test in test_values:
        silhouettes = []
        # Filter to one day
        for i in range(14, 52):
            month = 4 + int(i / 31)
            day = i % 30 + 1
            day = datetime(2024, month, day)
            day_trajectory = filter_by_date(location_data, day)
            if len(day_trajectory) < 4:
                continue
            s = get_silhouette(day_trajectory, weight='inverse', s=test * len(day_trajectory), r_index=1)
            if s is not None:
                silhouettes.append(s)
        silhouettes = np.array(silhouettes)
        print(silhouettes.mean(), silhouettes.std(), test)
        means.append(silhouettes.mean())
    print("max:", np.max(means), test_values[np.argmax(means)])


def get_silhouette(trajectory, weight='uniform', s=5e-11, r_index=None):
    smoothed = smooth_trajectory(trajectory, s=s * len(trajectory), weight=weight, r_index=r_index)
    cp_indices = characteristic_indices(smoothed, 4, 1)  # [45:47]
    significant_places = significant_place_mining(smoothed, cp_indices, 3, 0.25, 120, 60)
    if len(significant_places) <= 1:
        return None

    s = 0
    for i in range(len(significant_places)):
        s += significant_places[i].silhouette(significant_places[:i] + significant_places[i + 1:])
    s /= len(significant_places)
    return s


def gb_spm(trajectory, weight):
    # Smoothing
    r_index = 1
    if weight == 'inverse':
        s = 5e-11
    elif weight == 'square':
        s = 5e-13
    elif weight == 'neighbor':
        s = 5e-11 / (2 * r_index + 1)
    smoothed = smooth_trajectory(trajectory, s=s * len(trajectory), weight=weight, r_index=r_index)
    # smoothed = smooth_trajectory(trajectory, s=5e-14 * len(trajectory), weight="square")

    # Characteristic points
    cp_indices = characteristic_indices(smoothed, 4, 1)  # [45:47]
    characteristic_points = trajectory[cp_indices]

    # Significant places
    significant_places = significant_place_mining(smoothed, cp_indices, 3, 0.25, 120, 60)

    map_plot = MapPlot()
    map_plot.add_curve(smoothed, color='yellow')
    map_plot.add_curve(trajectory, color='#4e108d')
    # map_plot.add_curve(smoothed_squared, color='blue')
    # map_plot.add_points_heat(characteristic_points, list(range(len(characteristic_points))))
    map_plot.add_stop_regions(significant_places, color="red", markers=True)

    map_file_path = absolute_path('map.html')
    map_plot.save(map_file_path)
    webbrowser.open(map_file_path)


def all_data():
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path, accuracy_threshold=120)
    gb_spm(location_data)


def day_by_day():
    # Get trajectory
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path, accuracy_threshold=80)

    # Filter to one day
    for i in range(14, 52):
        month = 4 + int(i / 31)
        day = i % 30 + 1
        day = datetime(2024, month, day)
        day_trajectory = filter_by_date(location_data, day)
        if len(day_trajectory) < 4:
            continue
        gb_spm(day_trajectory, weight='inverse')


# Interesting days: 5/22, 4/19, 4/20
# 4/18 [2150:2200] -> interesting short merge
def given_day(month, day):
    # Get trajectory
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path, accuracy_threshold=80)

    # Filter to one day
    day = datetime(2024, month, day)
    day_trajectory = filter_by_date(location_data, day)
    gb_spm(day_trajectory, weight="inverse")


if __name__ == '__main__':
    day_by_day()
