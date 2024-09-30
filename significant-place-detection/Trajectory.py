import csv
import numpy as np
from geopy.distance import distance
from datetime import datetime
from StopRegion import StopRegion


position_fix_dtype = np.dtype([('lat', np.float64),
                              ('lon', np.float64),
                              ('time', np.float64),
                              ('accuracy', np.float64),
                              ('speed', np.float64),
                              ('distance', np.float64),
                              ('time_diff', np.float64)])


class Trajectory:
    def __init__(self, points):
        self.points = points

    def __getitem__(self, index):
        return self.points[index]

    def __len__(self):
        return len(self.points)

    @classmethod
    def from_file(cls, file_path, remove_duplicates=True, accuracy_threshold=None):
        points = []
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)
            prior = None
            for row in reader:
                point = (float(row['latitude']),
                         float(row['longitude']),
                         float(row['create_time_epoch']),
                         float(row['accuracy']),
                         float(row['speed']),
                         0.0,
                         0.0
                         )
                if remove_duplicates:
                    if prior is not None and prior == point:
                        prior = point
                        continue
                    else:
                        prior = point
                if accuracy_threshold is not None:
                    if float(row['accuracy']) > accuracy_threshold:
                        continue
                points.append(point)
        points = np.array(points, dtype=position_fix_dtype)
        last = points[0]
        for i in points[1:]:
            i['distance'] = distance(i[['lat', 'lon']], last[['lat', 'lon']]).meters
            i['time_diff'] = i['time'] - last['time']
            last = i

        return cls(points)

    def filter_by_date(self, date):
        year = date.year
        month = date.month
        day = date.day

        # Create datetime objects for the start and end of the day
        start_of_day = datetime(year, month, day, 0, 0, 0)
        end_of_day = datetime(year, month, day, 23, 59, 59)

        # Convert datetime objects to epoch time (Unix timestamp)
        epoch_start_of_day = start_of_day.timestamp()
        epoch_end_of_day = end_of_day.timestamp()

        mask = (self.points['time'] >= epoch_start_of_day) & (self.points['time'] <= epoch_end_of_day)
        new_data = self.points[mask].copy()

        # Extracting values between the timestamps
        return Trajectory(new_data)

    def get_date_range(self):
        start = self.points[0]['time']
        end = self.points[-1]['time']
        start_date = datetime.utcfromtimestamp(start).date()
        end_date = datetime.utcfromtimestamp(end).date()
        return start_date, end_date

    # Using either only reported or calculated speed can lead to missing stops.
    # For reported, signal loss in a building would mean it never drops below the threshold.
    # For calculated, noise in the building would mean it never drops below the threshold.
    # Therefore, use an expected value for the reported threshold and a much more conservative value for calculated.
    def get_labels(self, stop_threshold, calculated_threshold=None):
        labels = np.zeros(len(self.points))
        for i in range(len(self.points)):
            if self.points[i]['speed'] < stop_threshold:
                labels[i] = 1
            elif (calculated_threshold is not None
                  and self.points[i]['distance'] / self.points[i]['time_diff'] < calculated_threshold):
                labels[i] = 1
        return labels

    # Returns subtrajectories of a given label
    def get_subtrajectories(self, labels, label, return_boundaries=False):
        difference = np.diff((labels == label).astype(int))
        starts = np.where(difference == 1)[0] + 1
        ends = np.where(difference == -1)[0] + 1
        if labels[0] == label:
            starts = np.insert(starts, 0, 0)
        if labels[-1] == label:
            ends = np.append(ends, len(labels))
        subtrajectories = [self.points[starts[i]:ends[i]] for i in range(len(starts))]
        if return_boundaries:
            return subtrajectories, starts, ends
        else:
            return subtrajectories

    def get_stop_regions(self, labels, distance_threshold=500, accuracy_error=30):
        consecutive_points, starts, stops = self.get_subtrajectories(labels, 1, True)
        starts = starts.tolist()
        stops = stops.tolist()

        regions = []
        while len(starts) > 0:
            start = starts.pop(0)
            stop = stops.pop(0)
            for j in range(start, stop - 1):
                # split if points are far apart
                thresh = min(distance_threshold, np.sum(self.points[j:j+2]['accuracy']) + accuracy_error)
                if self.points[j + 1]['distance'] > thresh:
                    starts.insert(0, j + 1)
                    stops.insert(0, stop)
                    stop = j + 1
                    break
            regions.append(StopRegion(self, start, stop))
        return regions

