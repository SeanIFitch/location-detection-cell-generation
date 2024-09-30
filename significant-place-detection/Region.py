from shapely.geometry import Point, LineString
import numpy as np
from geopy.distance import distance


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


def stop_regions_from_trajectory(trajectory, labels, distance_threshold=500):
    consecutive_points = get_filtered_subtrajectories(trajectory, labels, 1)

    regions = []
    while len(consecutive_points) > 0:
        points = consecutive_points.pop(0)
        for j in range(len(points) - 1):
            # split if points are far apart
            if points[j + 1]['distance'] > min(distance_threshold, points[j]['accuracy'] + points[j]['accuracy'] + 30):
                consecutive_points.insert(0, points[j + 1:])
                points = points[:j + 1]
                break
        regions.append(Region(points, 1))
    return regions


class Region:
    def __init__(self, points, label=1):
        self.points = points
        self.entry_times = np.array([points[0]['time']])
        self.exit_times = np.array([points[-1]['time']])
        self.label = label
        self.centroid, self.shape = self.define_shape()

    def union(self, other, new_label=1):
        self.points = np.append(self.points, other.points)
        self.label = new_label
        self.centroid, self.shape = self.define_shape()

        # Combine stays and keep them sorted
        self.entry_times = np.sort(np.concatenate((self.entry_times, other.entry_times)))
        self.exit_times = np.sort(np.concatenate((self.exit_times, other.exit_times)))

        return self

    def percent_intersection(self, other):
        intersection = self.shape.intersection(other.shape)

        if intersection.geom_type in ['LineString', 'MultiLineString']:
            return intersection.length / min(self.shape.length, other.shape.length)
        elif intersection.geom_type == 'Point' and len(intersection.coords[:]) > 0:
            return 1.0
        elif intersection.geom_type in ['MultiPoint', 'Point']:
            return 0.0
        else:
            return intersection.area / min(self.shape.area, other.shape.area)

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
        lon_lats = [list(i) for i in self.points[['lon', 'lat']]]
        # Outlier rejection for stops
        if self.label == 1:
            lon_lats = np.array(lon_lats)[self.points['accuracy'] <= 60]
            if len(lon_lats) == 0:
                lon_lats = [list(i) for i in self.points[['lon', 'lat']]]

        # If first and last points are at the same point, the shape should be a point
        if distance(lon_lats[0], lon_lats[-1]).meters == 0:
            shape = Point(lon_lats[0])
        elif self.label == 1:
            shape = LineString(lon_lats).convex_hull
        else:
            shape = LineString(lon_lats)

        centroid = shape.centroid
        # Convert to convex hull for stops or linestring for walks/moves
        return centroid, shape

    @staticmethod
    def recursive_merge(stop_regions, distance_threshold=None):
        merged = Region.merge_stop_regions(stop_regions, 0.0, distance_threshold)
        if len(merged) == len(stop_regions):
            return stop_regions
        else:
            return Region.recursive_merge(merged, distance_threshold)

    # Function to merge point clouds based if they overlap or if their distances are less than a threshold
    @staticmethod
    def merge_stop_regions(stop_regions, overlap_threshold=0.0, distance_threshold=None):
        if len(stop_regions) == 0:
            return stop_regions
        merged_stops = [stop_regions[0]]
        for stop in stop_regions[1:]:
            merged = False
            min_distance = None
            min_distance_index = None
            for i in range(len(merged_stops)):
                percent_intersection = stop.percent_intersection(merged_stops[i])
                if percent_intersection > overlap_threshold:
                    merged_stops[i] = merged_stops[i].union(stop)
                    merged = True
                    break
                if distance_threshold is not None:
                    dist = stop.distance(merged_stops[i])
                    if min_distance is None or dist < min_distance:
                        min_distance = dist
                        min_distance_index = i
            # If no intersections, merge with the closest region if under distance_threshold
            if not merged and min_distance is not None and min_distance < distance_threshold:
                merged_stops[min_distance_index] = merged_stops[min_distance_index].union(stop)
                merged = True
            # Make a new region if not merged
            if not merged:
                merged_stops.append(stop)
        return merged_stops

    # Merges all stays within a stop that do not have a stay from another stop in between them
    @staticmethod
    def merge_stay_times(stop_regions, min_time):
        count = len(stop_regions)
        if len(stop_regions) == 1:
            stop_regions[0].entry_times = np.array([stop_regions[0].entry_times[0]])
            stop_regions[0].exit_times = np.array([stop_regions[0].exit_times[-1]])
            return stop_regions
        for i in range(len(stop_regions)):
            other_starts = np.concatenate([other.entry_times for other in stop_regions[:i] + stop_regions[i + 1:]])
            new_entries = [stop_regions[i].entry_times[0]]
            new_exits = []
            for j in range(len(stop_regions[i].entry_times) - 1):
                for other in other_starts:
                    if stop_regions[i].entry_times[j + 1] > other > stop_regions[i].exit_times[j]:
                        new_entries.append(stop_regions[i].entry_times[j + 1])
                        new_exits.append(stop_regions[i].exit_times[j])
                        break
            new_exits.append(stop_regions[i].exit_times[-1])

            stop_regions[i].entry_times = np.array(new_entries)
            stop_regions[i].exit_times = np.array(new_exits)

        # Filter to min_time
        stay_times = np.array([np.max(i.exit_times - i.entry_times) for i in stop_regions])
        stop_regions = list(np.array(stop_regions)[stay_times >= min_time])

        # Recursion because filtering by length could allow more merges
        if count == len(stop_regions):
            # Remove stops under half the min_time
            for r in stop_regions:
                time_filter = r.exit_times - r.entry_times > min_time / 2
                r.entry_times = r.entry_times[time_filter]
                r.exit_times = r.exit_times[time_filter]
            return stop_regions
        else:
            return Region.merge_stay_times(stop_regions, min_time)

