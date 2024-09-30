import numpy as np
from position_fix_utils import distance_between_points
from StopRegion import StopRegion


# Returns significant places
def significant_place_mining(trajectory, cp_indices, r_index, max_dist, max_time, dist_mult, unit='sec'):
    vertex_labels = np.arange(len(cp_indices))
    characteristic_potentials = characteristic_point_potentials(trajectory, cp_indices, r_index, dist_mult)
    stay_times = neighborhood_stay_times(trajectory[cp_indices], r_index, unit=unit)

    # Define weight matrix
    # Only need weights between CPs and their following CPs since the weight of a preceding CP is the same
    # as in the preceding point's following CP
    weight_matrix = np.zeros((len(cp_indices), r_index))
    for i in range(len(cp_indices) - 1):
        for j in range(r_index - max(i + 1 - len(cp_indices) + r_index, 0)):
            mutual_stay_time = np.average([stay_times[i], stay_times[i + j + 1]])
            relative_potential = abs(characteristic_potentials[i] - characteristic_potentials[i + j + 1])
            points = np.array([trajectory[cp_indices[i]], trajectory[cp_indices[i+j+1]]])
            dist = distance_between_points(points) * dist_mult
            weight_matrix[i][j] = mutual_stay_time * relative_potential * np.exp(-dist)

    # Find max weight for each vertex and create an array recording their indices
    max_weight_indices = np.zeros(len(cp_indices)).astype(np.int32)
    for i in range(len(cp_indices)):
        # Find neighborhood weights for vertex i
        earlier_neighbor_weights = np.diagonal(np.fliplr(weight_matrix), offset=r_index - i)
        later_neighbor_weights = weight_matrix[i][:len(cp_indices) - i - 1]
        neighbor_weights = np.concatenate([earlier_neighbor_weights, later_neighbor_weights])

        # Update label of i to that of the max weight vertex
        max_idx = np.argmax(neighbor_weights)
        if max_idx < len(earlier_neighbor_weights):
            max_label_offset = max_idx - len(earlier_neighbor_weights)
        else:
            max_label_offset = max_idx - len(earlier_neighbor_weights) + 1
        max_weight_indices[i] = i + max_label_offset

        # Set its child to itself if max_distance and max_time are exceeded
        if (distance_between_points(trajectory[cp_indices[[i, max_weight_indices[i]]]]) > max_dist and
                abs(np.diff(trajectory[cp_indices[[i, max_weight_indices[i]]]]['time'])) > max_time):
            max_weight_indices[i] = i

    # Update labels
    order = np.argsort(-characteristic_potentials)
    max_iterations = 15
    for it in range(max_iterations):
        changed = False
        for i in order:
            if vertex_labels[i] != vertex_labels[max_weight_indices[i]]:
                changed = True
                vertex_labels[i] = vertex_labels[max_weight_indices[i]]
        if not changed:
            break

    stop_regions = generate_stop_regions(trajectory, cp_indices, vertex_labels)

    return stop_regions


# Returns indices of characteristic points (points where neighborhood_velocity <= max_velocity)
def characteristic_indices(trajectory, r_index, max_velocity, unit='kph'):
    velocities = neighborhood_velocities(trajectory, r_index, unit=unit)
    cp_indices = np.where(velocities <= max_velocity)[0]
    return cp_indices


# Returns total distance traveled over time
def neighborhood_velocities(trajectory, r_index, unit):
    if unit == 'kph':
        dist_unit, time_unit = 'km', 'hr'
    elif unit == 'mps':
        dist_unit, time_unit = 'm', 'sec'
    else:
        raise ValueError('Unit must be kph or mps')

    # Get sum of distances in neighborhood for each point
    distances = distance_between_points(trajectory, unit=dist_unit)
    padded_dist = np.pad(distances, (r_index, r_index), mode='constant', constant_values=0)
    dist_kernel = np.ones(2 * r_index)
    distance_sums = np.convolve(padded_dist, dist_kernel, mode='valid')

    times = neighborhood_stay_times(trajectory, r_index, unit=time_unit)

    return distance_sums / times


# Returns total time of each neighborhood
def neighborhood_stay_times(trajectory, r_index, unit='sec'):
    times = trajectory['time']
    padded_time = np.pad(times, (r_index, r_index), mode='edge')
    time_kernel = np.zeros(2 * r_index + 1)
    time_kernel[0] = 1
    time_kernel[-1] = -1
    time_diffs = np.convolve(padded_time, time_kernel, mode='valid')
    if unit == 'sec':
        return time_diffs
    elif unit == 'min':
        return time_diffs / 60
    elif unit == 'hr':
        return time_diffs / 3600
    else:
        raise ValueError('Unit must be sec, min, or hr.')


