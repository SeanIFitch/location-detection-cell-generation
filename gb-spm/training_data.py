import numpy as np
import csv
from utils import absolute_path
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from position_fix_utils import filter_by_date, smooth_trajectory
from gb_spm import characteristic_indices, significant_place_mining
import webbrowser
from MapPlot import MapPlot


position_fix_dtype = np.dtype([
    ('lat', np.float64),
    ('lon', np.float64),
    ('time', np.float64),
    # ('altitude', np.float64),
    ('bearing', np.float64),
    ('speed', np.float64),
    ('accuracy', np.float64),
    # ('vertical_accuracy', np.float64),
    ('bearing_accuracy', np.float64),
    ('speed_accuracy', np.float64),
])


def position_fix_from_csv(file_path, remove_duplicates=True):
    data = []
    with open(file_path, 'r') as file:
        reader = csv.DictReader(file)
        prior = None
        for row in reader:
            point = (
                float(row['latitude']),
                float(row['longitude']),
                float(row['create_time_epoch']),
                # float(row['altitude']),
                float(row['bearing']),
                float(row['speed']),
                float(row['accuracy']),
                # float(row['vertical_accuracy']),
                float(row['bearing_accuracy']),
                float(row['speed_accuracy']),
            )
            if remove_duplicates:
                if prior is not None and prior == point:
                    continue
                else:
                    prior = point
            data.append(point)
    return np.array(data, dtype=position_fix_dtype)


# RESULTS: altitude and vertical accuracy may be unnecessary.
def show_covariance_matrix(data):
    data_matrix = np.column_stack([data[field] for field in position_fix_dtype.names])
    data_matrix_standardized = (data_matrix - np.mean(data_matrix, axis=0)) / np.std(data_matrix, axis=0)

    cov_matrix = np.cov(data_matrix_standardized, rowvar=False)
    # Plot covariance matrix as heatmap
    plt.figure(figsize=(8, 6))
    plt.imshow(cov_matrix, cmap='viridis', interpolation='nearest')
    plt.colorbar(label='Covariance')
    plt.title('Covariance Matrix')
    plt.xticks(np.arange(len(position_fix_dtype.names)), position_fix_dtype.names, rotation=45)
    plt.yticks(np.arange(len(position_fix_dtype.names)), position_fix_dtype.names)
    plt.show()


def all_days(data):
    date_range = (datetime(2024, 4, 15), datetime(2024, 5, 22))

    current_date = date_range[0]
    while current_date <= date_range[1]:
        day_data = filter_by_date(location_data, current_date)
        current_date += timedelta(days=1)


def gb_spm(data):
    smoothed = smooth_trajectory(data, s=5e-11 * len(data), weight='inverse')
    cp_indices = characteristic_indices(smoothed, 4, 1)  # [45:47]
    characteristic_points = data[cp_indices]
    significant_places = significant_place_mining(smoothed, cp_indices, 3, 0.25, 120, 60)

    map_plot = MapPlot()
    map_plot.add_curve(data, color='green')
    map_plot.add_points_clickable(characteristic_points)
    map_plot.add_stop_regions(significant_places, color='blue')

    map_file_path = absolute_path('map.html')
    map_plot.save(map_file_path)
    webbrowser.open(map_file_path)
    return significant_places


if __name__ == '__main__':
    data_path = absolute_path("../data/andrew-device-locations-all.csv")
    location_data = position_fix_from_csv(data_path)
    day_data = filter_by_date(location_data, datetime(2024, 4, 20))
    gb_spm(day_data)
