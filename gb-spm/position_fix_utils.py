import numpy as np
import csv
from datetime import datetime
from scipy.interpolate import UnivariateSpline


position_fix_dtype = np.dtype([('lat', np.float64),
                              ('lon', np.float64),
                              ('time', np.float64),
                              ('accuracy', np.float64),
                               ('speed', np.float64)])


def position_fix_from_csv(file_path, remove_duplicates=True, accuracy_threshold=None):
    data = []
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        prior = None
        for row in reader:
            point = (float(row['latitude']), float(row['longitude']), float(row['create_time_epoch']), float(row['accuracy']), float(row['speed']))
            if remove_duplicates:
                if prior is not None and prior == point:
                    prior = point
                    continue
                else:
                    prior = point
            if accuracy_threshold is not None:
                if float(row['accuracy']) > accuracy_threshold:
                    continue
            data.append(point)
    return np.array(data, dtype=position_fix_dtype)


def distance_between_points(points, unit='km'):
    if len(points) < 2:
        raise ValueError("At least two points are required")
    if unit not in ['m', 'km', 'ft']:
        raise ValueError("Unit must be 'm', 'km', 'ft'")

    # Convert latitude and longitude from degrees to radians
    lon = np.radians(points['lon'])
    lat = np.radians(points['lat'])

    # Compute differences
    lat_diff = lat[1:] - lat[:-1]
    lon_diff = lon[1:] - lon[:-1]

    # Haversine formula
    a = np.sin(lat_diff / 2.0) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(lon_diff / 2.0) ** 2

    c = 2 * np.arcsin(np.sqrt(a))
    distance_km = 6378.137 * c

    if unit == 'km':
        return distance_km
    elif unit == 'ft':
        return distance_km * 3280.84
    elif unit == 'm':
        return distance_km * 1000


def distance_between_arrays(points1, points2, unit='km'):
    if unit not in ['m', 'km', 'ft']:
        raise ValueError("Unit must be 'm', 'km', 'ft'")

    # Convert latitude and longitude from degrees to radians
    lon1 = np.radians(points1['lon'])
    lon2 = np.radians(points2['lon'])
    lat1 = np.radians(points1['lat'])
    lat2 = np.radians(points2['lat'])

    # Compute differences
    lat_diff = lat1 - lat2
    lon_diff = lon1 - lon2

    # Haversine formula
    a = np.sin(lat_diff / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(lon_diff / 2.0) ** 2

    c = 2 * np.arcsin(np.sqrt(a))
    distance_km = 6378.137 * c

    if unit == 'km':
        return distance_km
    elif unit == 'ft':
        return distance_km * 3280.84
    elif unit == 'm':
        return distance_km * 1000


def filter_by_date(points, date):
    year = date.year
    month = date.month
    day = date.day

    # Create datetime objects for the start and end of the day
    start_of_day = datetime(year, month, day, 0, 0, 0)
    end_of_day = datetime(year, month, day, 23, 59, 59)

    # Convert datetime objects to epoch time (Unix timestamp)
    epoch_start_of_day = start_of_day.timestamp()
    epoch_end_of_day = end_of_day.timestamp()

    mask = (points['time'] >= epoch_start_of_day) & (points['time'] <= epoch_end_of_day)

    # Extracting values between the timestamps
    return points[mask]


def smooth_trajectory(trajectory, s=None, weight="inverse", r_index=1):
    time = trajectory['time']
    if weight == "inverse":
        weights = 1 / trajectory['accuracy']
    elif weight == "square":
        weights = 1 / trajectory['accuracy'] ** 2
    elif weight == "exp":
        weights = np.exp(-trajectory['accuracy'])
    elif weight == "neighbor":
        kernel = np.ones(r_index * 2 + 1)
        padded_accuracies = np.pad(trajectory['accuracy'], r_index, mode='edge')
        weights = 1 / np.convolve(padded_accuracies, kernel, mode='valid')
    elif weight == "uniform":
        weights = np.ones_like(trajectory['accuracy'])
    else:
        raise ValueError("Unrecognized weight method")

    if s is None:
        lat_spline = UnivariateSpline(time, trajectory['lat'], w=weights)
        lon_spline = UnivariateSpline(time, trajectory['lon'], w=weights)
    else:
        lat_spline = UnivariateSpline(time, trajectory['lat'], w=weights, s=s)
        lon_spline = UnivariateSpline(time, trajectory['lon'], w=weights, s=s)

    latitude_smoothed = lat_spline(time)
    longitude_smoothed = lon_spline(time)

    # Creating a new structured array
    smoothed_trajectory = np.zeros(len(time), dtype=position_fix_dtype)
    smoothed_trajectory['lat'] = latitude_smoothed
    smoothed_trajectory['lon'] = longitude_smoothed
    smoothed_trajectory['time'] = time

    return smoothed_trajectory
