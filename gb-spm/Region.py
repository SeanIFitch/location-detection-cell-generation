from shapely.geometry import Point, LineString
import numpy as np
from geopy import distance


def recursive_merge(stop_regions, distance_threshold=0.0):
    merged = merge_stop_regions(stop_regions, distance_threshold=distance_threshold)
    if len(merged) == len(stop_regions):
        return stop_regions
    else:
        return recursive_merge(merged, distance_threshold)


# Function to merge point clouds based if they overlap or if centroids are close
def merge_stop_regions(stop_regions, distance_threshold=0.0, overlap_threshold=0.0):
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
            if distance_threshold > 0.0:
                dist = distance.distance((stop.centroid.y, stop.centroid.x), (merged_stops[i].centroid.y, merged_stops[i].centroid.x)).meters
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


class Region:
    def __init__(self, points, label):
        self.points = points
        self.entry_times = [points[0]['time']]
        self.exit_times = [points[-1]['time']]
        self.label = label

        lon_lats = [list(i) for i in self.points[['lon', 'lat']]]
        dist = distance.distance(self.points[['lon', 'lat']][0], self.points[['lon', 'lat']][-1]).meters
        shape = LineString(lon_lats) if dist != 0 else Point(lon_lats[0])
        self.centroid = shape.centroid
        # Convert to convex hull for stops or linestring for walks/moves
        self.shape = shape.convex_hull if label == 1 else shape

    def union(self, other, new_label=1):
        self.points = np.append(self.points, other.points)
        self.entry_times.extend(other.entry_times)
        self.exit_times.extend(other.exit_times)
        self.label = new_label

        lon_lats = [list(i) for i in self.points[['lon', 'lat']]]
        shape = LineString(lon_lats)
        self.centroid = shape.centroid
        # Convert to convex hull for stops or linestring for walks/moves
        self.shape = shape.convex_hull if new_label == 1 else shape

        return self

    def percent_intersection(self, other):
        intersection = self.shape.intersection(other.shape)

        if intersection.geom_type in ['LineString', 'MultiLineString']:
            print(self.shape.length, self.shape.geom_type, other.shape.length, other.shape.geom_type)
            return intersection.length / min(self.shape.length, other.shape.length)
        elif intersection.geom_type == 'Point':
            return 1.0
        else:
            return intersection.area / min(self.shape.area, other.shape.area)

    def path_intersection(self, path):
        intersection = self.shape.intersection(path.shape)

        if intersection.geom_type in ['LineString', 'MultiLineString']:
            print(intersection.length, path.shape.length, intersection.length / path.shape.length)
            return intersection.length / path.shape.length
        elif intersection.geom_type == 'Point':
            return float(path.shape.geom_type == 'Point')
