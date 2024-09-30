from shapely.geometry import Point, LineString
import numpy as np
from geopy.distance import distance


class StopRegion:
    def __init__(self, trajectory, start, end):
        self.trajectory = trajectory
        self.entry_indices = np.array([start])
        self.exit_indices = np.array([end])
        self.centroid, self.shape = self.define_shape()

    def union(self, other):
        # Combine stays and keep them sorted
        self.entry_indices = np.sort(np.concatenate((self.entry_indices, other.entry_indices)))
        self.exit_indices = np.sort(np.concatenate((self.exit_indices, other.exit_indices)))

        self.centroid, self.shape = self.define_shape()

        return self

    def percent_intersection(self, other):
        intersection = self.shape.intersection(other.shape)

        if intersection.geom_type in ['LineString', 'MultiLineString']:
            return intersection.length / other.shape.length
        elif intersection.geom_type in ['MultiPoint', 'Point']:
            if len(intersection.coords[:]) > 0 and other.shape.geom_type == 'Point':
                return 1.0
            else:
                return 0.0
        else:
            return intersection.area / other.shape.area

    def distance(self, other, centroid_threshold=200):
        centroid_dist = distance((self.centroid.y, self.centroid.x), (other.centroid.y, other.centroid.x)).meters
        # Thresholded to reduce computations when the regions are far apart
        if centroid_dist > centroid_threshold:
            return centroid_dist
        # Iterates over vertices in a decreasing direction.
        # NOTE: this does not return the minimum distance.
        # It returns the distance between a pair of vertices on the edge with minimum distance.
        # It is close enough and is significantly less computationally intensive.
        else:
            if self.shape.geom_type in ['LineString', "Point"]:
                self_coords = self.shape.coords
            else:
                self_coords = self.shape.exterior.coords[:-1]  # Last point is the same as the first
            if other.shape.geom_type in ['LineString', "Point"]:
                other_coords = other.shape.coords
            else:
                other_coords = other.shape.exterior.coords[:-1]  # Last point is the same as the first
            self_pointer = 0
            other_pointer = 0
            # Clockwise or counter-clockwise iteration
            self_direction = 1 if len(self_coords) > 1 else 0
            other_direction = 1 if len(other_coords) > 1 else 0
            # Prevents infinite looping if there is a line with endpoints equidistant to a point
            self_lap_start = None
            other_lap_start = None

            dist = distance(self_coords[self_pointer], other_coords[other_pointer]).meters
            while self_direction != 0 or other_direction != 0:
                if self_direction != 0:
                    self_pointer = (self_pointer + self_direction) % len(self_coords)
                    if self_pointer == self_lap_start:
                        self_direction = 0
                    new_dist = distance(self_coords[self_pointer], other_coords[other_pointer]).meters
                    if new_dist > dist:
                        if self_lap_start is None:
                            self_direction *= -1
                            self_lap_start = self_pointer
                        else:
                            self_direction = 0
                    elif new_dist < dist:
                        self_lap_start = self_pointer
                        dist = new_dist
                if other_direction != 0:
                    other_pointer = (other_pointer + other_direction) % len(other_coords)
                    if other_pointer == other_lap_start:
                        other_direction = 0
                    new_dist = distance(self_coords[self_pointer], other_coords[other_pointer]).meters
                    if new_dist > dist:
                        if other_lap_start is None:
                            other_direction *= -1
                            other_lap_start = other_pointer
                        else:
                            other_direction = 0
                    elif new_dist < dist:
                        other_lap_start = other_pointer
                        dist = new_dist
            return dist

    def define_shape(self):
        all_points = self.get_all_points()
        lon_lats = [list(i) for i in all_points[['lon', 'lat']]]
        # Outlier rejection
        filtered = np.array(lon_lats)[all_points['accuracy'] <= 60]
        if len(filtered) > 0:
            lon_lats = filtered

        # If first and last points are at the same point, the shape should be a point
        if distance(lon_lats[0], lon_lats[-1]).meters == 0:
            shape = Point(lon_lats[0])
        else:
            shape = LineString(lon_lats).convex_hull

        centroid = shape.centroid
        return centroid, shape

    def get_all_points(self):
        result = []
        for start, stop in zip(self.entry_indices, self.exit_indices):
            # Get the items in the range and extend the result list
            result.append(self.trajectory[start:stop])

        return np.concatenate(result)

    def get_stay_time(self):
        start = self.trajectory[self.entry_indices[0]]['time']
        stop = self.trajectory[self.exit_indices[-1] - 1]['time']
        # Add adjacent time. This is important to get more accurate durations during signal loss.
        if self.entry_indices[0] > 0:
            dist = self.trajectory[self.entry_indices[0]]['distance']
            speed = self.trajectory[self.entry_indices[0] - 1]['speed']
            expected_travel_time = dist / max(speed, 1e-6)
            time_diff = start - self.trajectory[self.entry_indices[0] - 1]['time']
            start -= max(0, time_diff - expected_travel_time)
        if self.exit_indices[-1] < len(self.trajectory):
            dist = self.trajectory[self.exit_indices[-1]]['distance']
            speed = self.trajectory[self.exit_indices[-1]]['speed']
            expected_travel_time = dist / max(speed, 1e-6)
            time_diff = self.trajectory[self.exit_indices[-1]]['time'] - stop
            stop += max(0, time_diff - expected_travel_time)
        return start, stop

    @staticmethod
    def recursive_merge(stop_regions, distance_threshold=None):
        merged = StopRegion.merge_stop_regions(stop_regions, 0.0, distance_threshold)
        if len(merged) == len(stop_regions):
            return stop_regions
        else:
            return StopRegion.recursive_merge(merged, distance_threshold)

    # Function to merge point clouds based if they overlap or if their distances are less than a threshold
    @staticmethod
    def merge_stop_regions(stop_regions, overlap_threshold=0.0, distance_threshold=None):
        if len(stop_regions) == 0:
            return stop_regions
        merged_stops = [stop_regions[0]]
        for stop in stop_regions[1:]:
            merged = False
            percent_intersection = stop.percent_intersection(merged_stops[-1])
            if percent_intersection > overlap_threshold:
                merged_stops[-1] = merged_stops[-1].union(stop)
                merged = True
            elif distance_threshold is not None:
                dist = stop.distance(merged_stops[-1])
                if dist < distance_threshold:
                    merged_stops[-1] = merged_stops[-1].union(stop)
                    merged = True
            # Make a new region if not merged
            if not merged:
                merged_stops.append(stop)
        return merged_stops

    def longer_than(self, duration):
        start, stop = self.get_stay_time()
        return stop - start >= duration