# Returns characteristic point potentials of each characteristic point
def characteristic_point_potentials(trajectory, cp_indices, r_index, dist_mult):
    potentials = []
    distances = distance_between_points(trajectory) * dist_mult
    std_dev = np.std(distances)
    for i in range(len(cp_indices)):
        before_in_neighborhood = np.min([r_index, i])
        after_in_neighborhood = np.min([r_index, len(cp_indices) - i + 1])
        start = cp_indices[i] - before_in_neighborhood
        end = cp_indices[i] + after_in_neighborhood

        potential = np.sum(np.exp(-distances[start:end] / std_dev))

        potentials.append(potential)
    return np.array(potentials)


def generate_stop_regions(trajectory, cp_indices,  vertex_labels):
    unique_labels = np.unique(vertex_labels)
    stop_regions = []
    for label in unique_labels:
        points = trajectory[cp_indices[vertex_labels == label]]
        stop_regions.append(StopRegion(points))

    merged = recursive_merge(stop_regions, 50)

    # merged = merge_short_stops(merged, 300, 120)

    merged = merge_stops_in_regions(merged, trajectory, cp_indices, 3, 300)

    # Remove all stops below 5 minutes
    for i in range(len(merged) - 1, -1, -1):
        if merged[i].exit_times[-1] - merged[i].entry_times[0] <= 300:
            merged.pop(i)

    return merged


def recursive_merge(multi_points, threshold):
    merged = merge_stop_regions(multi_points, threshold)
    if len(merged) == len(multi_points):
        return multi_points
    else:
        return recursive_merge(merged, threshold)


# Function to merge point clouds based if they overlap at all or if centroids are close
def merge_stop_regions(stop_regions, distance_threshold):
    merged_stops = [stop_regions[0]]
    for stop in stop_regions[1:]:
        merged = False
        min_distance = None
        min_distance_index = None
        for i in range(len(merged_stops)):
            if stop.intersects(merged_stops[i]):
                merged_stops[i] = merged_stops[i].union(stop)
                merged = True
                break
            distance = stop.centroid_distance(merged_stops[i])
            if min_distance is None or distance < min_distance:
                min_distance = distance
                min_distance_index = i
        # If no intersections, merge with the closest region if under distance_threshold
        if min_distance is not None and min_distance < distance_threshold:
            merged_stops[min_distance_index] = merged_stops[min_distance_index].union(stop)
            merged = True

        # Make a new region if not merged
        if not merged:
            merged_stops.append(stop)
    return merged_stops


def merge_short_stops(stops, duration_threshold, merge_threshold):
    entry_times = []
    exit_times = []
    stop_indices = []
    for i in range(len(stops)):
        entry_times.extend(stops[i].entry_times)
        exit_times.extend(stops[i].exit_times)
        stop_indices.extend([i] * len(stops[i].entry_times))
    entry_times = np.array(entry_times)
    exit_times = np.array(exit_times)
    stop_indices = np.array(stop_indices)

    merged = []
    for i in range(len(stops)):
        if len(stops[i].entry_times) == 1:
            after_times = entry_times - stops[i].exit_times[0]
            before_times = stops[i].entry_times[0] - exit_times
            after_positive = after_times[after_times > 0]
            before_positive = before_times[before_times > 0]

            # do not merge if there is no stop within merge_threshold_time of the current stop
            if np.min(np.concatenate([after_positive, before_positive])) > merge_threshold:
                merged.append(stops[i])
                continue

            if len(after_positive) == 0:
                merge_into = stop_indices[before_times > 0][np.argmin(before_positive)]
            elif len(before_positive) == 0:
                merge_into = stop_indices[after_times > 0][np.argmin(after_positive)]
            elif min(before_positive) <= min(after_positive):
                merge_into = stop_indices[before_times > 0][np.argmin(before_positive)]
            else:
                merge_into = stop_indices[after_times > 0][np.argmin(after_positive)]

            # Merge only times. These stops are usually due to people slowly entering or leaving a location and
            # therefore would add outliers to the plotted location
            stops[merge_into].entry_times.append(stops[i].entry_times[0])
            stops[merge_into].exit_times.append(stops[i].exit_times[0])

        else:
            merged.append(stops[i])
    return merged


# Merge all stops within index_threshold characteristic points or time_threshold seconds of each other
# TODO: make this just be merge 2 stops if there is no stop in between them
def merge_stops_in_regions(stops, trajectory, cp_indices, index_threshold, time_threshold):
    times = trajectory[cp_indices]['time']
    for i in range(len(stops)):
        entry_indices = np.searchsorted(times, stops[i].entry_times)
        exit_indices = np.searchsorted(times, stops[i].exit_times)
        # places where the exit and following entry are within index_threshold characteristic points
        exit_indices_to_remove = np.where(entry_indices[1:] - exit_indices[:-1] <= index_threshold)[0]
        stops[i].entry_times = np.delete(stops[i].entry_times, exit_indices_to_remove + 1)
        stops[i].exit_times = np.delete(stops[i].exit_times, exit_indices_to_remove)
    return stops
