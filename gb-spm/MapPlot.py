from ipyleaflet import (
    Map,
    CircleMarker,
    Polyline,
    Popup,
    Marker,
)
from ipywidgets import Layout, HTML
import numpy as np
from datetime import datetime
import matplotlib.colors as mcolors
from shapely.geometry import Polygon, LineString


class MapPlot(Map):
    def __init__(self, height='1250px'):
        super().__init__(
            scroll_wheel_zoom=True,
            layout=Layout(width='100%', height=height)
        )
        self.current_bounds = None

    def add_points(self, points, time_popup=True, color='blue'):
        for i in range(len(points)):
            location = (points[i]['lat'], points[i]['lon'])
            marker = CircleMarker(location=location, radius=2, color=color)

            if time_popup:
                marker.popup = Popup(
                    location=location,
                    child=HTML(value=(
                            datetime.utcfromtimestamp(points[i]['time']).strftime("%B %d %H:%M:%S")
                            + f"<br>Index: {i}")),
                    close_button=False,
                    auto_close=False,
                    close_on_escape_key=False
                )

            self.add(marker)
        self.set_coordinate_ranges(points)

    def add_curve(self, points, color='blue'):
        point_list = points.view((np.float64, len(points.dtype.fields)))[:, 0:2].tolist()
        polyline = Polyline(locations=point_list, color=color, weight=1, fill=False)
        self.add(polyline)
        self.set_coordinate_ranges(points)

    def add_curve_heat(self, points, keys, normalization='linear'):
        colors = self.get_color_range(keys, normalization)
        point_list = points.view((np.float64, 4))[:, 0:2].tolist()

        # Add circle markers with colors corresponding to the heatmap
        for i in range(len(point_list) - 1):
            polyline = Polyline(locations=point_list[i:i+2], color=colors[i], weight=2, fill=False)
            self.add(polyline)

    def add_points_heat(self, points, keys, time_popup=True, normalization='linear'):
        colors = self.get_color_range(keys, normalization)

        # Add circle markers with colors corresponding to the heatmap
        for i in range(len(points)):
            location = (points[i]['lat'], points[i]['lon'])
            marker = CircleMarker(location=location, radius=2, color=colors[i])

            if time_popup:
                marker.popup = Popup(
                    location=location,
                    child=HTML(value=datetime.utcfromtimestamp(points[i]['time']).strftime("%B %d %H:%M:%S") +
                               f"<br>Key: {keys[i]:.2f}<br>Index: {i}"),
                    close_button=False,
                    auto_close=False,
                    close_on_escape_key=False
                )

            self.add(marker)

        # Update coordinate ranges
        self.set_coordinate_ranges(points)

    def add_stop_region(self, stop_region, color='red', markers=True, draggable=False):
        hull = stop_region.convex_hull()
        if isinstance(hull, LineString):
            polygon_coords = hull.coords
        else:
            polygon_coords = hull.exterior.coords

        pc = [(a, b) for b, a in polygon_coords]
        polyline = Polyline(
            locations=pc,
            color=color,
            fill_color=color,
            weight=2,
            fill=True
        )
        self.add(polyline)
        if markers:
            # Add POI marker
            poi_marker = Marker(
                location=(stop_region.centroid().coords[0][1], stop_region.centroid().coords[0][0]),
                draggable=draggable,
            )
            
            times = "<br>".join([datetime.utcfromtimestamp(stop_region.entry_times[i]).strftime("%B %d %H:%M:%S")
                        + " - "
                        + datetime.utcfromtimestamp(stop_region.exit_times[i]).strftime("%H:%M:%S")
                        for i in range(len(stop_region.entry_times))])
            poi_marker.popup = Popup(
                location=(stop_region.centroid().coords[0][1], stop_region.centroid().coords[0][0]),
                child=HTML(value=times),
                close_button=False,
                auto_close=False,
                close_on_escape_key=False
            )
            self.add(poi_marker)
        self.set_coordinate_ranges(stop_region.points)

    def add_stop_regions_heat(self, stop_regions, keys, normalization='linear', markers=True):
        colors = self.get_color_range(keys, normalization)

        # Add circle markers with colors corresponding to the heatmap
        for i in range(len(stop_regions)):
            self.add_stop_region(stop_regions[i], color=colors[i], markers=markers)

    def add_stop_regions(self, stop_regions, color='blue', markers=True, draggable=False):
        for i in range(len(stop_regions)):
            self.add_stop_region(stop_regions[i], color=color, markers=markers, draggable=draggable)

    @staticmethod
    def get_color_range(keys, normalization='linear'):
        # Determine the range of keys
        min_key = np.min(keys)
        max_key = np.max(keys)

        # Map normalized keys to colors in the heatmap range
        if len(keys) == 1:
            normalized_keys = [1]
        elif normalization == 'linear':
            normalized_keys = (keys - min_key) / (max_key - min_key)
        elif normalization == 'log':
            normalized_keys = np.log(keys - min_key + 1) / np.log(max_key - min_key + 1)
        else:
            raise ValueError("Normalization method must be either 'linear' or 'log'.")
        cmap = mcolors.LinearSegmentedColormap.from_list("", ["blue", "red"])
        colors_rgba = cmap(normalized_keys)
        colors_html = [mcolors.to_hex(color) for color in colors_rgba]
        return colors_html

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
        self.set_center()

    def set_center(self):
        center_lat = self.current_bounds[:2].mean()
        center_lon = self.current_bounds[2:].mean()
        self.center = (center_lat, center_lon)
