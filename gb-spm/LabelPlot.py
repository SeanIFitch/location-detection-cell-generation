from MapPlot import MapPlot
from ipyleaflet import CircleMarker, Popup, GeomanDrawControl, Polyline, Marker
from datetime import datetime
import numpy as np
from ipywidgets import HTML


# move is 0/green, stop is 1/red
class LabelPlot(MapPlot):
    def __init__(self,  height='500px'):
        MapPlot.__init__(self, height=height)
        self.points = None
        self.labels = None
        self.markers = None
        self.draw_control = None
        self.visible_start_index = 0
        self.visible_end_index = 0

    def add_points_clickable(self, points, function=None, time_popup=False, labels=None):
        self.points = points
        self.markers = []
        if labels is None:
            self.labels = np.zeros(len(self.points))
        else:
            self.labels = labels

        for i in range(len(self.points)):
            location = (self.points[i]['lat'], self.points[i]['lon'])
            color = 'red' if self.labels[i] == 1 else 'green'
            opacity = 1 if function is None else 0
            marker = CircleMarker(location=location, radius=2, color=color, opacity=opacity, fill_opacity=opacity)
            if time_popup:
                marker.popup = Popup(
                    location=location,
                    child=HTML(value=(
                            datetime.utcfromtimestamp(self.points[i]['time']).strftime("%B %d %H:%M:%S")
                            + f"<br>Index: {i}")),
                    close_button=False,
                    auto_close=False,
                    close_on_escape_key=False
                )
            if function is not None:
                marker.visible = False
                marker.on_click(function)
            self.add(marker)
            self.markers.append(marker)

        self.set_coordinate_ranges(self.points)

    def add_rectangle_tool(self, function):
        self.draw_control = GeomanDrawControl(polyline={}, circle={}, circlemarker={}, marker={}, polygon={})
        self.draw_control.rectangle = {
            "shapeOptions": {
                "color": "#FF0000",
                "weight": 1,
                "opacity": 1.0,
                "fillOpacity": 0.1,
                "snappable": False   # This doesnt work
            },
        }
        self.draw_control.cut = False
        self.draw_control.drag = False
        self.draw_control.rotate = False
        self.draw_control.remove = False
        self.draw_control.edit = False
        self.draw_control.on_draw(function)
        self.add(self.draw_control)

    def show_time(self, start_time, end_time):
        times = self.points['time']
        self.visible_start_index = np.searchsorted(times, start_time, side='left')
        self.visible_end_index = np.searchsorted(times, end_time, side='right')

        for m in self.markers[self.visible_start_index:self.visible_end_index]:
            m.visible = True
            m.opacity = 1
        for m in self.markers[:self.visible_start_index] + self.markers[self.visible_end_index:]:
            m.visible = False
            m.opacity = 0

    def add_labeled_curve(self, trajectory, labels, stop_markers=False):
        point_list = trajectory.view((np.float64, len(trajectory.dtype.fields)))[:, 0:2].tolist()

        current_label = labels[0]
        current_segment = [point_list[0]]
        for i in range(1, len(labels)):
            if labels[i] != current_label or i == len(labels) - 1:
                color = 'red' if current_label == 1 else 'green' if current_label == 0 else 'blue'
                if True and stop_markers and current_label == 1:
                    # Add POI marker
                    location = current_segment[len(current_segment) // 2]
                    poi_marker = Marker(location=location, draggable=True)

                    enter_index = max(0, i - len(current_segment))
                    exit_index = i
                    enter_time = datetime.utcfromtimestamp(trajectory['time'][enter_index])
                    exit_time = datetime.utcfromtimestamp(trajectory['time'][exit_index])
                    time_diff = exit_time - enter_time
                    hours = time_diff.seconds // 3600
                    minutes = (time_diff.seconds % 3600) // 60
                    seconds = time_diff.seconds % 60
                    time_diff_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    times = (enter_time.strftime("%B %d %H:%M:%S") + " - "
                             + exit_time.strftime("%H:%M:%S") + "<br>" + time_diff_formatted)
                    poi_marker.popup = Popup(
                        location=current_segment[-1],
                        child=HTML(value=times),
                        close_button=False,
                        auto_close=False,
                        close_on_escape_key=False
                    )
                    self.add(poi_marker)
                elif True and stop_markers and current_label == 2:
                    # Add POI marker
                    location = current_segment[len(current_segment) // 2]
                    poi_marker = Marker(location=location, draggable=True)

                    enter_index = max(0, i - len(current_segment))
                    exit_index = i
                    enter_time = datetime.utcfromtimestamp(trajectory['time'][enter_index])
                    exit_time = datetime.utcfromtimestamp(trajectory['time'][exit_index])
                    time_diff = exit_time - enter_time
                    hours = time_diff.seconds // 3600
                    minutes = (time_diff.seconds % 3600) // 60
                    seconds = time_diff.seconds % 60
                    time_diff_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    from velocity_test import vector_directionality
                    d = vector_directionality(trajectory[enter_index:exit_index])

                    times = (enter_time.strftime("%B %d %H:%M:%S") + " - "
                             + exit_time.strftime("%H:%M:%S") + "<br>" + time_diff_formatted
                             + "<br>" + str(d))
                    poi_marker.popup = Popup(
                        location=current_segment[-1],
                        child=HTML(value=times),
                        close_button=False,
                        auto_close=False,
                        close_on_escape_key=False
                    )
                    self.add(poi_marker)
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

    def add_shapes(self, shapes, color='red'):
        for shape in shapes:
            if hasattr(shape, 'geoms'):  # Check if the shape is a multi-part geometry
                for part in shape.geoms:
                    pc = [(a, b) for b, a in part.coords]
                    polyline = Polyline(
                        locations=pc,
                        color=color,
                        fill_color=color,
                        weight=2,
                        fill=True
                    )
                    self.add(polyline)
            else:  # Single-part geometry
                pc = [(a, b) for b, a in shape.coords]
                polyline = Polyline(
                    locations=pc,
                    color=color,
                    fill_color=color,
                    weight=2,
                    fill=True
                )
                self.add(polyline)
