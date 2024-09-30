from utils import absolute_path
from position_fix_utils import (
    position_fix_dtype,
    position_fix_from_csv,
    filter_by_date,
)
from datetime import datetime, timedelta
import numpy as np
from LabelPlot import LabelPlot
import webbrowser
from Region import Region, recursive_merge
from geopy import distance


# TODO: use filtered subtrajectories
def interpolate_edges(trajectory, labels):
    region_ends = np.where(np.diff(labels) != 0)[0]
    new_points = np.zeros((len(region_ends)), dtype=position_fix_dtype)
    for i in range(len(region_ends)):
        end_index = region_ends[i]
        start_index = end_index + 1
        dist = distance.distance(trajectory[['lat', 'lon']][end_index],
                                 trajectory[['lat', 'lon']][start_index]).meters
        # end of a move
        if labels[end_index] == 0:
            new_points[i] = trajectory[start_index].copy()
            expected_travel_time = dist / trajectory[end_index]['speed']
            new_points[i]['time'] = trajectory[end_index]['time'] + expected_travel_time

        # end of a stop
        elif labels[end_index] == 1:
            new_points[i] = trajectory[end_index].copy()
            expected_travel_time = dist / trajectory[start_index]['speed']
            new_points[i]['time'] = trajectory[start_index]['time'] - expected_travel_time

    result_array = trajectory.copy()
    for i, idx in enumerate(region_ends):
        result_array = np.insert(result_array, idx + i + 1, new_points[i])

    return result_array


def remove_short_regions(trajectory, labels, to_remove, to_replace, time_threshold=60, point_threshold=None):
    subtrajectories, starts, ends = get_filtered_subtrajectories(trajectory, labels, to_remove, True)

    for i in range(len(subtrajectories)):
        time_diff = np.diff(subtrajectories[i]['time'][[0, -1]])[0]
        if time_diff < time_threshold:
            if point_threshold is None or ends[i] - starts[i] < point_threshold:
                labels[starts[i]:ends[i]] = to_replace

    return labels


def vector_directionality(trajectory) -> float:
    if len(trajectory) <= 5:
        return 0.0
    lat_rad = np.deg2rad(trajectory['lat'])
    lon_rad = np.deg2rad(trajectory['lon'])
    x = np.cos(lat_rad) * np.cos(lon_rad)
    y = np.cos(lat_rad) * np.sin(lon_rad)
    z = np.sin(lat_rad)
    cartesian_coords = np.array([x, y, z]).T

    difference = np.diff(cartesian_coords, axis=0)
    norms = np.linalg.norm(difference, axis=1)
    norms[norms == 0] = 1  # Avoid division by zero
    diff_normalized = difference / norms[:, np.newaxis]
    mean_vec = np.mean(diff_normalized, axis=0)
    return np.linalg.norm(mean_vec)


def get_filtered_subtrajectories(trajectory, labels, label, return_boundaries=False):
    difference = np.diff((labels == label).astype(int))
    starts = np.where(difference == 1)[0] + 1
    ends = np.where(difference == -1)[0] + 1
    if labels[0] == label:
        starts = np.insert(starts, 0, 0)
    if labels[-1] == label:
        ends = np.append(ends, len(labels))
    subtrajectories = [trajectory[starts[i]:ends[i]] for i in range(len(starts))]
    if return_boundaries:
        return subtrajectories, starts, ends
    else:
        return subtrajectories


def classify_walks_by_intersection(stop_regions, trajectory, labels, threshold):
    subtrajectories, starts, stops = get_filtered_subtrajectories(trajectory, labels, 2, True)
    walk_regions = [Region(i, 2) for i in subtrajectories]

    for i in range(len(walk_regions)):
        for stop in stop_regions:
            if stop.percent_intersection(walk_regions[i]) > threshold:
                labels[starts[i]:stops[i]] = 1
                break
            labels[starts[i]:stops[i]] = 0
    return labels


def show_speed_map(trajectory):
    labels = trajectory['speed'] < 1.5

    interpolated_trajectory = interpolate_edges(trajectory, labels)
    walking_labels = interpolated_trajectory['speed'] < 1.5
    stop_labels = interpolated_trajectory['speed'] < 0.5
    interpolated_labels = walking_labels.astype(int) * 2 - stop_labels.astype(int)

    # Convert sub 2-minute stops to walks
    interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 1, 2, 120, None)

    stop_regions = recursive_merge([Region(i, 1) for i in get_filtered_subtrajectories(interpolated_trajectory, interpolated_labels, 1)], 5)
    interpolated_labels = classify_walks_by_intersection(stop_regions, interpolated_trajectory, interpolated_labels.copy(), .9)

    # interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 0, 1, 5, 2)
    # interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 1, 0, 5, None)
    # interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 0, 1, 30, 5)
    # interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 1, 0, 30, None)
    # interpolated_labels = remove_short_regions(interpolated_trajectory, interpolated_labels, 1, 0, 300, None)

    map_plot = LabelPlot(height='1200px')
    map_plot.add_labeled_curve(interpolated_trajectory, labels=interpolated_labels, stop_markers=True)

    map_file_path = absolute_path('map.html')
    map_plot.save(map_file_path)
    webbrowser.open(map_file_path)


def given_day(data, day):
    # Filter to one day
    day_trajectory = filter_by_date(data, day)
    if len(day_trajectory) < 2:
        return

    show_speed_map(day_trajectory)


def day_by_day(data):
    start = data[0]['time']
    end = data[-1]['time']
    start_date = datetime.utcfromtimestamp(start)
    end_date = datetime.utcfromtimestamp(end)

    current_date = start_date
    while current_date <= end_date:
        current_date += timedelta(days=1)
        given_day(data, current_date)


if __name__ == '__main__':
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path, accuracy_threshold=None)
    given_day(location_data, datetime(2024, 4, 21))
    # day_by_day(location_data)
