from ipyleaflet import (
    Map,
    Polyline,
    Popup,
    Marker,
    CircleMarker
)
from ipywidgets import Layout, HTML
import numpy as np
from datetime import datetime, timedelta
from shapely.geometry import Polygon


class MapPlot(Map):
    def __init__(self, height='1250px'):
        super().__init__(
            scroll_wheel_zoom=True,
            layout=Layout(width='100%', height=height)
        )
        self.current_bounds = None

    def add_curve(self, points, color='green'):
        point_list = points.view((np.float64, len(points.dtype.fields)))[:, 0:2].tolist()
        polyline = Polyline(locations=point_list, color=color, weight=1, fill=False)
        self.add(polyline)
        self.set_coordinate_ranges(points)

    def add_labeled_curve(self, trajectory, labels):
        point_list = trajectory.view((np.float64, len(trajectory.dtype.fields)))[:, 0:2].tolist()

        current_label = labels[0]
        current_segment = [point_list[0]]
        for i in range(1, len(labels)):
            if labels[i] != current_label or i == len(labels) - 1:
                color = 'red' if current_label == 1 else 'green' if current_label == 0 else 'blue'
                # add adjacent points
                if current_label == 0 or current_label == 2:
                    last_index = i - len(current_segment) - 1
                    next_index = i
                    if last_index >= 0:
                        current_segment.insert(0, point_list[last_index])
                    if next_index < len(point_list):
                        current_segment.append(point_list[next_index])
                polyline = Polyline(locations=current_segment, color=color, weight=2, fill=False)
                self.add(polyline)
                current_label = labels[i]
                current_segment = []

            current_segment.append(point_list[i])
        self.set_coordinate_ranges(trajectory)

    def add_regions(self, regions, color='red', markers=True):
        for region in regions:
            if hasattr(region, 'geoms'):  # Check if the shape is a multipart geometry
                for part in region.geoms:
                    pc = [(a, b) for b, a in part.coords]
                    polyline = Polyline(
                        locations=pc,
                        color=color,
                        weight=2,
                    )
                    self.add(polyline)
            else:  # Single-part geometry
                if region.shape.geom_type in ['LineString', "Point"]:
                    coords = region.shape.coords
                else:
                    coords = region.shape.exterior.coords
                pc = [(a, b) for b, a in coords]
                polyline = Polyline(
                    locations=pc,
                    color=color,
                    fill_color=color,
                    weight=2,
                    fill=True
                )
                self.add(polyline)
            if markers:
                poi_marker = Marker(location=(region.centroid.coords[0][1], region.centroid.coords[0][0]), draggable=True)
                text = ''
                starts, stops = region.get_stay_time()
                starts = [starts]
                stops = [stops]
                for i in range(len(starts)):
                    enter_time = datetime.utcfromtimestamp(starts[i]) - timedelta(hours=4)
                    exit_time = datetime.utcfromtimestamp(stops[i]) - timedelta(hours=4)
                    time_diff_formatted = str(exit_time - enter_time).split('.')[0]
                    text += (enter_time.strftime("%B %d %H:%M:%S") + " - " + exit_time.strftime("%H:%M:%S")
                             + " (" + time_diff_formatted + ")<br>")
                poi_marker.popup = Popup(
                    location=(region.centroid.coords[0][1], region.centroid.coords[0][0]),
                    child=HTML(value=text),
                )
                self.add(poi_marker)

    def add_points(self, points, labels=None, time_popup=True):
        if labels is None:
            labels = np.zeros(len(points))

        for i in range(len(points)):
            location = (points[i]['lat'], points[i]['lon'])
            color = 'red' if labels[i] == 1 else 'green' if labels[i] == 0 else 'blue'
            marker = CircleMarker(location=location, radius=2, color=color)
            if time_popup:
                marker.popup = Popup(
                    location=location,
                    child=HTML(value=(
                            (datetime.utcfromtimestamp(points[i]['time'])-timedelta(hours=4)).strftime("%B %d %H:%M:%S")
                            + f"<br>Index: {i}"
                            + f"<br>Speed: {points[i]['speed']}"
                            + f"<br>Calculated Speed: {points[i]['distance'] / points[i]['time_diff']}"
                            + f"<br>Accuracy: {points[i]['accuracy']}"
                            + f"<br>Distance: {points[i]['distance']}")),
                    close_button=False,
                    auto_close=False,
                    close_on_escape_key=False
                )
            self.add(marker)
        self.set_coordinate_ranges(points)

    def set_coordinate_ranges(self, points):
        bounds = None
        if isinstance(points, Polygon):
            bounds = points.bounds

        elif isinstance(points, np.ndarray):
            bounds = [points['lat'].max(),
                      points['lat'].min(),
                      points['lon'].max(),
                      points['lon'].min(),
                      ]
        if self.current_bounds is None:
            self.current_bounds = np.array(bounds)
        elif bounds is not None:
            self.current_bounds[0] = max(self.current_bounds[0], bounds[0])
            self.current_bounds[1] = min(self.current_bounds[1], bounds[1])
            self.current_bounds[2] = max(self.current_bounds[2], bounds[2])
            self.current_bounds[3] = min(self.current_bounds[3], bounds[3])

        center_lat = self.current_bounds[:2].mean()
        center_lon = self.current_bounds[2:].mean()
        self.center = (center_lat, center_lon)
