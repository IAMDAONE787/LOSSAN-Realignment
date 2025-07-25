import folium
import numpy as np
from utils.engineering_coords import (
    calculate_track_parameters, 
    station_to_gis, 
    parse_station,
    parse_angle,
    calculate_radius_from_degree_of_curve
)
from utils.railway_curve import add_complete_railway_curve_to_map
from utils.tangent_line import add_railway_tangent_to_map

class RailwaySegment:
    """Base class for railway alignment segments"""
    
    def __init__(self, segment_type, name=None, color="#FF7700", weight=8, opacity=1.0):
        self.type = segment_type
        self.name = name or f"{segment_type.capitalize()} segment"
        self.color = color
        self.weight = weight
        self.opacity = opacity
        self.start_point = None
        self.end_point = None
        self.coords = []
        
    def add_to_map(self, m, start_point, bearing_deg):
        """Add the segment to the map and return the end point and bearing"""
        raise NotImplementedError("Subclasses must implement this method")

class TangentSegment(RailwaySegment):
    """Straight line segment in a railway alignment"""
    
    def __init__(self, start_station, end_station, name=None, color="#FF7700", weight=8, opacity=1.0):
        super().__init__("tangent", name, color, weight, opacity)
        self.start_station = start_station
        self.end_station = end_station
        self.start_station_value = parse_station(start_station)
        self.end_station_value = parse_station(end_station)
        self.length_ft = self.end_station_value - self.start_station_value
        self.manual_bearing = None  # Allow for manually setting the bearing
        
    def add_to_map(self, m, start_point, bearing_deg):
        """Add the tangent segment to the map"""
        self.start_point = start_point
        
        # If manual bearing is set, use it instead of the calculated bearing
        actual_bearing = self.manual_bearing if self.manual_bearing is not None else bearing_deg
        
        tangent_coords = add_railway_tangent_to_map(
            m=m,
            start_point=start_point,
            bearing_deg=actual_bearing,
            length_ft=self.length_ft,
            color=self.color,
            weight=self.weight,
            opacity=self.opacity,
            tooltip=f"{self.name} ({self.start_station} to {self.end_station})",
            num_points=20
        )
        
        self.coords = tangent_coords
        self.end_point = tangent_coords[-1]
        
        # Return the manual bearing if set, otherwise use the input bearing
        return self.end_point, actual_bearing

class CurveSegment(RailwaySegment):
    """Spiral-curve-spiral segment in a railway alignment"""
    
    def __init__(self, ts_station, sc_station, cs_station, st_station, 
                 degree_of_curve=None, radius_ft=None, direction="right", 
                 name=None, color="#FF7700", weight=8, opacity=1.0, 
                 add_white_pattern=True, add_markers=True):
        super().__init__("spiral_curve_spiral", name, color, weight, opacity)
        self.ts_station = ts_station
        self.sc_station = sc_station
        self.cs_station = cs_station
        self.st_station = st_station
        
        # Parse stations to numeric values
        self.ts_station_value = parse_station(ts_station)
        self.sc_station_value = parse_station(sc_station)
        self.cs_station_value = parse_station(cs_station)
        self.st_station_value = parse_station(st_station)
        
        # Calculate lengths for each component
        self.entry_spiral_length = self.sc_station_value - self.ts_station_value
        self.circular_arc_length = self.cs_station_value - self.sc_station_value
        self.exit_spiral_length = self.st_station_value - self.cs_station_value
        
        # Parse degree of curve and calculate radius
        if degree_of_curve is not None:
            self.degree_value = parse_angle(degree_of_curve)
            self.radius_ft = calculate_radius_from_degree_of_curve(self.degree_value)
        elif radius_ft is not None:
            self.radius_ft = radius_ft
            self.degree_value = 5729.58 / radius_ft  # Calculate degree of curve from radius
        else:
            raise ValueError("Either degree_of_curve or radius_ft must be provided")
            
        self.direction = direction
        self.add_white_pattern = add_white_pattern
        self.add_markers = add_markers
        
        # Points to be populated when added to map
        self.ts_point = None
        self.sc_point = None
        self.cs_point = None
        self.st_point = None
        
        # Bearings to be calculated
        self.ts_bearing = None
        self.sc_bearing = None
        self.cs_bearing = None
        self.st_bearing = None
        
    def add_to_map(self, m, start_point, bearing_deg):
        """Add the curve segment to the map"""
        self.ts_point = start_point
        self.ts_bearing = bearing_deg
        
        # Create custom tooltips
        tooltips = {
            "entry_spiral": f"{self.name} - Entry Spiral (TS {self.ts_station} to SC {self.sc_station})",
            "circular_curve": f"{self.name} - Circular Curve (SC {self.sc_station} to CS {self.cs_station})",
            "exit_spiral": f"{self.name} - Exit Spiral (CS {self.cs_station} to ST {self.st_station})"
        }
        
        # Add the complete railway curve
        curve_result = add_complete_railway_curve_to_map(
            m=m,
            ts_point=start_point,
            ts_bearing_deg=bearing_deg,
            entry_spiral_length_ft=self.entry_spiral_length,
            circular_arc_length_ft=self.circular_arc_length,
            exit_spiral_length_ft=self.exit_spiral_length,
            radius_ft=self.radius_ft,
            direction=self.direction,
            color=self.color,
            weight=self.weight,
            opacity=self.opacity,
            add_white_pattern=self.add_white_pattern,
            add_markers=self.add_markers,
            tooltips=tooltips
        )
        
        # Store key points and coordinates
        self.sc_point = curve_result["sc_point"]
        self.cs_point = curve_result["cs_point"]
        self.st_point = curve_result["st_point"]
        self.coords = curve_result["all_coords"]
        
        # Calculate bearings at key points
        # Entry spiral deflection
        entry_deflection = (self.entry_spiral_length**2) / (2 * self.radius_ft * self.entry_spiral_length)
        entry_deflection_deg = np.degrees(entry_deflection)
        
        # Circular curve deflection
        circular_deflection_rad = self.circular_arc_length / self.radius_ft
        circular_deflection_deg = np.degrees(circular_deflection_rad)
        
        # Exit spiral deflection
        exit_deflection = (self.exit_spiral_length**2) / (2 * self.radius_ft * self.exit_spiral_length)
        exit_deflection_deg = np.degrees(exit_deflection)
        
        # Calculate bearings based on direction
        if self.direction == "right":
            self.sc_bearing = bearing_deg - entry_deflection_deg
            self.cs_bearing = self.sc_bearing - circular_deflection_deg
            self.st_bearing = self.cs_bearing - exit_deflection_deg
        else:  # left
            self.sc_bearing = bearing_deg + entry_deflection_deg
            self.cs_bearing = self.sc_bearing + circular_deflection_deg
            self.st_bearing = self.cs_bearing + exit_deflection_deg
            
        return self.st_point, self.st_bearing

class TrackTypeSection:
    """Class representing a section of track with a specific construction type"""
    
    def __init__(self, track_type, start_station, end_station, color=None, tooltip=None, depth_info=None, depth_values=None, elevation_values=None):
        """
        Initialize a track type section
        
        Args:
            track_type: Type of track construction (e.g., "Bored Tunnel", "Bridge")
            start_station: Starting station value or string
            end_station: Ending station value or string
            color: Color for this section (optional)
            tooltip: Tooltip text to display on hover (optional)
            depth_info: General information about depth/elevation (optional)
            depth_values: List of (station, depth) tuples for detailed depth profile (optional)
            elevation_values: List of (station, depth, elevation) tuples with elevation relative to sea level (optional)
        """
        self.track_type = track_type
        
        # Parse station values if they are strings
        if isinstance(start_station, str):
            self.start_station_value = parse_station(start_station)
            self.start_station = start_station
        else:
            self.start_station_value = start_station
            self.start_station = f"{int(start_station/100)}+{start_station % 100:02.0f}"
            
        if isinstance(end_station, str):
            self.end_station_value = parse_station(end_station)
            self.end_station = end_station
        else:
            self.end_station_value = end_station
            self.end_station = f"{int(end_station/100)}+{end_station % 100:02.0f}"
        
        self.color = color
        self.depth_info = depth_info
        self.depth_values = depth_values or []
        self.elevation_values = elevation_values or []
        
        # Create tooltip with track type and station range only
        base_tooltip = f"{track_type} ({self.start_station} to {self.end_station})"
        self.tooltip = tooltip or base_tooltip
            
        self.coords = []
        
    def get_depth_at_station(self, station_value):
        """
        Get the depth at a specific station by interpolating between known depth values
        
        Args:
            station_value: Station value to get depth for
            
        Returns:
            Interpolated depth value or None if no depth data available
        """
        if not self.depth_values:
            return None
            
        # Sort depth values by station
        sorted_depths = sorted(self.depth_values, key=lambda x: x[0])
        
        # If station is before first depth point, return first depth
        if station_value <= sorted_depths[0][0]:
            return sorted_depths[0][1]
            
        # If station is after last depth point, return last depth
        if station_value >= sorted_depths[-1][0]:
            return sorted_depths[-1][1]
            
        # Find the two depth points that bracket this station
        for i in range(len(sorted_depths) - 1):
            station1, depth1 = sorted_depths[i]
            station2, depth2 = sorted_depths[i + 1]
            
            if station1 <= station_value <= station2:
                # Linear interpolation between the two points
                if station2 == station1:  # Avoid division by zero
                    return depth1
                    
                ratio = (station_value - station1) / (station2 - station1)
                return depth1 + ratio * (depth2 - depth1)
                
        return None
    
    def get_elevation_at_station(self, station_value):
        """
        Get the elevation at a specific station by interpolating between known elevation values
        
        Args:
            station_value: Station value to get elevation for
            
        Returns:
            Tuple of (depth_below_ground, elevation) or None if no elevation data available
        """
        if not self.elevation_values:
            return None
            
        # Sort elevation values by station
        sorted_elevs = sorted(self.elevation_values, key=lambda x: x[0])
        
        # If station is before first elevation point, return first values
        if station_value <= sorted_elevs[0][0]:
            return sorted_elevs[0][1], sorted_elevs[0][2]
            
        # If station is after last elevation point, return last values
        if station_value >= sorted_elevs[-1][0]:
            return sorted_elevs[-1][1], sorted_elevs[-1][2]
            
        # Find the two elevation points that bracket this station
        for i in range(len(sorted_elevs) - 1):
            station1, depth1, elev1 = sorted_elevs[i]
            station2, depth2, elev2 = sorted_elevs[i + 1]
            
            if station1 <= station_value <= station2:
                # Linear interpolation between the two points
                if station2 == station1:  # Avoid division by zero
                    return depth1, elev1
                    
                ratio = (station_value - station1) / (station2 - station1)
                depth = depth1 + ratio * (depth2 - depth1)
                elev = elev1 + ratio * (elev2 - elev1)
                return depth, elev
                
        return None
        
    def add_to_map(self, m, coords, color=None, weight=7, opacity=0.9, add_ant_path=True, alignment=None):
        """
        Add this track section to the map
        
        Args:
            m: Folium map object
            coords: List of coordinates for this section
            color: Override color (optional)
            weight: Line weight
            opacity: Line opacity
            add_ant_path: Whether to add animated ant path
            alignment: The parent RailwayAlignment object (optional)
        """
        self.coords = coords
        use_color = color or self.color
        
        # First add the base polyline with the general tooltip
        folium.PolyLine(
            locations=coords,
            color=use_color,
            weight=weight,
            opacity=opacity,
            tooltip=self.tooltip,
            className="track-segment"
        ).add_to(m)
        
        # Generate detailed tooltips for each segment at 5-foot intervals
        if alignment and len(coords) > 1:
            # Check if track elevation points exist
            if not alignment.track_elevation_points:
                return coords
                
            # Calculate approximate station values for each coordinate
            section_length = self.end_station_value - self.start_station_value
            
            # Create tooltip points every 5 feet
            interval = 5  # 5-foot intervals
            num_points = int(section_length / interval) + 1
            
            for i in range(num_points):
                station = self.start_station_value + i * interval
                
                # Skip if station is beyond the end
                if station > self.end_station_value:
                    continue
                
                # Calculate position along the path (linear interpolation)
                ratio = (station - self.start_station_value) / section_length
                
                # Get the coordinates for this point
                if ratio <= 0:
                    point_coords = coords[0]
                elif ratio >= 1:
                    point_coords = coords[-1]
                else:
                    # Find the segment containing this point
                    segment_idx = int(ratio * (len(coords) - 1))
                    segment_ratio = (ratio * (len(coords) - 1)) - segment_idx
                    
                    # Interpolate between the two points
                    start_lat, start_lon = coords[segment_idx]
                    end_lat, end_lon = coords[segment_idx + 1]
                    
                    point_lat = start_lat + segment_ratio * (end_lat - start_lat)
                    point_lon = start_lon + segment_ratio * (end_lon - start_lon)
                    point_coords = (point_lat, point_lon)
                
                # Format station for display
                station_display = f"{int(station/100)}+{station % 100:02.0f}"
                
                # Get track elevation from alignment
                track_elevation = alignment.get_track_elevation_at_station(station)
                
                if track_elevation is not None:
                    # Round to nearest 5 feet
                    rounded_elevation = round(track_elevation / 5) * 5
                    
                    # Create tooltip with track type, station and elevation
                    segment_tooltip = f"{self.track_type}<br>Station {station_display}<br>Elevation: {rounded_elevation} ft"
                    
                    # Add tooltip marker with small visible circle
                    folium.CircleMarker(
                        location=point_coords,
                        radius=1,  # Small circle
                        color=use_color,
                        fill=True,
                        fill_color=use_color,
                        fill_opacity=0.5,
                        weight=1,
                        opacity=0.5,
                        tooltip=segment_tooltip
                    ).add_to(m)
        
        # Add animated ant path if requested
        if add_ant_path:
            from folium.plugins import AntPath
            AntPath(
                locations=coords,
                dash_array=[10, 20],
                delay=800,
                color=use_color,
                pulseColor='white',
                paused=False,
                weight=5,
                opacity=opacity,
                tooltip=self.tooltip
            ).add_to(m)
            
        return coords

class RailwayAlignment:
    """Class representing a complete railway alignment with multiple segments"""
    
    def __init__(self, name="Railway Alignment", color="#FF7700"):
        self.name = name
        self.color = color
        self.segments = []
        self.segment_coords = []
        self.all_coords = []
        self.reference_points = {}
        
        # Track type sections
        self.track_type_sections = []
        self.track_types = {
            "Standard Track": [],
            "Bridge": [],
            "Cut and Cover Tunnel": [],
            "Bored Tunnel": [],
            "U-Section": [],
            "Elevated": []
        }
        
        # Elevation data
        self.elevation_points = []  # List of (station, elevation) tuples for ground elevation relative to sea level
        self.track_elevation_points = []  # List of (station, elevation) tuples for track elevation relative to sea level
        self.track_relative_elevation_points = []  # List of (station, relative_elevation) tuples for track elevation relative to ground
    
    def add_reference_point(self, name, coords, station_value):
        """Add a reference point with known coordinates and station value"""
        self.reference_points[name] = {
            "coords": coords,
            "station": station_value
        }
        
    def add_segment(self, segment):
        """Add a segment to the alignment"""
        self.segments.append(segment)
        
    def add_tangent(self, start_station, end_station, name=None):
        """Add a tangent segment to the alignment"""
        segment = TangentSegment(
            start_station=start_station,
            end_station=end_station,
            name=name or f"Tangent {len(self.segments)+1}",
            color=self.color
        )
        self.add_segment(segment)
        return segment
        
    def add_curve(self, ts_station, sc_station, cs_station, st_station, 
                 degree_of_curve=None, radius_ft=None, direction="right", name=None):
        """Add a curve segment to the alignment"""
        segment = CurveSegment(
            ts_station=ts_station,
            sc_station=sc_station,
            cs_station=cs_station,
            st_station=st_station,
            degree_of_curve=degree_of_curve,
            radius_ft=radius_ft,
            direction=direction,
            name=name or f"Curve {len(self.segments)+1}",
            color=self.color,
            add_markers=False,
            add_white_pattern=False
        )
        self.add_segment(segment)
        return segment
    
    def add_track_type_section(self, track_type, start_station, end_station, color=None, tooltip=None, depth_info=None, depth_values=None, elevation_values=None):
        """
        Add a track type section to the alignment
        
        Args:
            track_type: Type of track construction (e.g., "Bored Tunnel", "Bridge")
            start_station: Starting station value or string
            end_station: Ending station value or string
            color: Color for this section (optional)
            tooltip: Tooltip text to display on hover (optional)
            depth_info: General information about depth/elevation (e.g., "-100 ft", "At grade", "+30 ft")
            depth_values: List of (station, depth) tuples for detailed depth profile
            elevation_values: List of (station, depth, elevation) tuples with elevation relative to sea level
        
        Returns:
            The created TrackTypeSection object
        """
        section = TrackTypeSection(
            track_type=track_type,
            start_station=start_station,
            end_station=end_station,
            color=color or self.color,
            tooltip=tooltip,
            depth_info=depth_info,
            depth_values=depth_values,
            elevation_values=elevation_values
        )
        
        self.track_type_sections.append(section)
        
        # Add to the appropriate track type list
        if track_type in self.track_types:
            self.track_types[track_type].append(section)
        else:
            self.track_types[track_type] = [section]
            
        return section
        
    def set_elevation_profile(self, elevation_points):
        """
        Set the ground elevation profile for the entire alignment
        
        Args:
            elevation_points: List of (station, elevation) tuples where elevation is in feet relative to sea level
        """
        # Sort elevation points by station
        self.elevation_points = sorted(elevation_points, key=lambda x: x[0])
    
    def set_track_elevation_profile(self, track_elevation_points):
        """
        Set the track elevation profile for the entire alignment
        
        Args:
            track_elevation_points: List of (station, elevation) tuples where elevation is in feet relative to sea level
        """
        # Sort track elevation points by station
        self.track_elevation_points = sorted(track_elevation_points, key=lambda x: x[0])
        
        # Calculate relative elevation (track height relative to ground)
        self.track_relative_elevation_points = []
        
        for station, track_elev in self.track_elevation_points:
            # Get ground elevation at this station
            ground_elev = self.get_elevation_at_station(station)
            
            if ground_elev is not None:
                # Calculate relative elevation (positive = above ground, negative = below ground)
                relative_elev = track_elev - ground_elev
                self.track_relative_elevation_points.append((station, relative_elev))
    
    def get_elevation_at_station(self, station_value):
        """
        Get the ground elevation at a specific station by interpolating between known elevation points
        
        Args:
            station_value: Station value to get elevation for
            
        Returns:
            Interpolated elevation value in feet relative to sea level or None if no elevation data
        """
        if not self.elevation_points:
            return None
            
        # If station is before first elevation point, return first elevation
        if station_value <= self.elevation_points[0][0]:
            return self.elevation_points[0][1]
            
        # If station is after last elevation point, return last elevation
        if station_value >= self.elevation_points[-1][0]:
            return self.elevation_points[-1][1]
            
        # Find the two elevation points that bracket this station
        for i in range(len(self.elevation_points) - 1):
            station1, elev1 = self.elevation_points[i]
            station2, elev2 = self.elevation_points[i + 1]
            
            if station1 <= station_value <= station2:
                # Linear interpolation between the two points
                if station2 == station1:  # Avoid division by zero
                    return elev1
                    
                ratio = (station_value - station1) / (station2 - station1)
                return elev1 + ratio * (elev2 - elev1)
                
        return None
    
    def get_track_elevation_at_station(self, station_value):
        """
        Get the track elevation at a specific station by interpolating between known track elevation points
        
        Args:
            station_value: Station value to get track elevation for
            
        Returns:
            Interpolated track elevation value in feet relative to sea level or None if no track elevation data
        """
        if not self.track_elevation_points:
            return None
            
        # If station is before first track elevation point, return first elevation
        if station_value <= self.track_elevation_points[0][0]:
            return self.track_elevation_points[0][1]
            
        # If station is after last track elevation point, return last elevation
        if station_value >= self.track_elevation_points[-1][0]:
            return self.track_elevation_points[-1][1]
            
        # Find the two track elevation points that bracket this station
        for i in range(len(self.track_elevation_points) - 1):
            station1, elev1 = self.track_elevation_points[i]
            station2, elev2 = self.track_elevation_points[i + 1]
            
            if station1 <= station_value <= station2:
                # Linear interpolation between the two points
                if station2 == station1:  # Avoid division by zero
                    return elev1
                    
                ratio = (station_value - station1) / (station2 - station1)
                return elev1 + ratio * (elev2 - elev1)
                
        return None
    
    def get_track_relative_elevation_at_station(self, station_value):
        """
        Get the track elevation relative to ground at a specific station
        
        Args:
            station_value: Station value to get relative elevation for
            
        Returns:
            Track elevation relative to ground (positive = above ground, negative = below ground) or None if data unavailable
        """
        if not self.track_relative_elevation_points:
            # If we have both track and ground elevation, calculate it on the fly
            track_elev = self.get_track_elevation_at_station(station_value)
            ground_elev = self.get_elevation_at_station(station_value)
            
            if track_elev is not None and ground_elev is not None:
                return track_elev - ground_elev
            
            return None
            
        # If station is before first relative elevation point, return first value
        if station_value <= self.track_relative_elevation_points[0][0]:
            return self.track_relative_elevation_points[0][1]
            
        # If station is after last relative elevation point, return last value
        if station_value >= self.track_relative_elevation_points[-1][0]:
            return self.track_relative_elevation_points[-1][1]
            
        # Find the two relative elevation points that bracket this station
        for i in range(len(self.track_relative_elevation_points) - 1):
            station1, rel_elev1 = self.track_relative_elevation_points[i]
            station2, rel_elev2 = self.track_relative_elevation_points[i + 1]
            
            if station1 <= station_value <= station2:
                # Linear interpolation between the two points
                if station2 == station1:  # Avoid division by zero
                    return rel_elev1
                    
                ratio = (station_value - station1) / (station2 - station1)
                return rel_elev1 + ratio * (rel_elev2 - rel_elev1)
                
        return None
    
    def generate_elevation_based_depths(self, start_station, end_station, track_depths, interval=10):
        """
        Generate depth values based on track depth below ground and ground elevation
        
        Args:
            start_station: Starting station (string or numeric)
            end_station: Ending station (string or numeric)
            track_depths: List of (station, depth_below_ground) tuples where depth is positive for below ground
            interval: Station interval in feet (default: 10 ft)
            
        Returns:
            List of (station, depth, elevation) tuples where:
                - station is the station value
                - depth is the depth below ground (positive for below ground)
                - elevation is the absolute elevation relative to sea level
        """
        # Parse station values if they are strings
        if isinstance(start_station, str):
            start_station_value = parse_station(start_station)
        else:
            start_station_value = start_station
            
        if isinstance(end_station, str):
            end_station_value = parse_station(end_station)
        else:
            end_station_value = end_station
            
        # Sort track depths by station
        sorted_depths = sorted(track_depths, key=lambda x: x[0]) if track_depths else []
        
        # Generate stations at regular intervals
        stations = []
        current_station = start_station_value
        while current_station <= end_station_value:
            stations.append(current_station)
            current_station += interval
            
        # Add end station if not included
        if end_station_value not in stations:
            stations.append(end_station_value)
            
        # Generate depth and elevation values for each station
        result = []
        track_elevation_points = []  # For updating track elevation profile
        
        for station in stations:
            # Get ground elevation at this station
            ground_elevation = self.get_elevation_at_station(station)
            
            # Get depth below ground at this station (interpolate if needed)
            depth_below_ground = None
            
            if sorted_depths:
                # If station is before first depth point
                if station <= sorted_depths[0][0]:
                    depth_below_ground = sorted_depths[0][1]
                # If station is after last depth point
                elif station >= sorted_depths[-1][0]:
                    depth_below_ground = sorted_depths[-1][1]
                else:
                    # Find the two depth points that bracket this station
                    for i in range(len(sorted_depths) - 1):
                        s1, d1 = sorted_depths[i]
                        s2, d2 = sorted_depths[i + 1]
                        
                        if s1 <= station <= s2:
                            # Linear interpolation
                            if s2 == s1:  # Avoid division by zero
                                depth_below_ground = d1
                            else:
                                ratio = (station - s1) / (s2 - s1)
                                depth_below_ground = d1 + ratio * (d2 - d1)
                            break
            
            # Calculate absolute elevation if both ground elevation and depth are available
            absolute_elevation = None
            if ground_elevation is not None and depth_below_ground is not None:
                absolute_elevation = ground_elevation - depth_below_ground
                
                # Store track elevation for later use
                track_elevation_points.append((station, absolute_elevation))
                
            result.append((station, depth_below_ground, absolute_elevation))
            
        # Update track elevation profile with the new data
        if track_elevation_points:
            # Merge with existing track elevation points if any
            if self.track_elevation_points:
                # Remove any existing points in the range we're updating
                self.track_elevation_points = [
                    (s, e) for s, e in self.track_elevation_points 
                    if s < start_station_value or s > end_station_value
                ]
                # Add the new points
                self.track_elevation_points.extend(track_elevation_points)
                # Sort by station
                self.track_elevation_points.sort(key=lambda x: x[0])
            else:
                # Just use the new points
                self.track_elevation_points = track_elevation_points
            
            # Update relative elevation points
            self.set_track_elevation_profile(self.track_elevation_points)
            
        return result
        
    def generate_depth_values(self, start_station, end_station, depth_start, depth_end, interval=10):
        """
        Generate a list of depth values at regular intervals between start and end stations
        
        Args:
            start_station: Starting station (string or numeric)
            end_station: Ending station (string or numeric)
            depth_start: Depth at starting station (numeric)
            depth_end: Depth at ending station (numeric)
            interval: Station interval in feet (default: 10 ft)
            
        Returns:
            List of (station, depth) tuples
        """
        # Parse station values if they are strings
        if isinstance(start_station, str):
            start_station_value = parse_station(start_station)
        else:
            start_station_value = start_station
            
        if isinstance(end_station, str):
            end_station_value = parse_station(end_station)
        else:
            end_station_value = end_station
            
        # Calculate number of intervals
        length = end_station_value - start_station_value
        num_intervals = int(length / interval) + 1
        
        # Generate depth values with linear interpolation
        depth_values = []
        
        for i in range(num_intervals):
            station = start_station_value + i * interval
            if station > end_station_value:
                break
                
            # Linear interpolation for depth
            ratio = i * interval / length if length > 0 else 0
            depth = depth_start + ratio * (depth_end - depth_start)
            
            depth_values.append((station, round(depth, 1)))
            
        # Add the end station if it's not already included
        if end_station_value not in [station for station, _ in depth_values]:
            depth_values.append((end_station_value, depth_end))
            
        return depth_values
    
    def get_coordinates_for_station_range(self, start_station, end_station):
        """
        Get coordinates for a range of stations
        
        Args:
            start_station: Starting station value
            end_station: Ending station value
            
        Returns:
            List of coordinate tuples within the station range
        """
        if not self.all_coords:
            raise ValueError("Alignment must be added to map first")
            
        # Convert station strings to values if needed
        if isinstance(start_station, str):
            start_station_value = parse_station(start_station)
        else:
            start_station_value = start_station
            
        if isinstance(end_station, str):
            end_station_value = parse_station(end_station)
        else:
            end_station_value = end_station
        
        # Find coordinates within the station range
        coords = []
        
        # Start at the first segment's starting station instead of 0
        if self.segments:
            alignment_start_station = self.segments[0].start_station_value
            current_station = alignment_start_station
        
        else:
            current_station = 0
        
        for i, segment in enumerate(self.segments):
            segment_start_station = current_station
            
            if segment.type == "tangent":
                segment_end_station = segment_start_station + segment.length_ft
            elif segment.type == "spiral_curve_spiral":
                segment_end_station = segment_start_station + segment.entry_spiral_length + segment.circular_arc_length + segment.exit_spiral_length
            else:
                segment_end_station = segment_start_station  # Unknown segment type
                
            # Check if this segment overlaps with our range
            if segment_end_station >= start_station_value and segment_start_station <= end_station_value:
                # Calculate percentage along segment for start and end points
                segment_coords = self.segment_coords[i]
                
                if segment_start_station <= start_station_value <= segment_end_station:
                    # Start point is in this segment
                    segment_length = segment_end_station - segment_start_station
                    if segment_length > 0:  # Avoid division by zero
                        start_pct = (start_station_value - segment_start_station) / segment_length
                        start_idx = int(start_pct * (len(segment_coords) - 1))
                    else:
                        start_idx = 0
                else:
                    # Start point is before this segment
                    start_idx = 0
                    
                if segment_start_station <= end_station_value <= segment_end_station:
                    # End point is in this segment
                    segment_length = segment_end_station - segment_start_station
                    if segment_length > 0:  # Avoid division by zero
                        end_pct = (end_station_value - segment_start_station) / segment_length
                        end_idx = int(end_pct * (len(segment_coords) - 1)) + 1  # +1 to include the end point
                    else:
                        end_idx = len(segment_coords)
                else:
                    # End point is after this segment
                    end_idx = len(segment_coords)
                
                # Ensure indices are within bounds
                start_idx = max(0, min(start_idx, len(segment_coords) - 1))
                end_idx = max(start_idx + 1, min(end_idx, len(segment_coords)))
                
                # Add the coordinates within the range
                coords.extend(segment_coords[start_idx:end_idx])
                
            current_station = segment_end_station
            
        return coords
    
    def render_track_type_sections(self, m):
        """
        Render all track type sections on the map
        
        Args:
            m: Folium map object
        """
        for section in self.track_type_sections:
            coords = self.get_coordinates_for_station_range(
                section.start_station_value, 
                section.end_station_value
            )
            if coords:
                # Add the section with detailed tooltips
                section.add_to_map(
                    m=m,
                    coords=coords,
                    color=section.color or self.color,
                    weight=8,  # Thicker line for better visibility
                    opacity=0.8,  # Slightly more opaque
                    add_ant_path=True,
                    alignment=self  # Pass the alignment reference
                )

                # Add animated path on top
                from folium.plugins import AntPath
                AntPath(
                    locations=coords,
                    dash_array=[10, 20],
                    delay=800,
                    color=section.color or self.color,
                    pulseColor='white',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip=section.tooltip
                ).add_to(m)
    
    def calculate_track_params(self, ref_point1_name, ref_point2_name):
        """Calculate track parameters based on two reference points"""
        ref_point1 = self.reference_points.get(ref_point1_name)
        ref_point2 = self.reference_points.get(ref_point2_name)
        
        if not ref_point1 or not ref_point2:
            raise ValueError(f"Reference points {ref_point1_name} and/or {ref_point2_name} not found")
            
        track_params = calculate_track_parameters(
            point1=ref_point1["coords"],
            station1=ref_point1["station"],
            point2=ref_point2["coords"],
            station2=ref_point2["station"]
        )
        
        return track_params
        
    def add_to_map(self, m, start_ref_point_name=None, track_params=None, start_station=None, add_markers=False, hide_technical_info=False):
        """Add the entire alignment to the map
        
        Args:
            m: Folium map object
            start_ref_point_name: Name of the reference point to start from
            track_params: Track parameters from calculate_track_params
            start_station: Starting station value (optional)
            add_markers: Whether to add markers for reference points
            hide_technical_info: Whether to hide technical information about tangents and curves
        """
        if not self.segments:
            raise ValueError("No segments added to alignment")
            
        # If start_ref_point_name is provided, calculate the start point
        if start_ref_point_name:
            ref_point = self.reference_points.get(start_ref_point_name)
            if not ref_point:
                raise ValueError(f"Reference point {start_ref_point_name} not found")
                
            if not track_params:
                raise ValueError("track_params must be provided with start_ref_point_name")
                
            if not start_station:
                start_station = self.segments[0].start_station_value
                
            # Calculate the start point from the reference point
            current_point = station_to_gis(
                ref_point["coords"], 
                ref_point["station"], 
                start_station, 
                track_params
            )
            
            # Initial bearing from the track parameters
            current_bearing = track_params['bearing_deg']
        else:
            # If no reference point is provided, use the first segment's start point
            current_point = self.segments[0].start_point
            current_bearing = 0  # Default bearing if not provided
            
            if not current_point:
                raise ValueError("No start point provided for the alignment")
        
        # If we're hiding technical info, add a simple line for the entire alignment
        if hide_technical_info:
            # Process each segment to collect coordinates without adding to map
            self.segment_coords = []
            self.all_coords = []
            
            for segment in self.segments:
                # Calculate the segment's coordinates without adding to map
                if segment.type == "tangent":
                    # For tangents, use add_railway_tangent_to_map but don't add to map
                    from utils.tangent_line import add_railway_tangent_to_map
                    segment_coords = add_railway_tangent_to_map(
                        m=None,  # Don't add to map
                        start_point=current_point,
                        bearing_deg=current_bearing if segment.manual_bearing is None else segment.manual_bearing,
                        length_ft=segment.length_ft,
                        num_points=20
                    )
                    segment.coords = segment_coords
                    
                    # Update current_point and current_bearing for next segment
                    current_point = segment_coords[-1]
                    current_bearing = current_bearing if segment.manual_bearing is None else segment.manual_bearing
                    
                elif segment.type == "spiral_curve_spiral":
                    # For curves, use add_complete_railway_curve_to_map but don't add to map
                    from utils.railway_curve import add_complete_railway_curve_to_map
                    curve_result = add_complete_railway_curve_to_map(
                        m=None,  # Don't add to map
                        ts_point=current_point,
                        ts_bearing_deg=current_bearing,
                        entry_spiral_length_ft=segment.entry_spiral_length,
                        circular_arc_length_ft=segment.circular_arc_length,
                        exit_spiral_length_ft=segment.exit_spiral_length,
                        radius_ft=segment.radius_ft,
                        direction=segment.direction,
                        add_markers=False
                    )
                    
                    segment.coords = curve_result["all_coords"]
                    
                    # Update current_point and current_bearing for next segment
                    current_point = curve_result["st_point"]
                    
                    # Calculate the final bearing
                    if segment.direction == "right":
                        entry_deflection = np.degrees((segment.entry_spiral_length**2) / (2 * segment.radius_ft * segment.entry_spiral_length))
                        circular_deflection = np.degrees(segment.circular_arc_length / segment.radius_ft)
                        exit_deflection = np.degrees((segment.exit_spiral_length**2) / (2 * segment.radius_ft * segment.exit_spiral_length))
                        current_bearing = current_bearing - entry_deflection - circular_deflection - exit_deflection
                    else:  # left
                        entry_deflection = np.degrees((segment.entry_spiral_length**2) / (2 * segment.radius_ft * segment.entry_spiral_length))
                        circular_deflection = np.degrees(segment.circular_arc_length / segment.radius_ft)
                        exit_deflection = np.degrees((segment.exit_spiral_length**2) / (2 * segment.radius_ft * segment.exit_spiral_length))
                        current_bearing = current_bearing + entry_deflection + circular_deflection + exit_deflection
                
                # Add segment coordinates to the list
                self.segment_coords.append(segment.coords)
                self.all_coords.extend(segment.coords)
            
            # Add a single polyline for the entire alignment with a generic tooltip
            folium.PolyLine(
                locations=self.all_coords,
                color=self.color,
                weight=5,
                opacity=0.7,
                tooltip=self.name
            ).add_to(m)
            
        else:
            # Process each segment and add to the map with full technical details
            for segment in self.segments:
                # Add segment to map and get the end point and bearing
                end_point, end_bearing = segment.add_to_map(m, current_point, current_bearing)
                
                # Update current point and bearing for the next segment
                current_point = end_point
                current_bearing = end_bearing
                
                # Add segment coordinates to the list
                self.segment_coords.append(segment.coords)
                self.all_coords.extend(segment.coords)
            
        # Add markers for reference points if requested
        if add_markers:
            for name, ref_point in self.reference_points.items():
                folium.Marker(
                    ref_point["coords"],
                    tooltip=f"Reference: {name} (STA {ref_point['station']})",
                    icon=folium.Icon(color="black", icon="map-pin", prefix="fa")
                ).add_to(m)
        
        # Render track type sections if any exist
        if self.track_type_sections:
            self.render_track_type_sections(m)
            
        return self.all_coords 

    def add_track_width_zone(self, m, buffer_width_ft=84.0, opacity=0.2):
        """
        Add a semi-transparent buffer zone around the track alignment
        
        Args:
            m: Folium map object
            buffer_width_ft: Width of the buffer in feet from track centerline
            opacity: Opacity of the buffer fill (0-1)
        """
        if not self.all_coords or len(self.all_coords) < 2:
            return
        
        # Convert buffer width from feet to approximate latitude degrees
        # 1 degree of latitude is roughly 364,000 feet (varies slightly by location)
        buffer_deg = buffer_width_ft / 364000
        
        # Performance optimization: Create fewer, larger polygons by grouping segments
        # Use a smaller stride to reduce coarseness while maintaining performance
        stride = max(1, len(self.all_coords) // 200)  # Use more points for smoother buffers
        simplified_coords = self.all_coords[::stride]
        
        # Ensure the last point is included
        if self.all_coords[-1] not in simplified_coords:
            simplified_coords.append(self.all_coords[-1])
        
        # Create polygon buffers for chunks of the track rather than individual segments
        # Use overlapping chunks to ensure connection between buffer sections
        chunk_size = 15  # Number of points per buffer polygon
        overlap = 3      # Number of points to overlap between chunks
        
        for i in range(0, len(simplified_coords) - 1, chunk_size - overlap):
            chunk_end = min(i + chunk_size, len(simplified_coords))
            chunk = simplified_coords[i:chunk_end]
            
            if len(chunk) < 2:
                continue
                
            # Create left and right sides of the buffer
            left_side = []
            right_side = []
            
            # Process each segment in the chunk
            for j in range(len(chunk) - 1):
                p1 = chunk[j]
                p2 = chunk[j + 1]
                
                # Calculate perpendicular vector
                dx = p2[0] - p1[0]  # Change in latitude
                dy = p2[1] - p1[1]  # Change in longitude
                
                # Normalize and rotate by 90 degrees for perpendicular
                length = (dx**2 + dy**2)**0.5
                if length > 0:
                    nx = -dy / length
                    ny = dx / length
                else:
                    continue
                    
                # Add points to left and right sides
                left_side.append((p1[0] + nx * buffer_deg, p1[1] + ny * buffer_deg))
                right_side.insert(0, (p1[0] - nx * buffer_deg, p1[1] - ny * buffer_deg))
                
                # Add the last point of the chunk
                if j == len(chunk) - 2:
                    left_side.append((p2[0] + nx * buffer_deg, p2[1] + ny * buffer_deg))
                    right_side.insert(0, (p2[0] - nx * buffer_deg, p2[1] - ny * buffer_deg))
            
            # Combine left and right sides to form a complete polygon
            buffer_polygon = left_side + right_side
            
            # Add the buffer polygon to the map with zoom control
            folium.Polygon(
                locations=buffer_polygon,
                color=self.color,
                weight=1,
                fill=True,
                fill_color=self.color,
                fill_opacity=opacity,
                opacity=0.4,
                # Remove tooltip to prevent hover display
                # Add an ID for potential JS-based optimization
                name=f"buffer_{self.name.replace(' ', '_')}_{i}"
            ).add_to(m)
            
    def generate_track_elevation_values(self, start_station, end_station, elevation_start, elevation_end, interval=10, track_distance=None):
        """
        Generate track elevation values at regular intervals with linear interpolation
        
        Args:
            start_station: Starting station (string or numeric)
            end_station: Ending station (string or numeric)
            elevation_start: Track elevation at starting station (feet above sea level)
            elevation_end: Track elevation at ending station (feet above sea level)
            interval: Station interval in feet (default: 10 ft)
            track_distance: Actual track distance in feet (optional, defaults to station difference)
                           Use this when the actual track length differs from the station difference
                           due to curves, spirals, or other alignment features
            
        Returns:
            List of (station, elevation) tuples
        """
        # Parse station values if they are strings
        if isinstance(start_station, str):
            start_station_value = parse_station(start_station)
        else:
            start_station_value = start_station
            
        if isinstance(end_station, str):
            end_station_value = parse_station(end_station)
        else:
            end_station_value = end_station
            
        # Calculate station distance
        station_distance = end_station_value - start_station_value
        
        # Use provided track distance if given, otherwise use station difference
        actual_distance = track_distance if track_distance is not None else station_distance
        
        # Calculate number of intervals
        num_intervals = int(station_distance / interval) + 1
        
        # Calculate elevation change per unit distance
        if actual_distance > 0:
            elevation_slope = (elevation_end - elevation_start) / actual_distance
        else:
            elevation_slope = 0
        
        # Generate elevation values with linear interpolation
        elevation_values = []
        
        for i in range(num_intervals):
            station = start_station_value + i * interval
            if station > end_station_value:
                break
                
            # Calculate how far along the track we are (as a proportion of total distance)
            distance_along_track = station - start_station_value
            
            # Calculate the elevation at this station using the slope
            elevation = elevation_start + (elevation_slope * distance_along_track)
            
            elevation_values.append((station, round(elevation, 1)))
            
        # Add the end station if it's not already included
        if end_station_value not in [station for station, _ in elevation_values]:
            elevation_values.append((end_station_value, elevation_end))
        
        # Update the track elevation profile with these values
        if elevation_values:
            # Merge with existing track elevation points if any
            if self.track_elevation_points:
                # Remove any existing points in the range we're updating
                self.track_elevation_points = [
                    (s, e) for s, e in self.track_elevation_points 
                    if s < start_station_value or s > end_station_value
                ]
                # Add the new points
                self.track_elevation_points.extend(elevation_values)
                # Sort by station
                self.track_elevation_points.sort(key=lambda x: x[0])
            else:
                # Just use the new points
                self.track_elevation_points = elevation_values
            
            # Update relative elevation points
            self.set_track_elevation_profile(self.track_elevation_points)
            
        return elevation_values 

    def generate_custom_elevation_profile(self, elevation_points_dict, interval=10):
        """
        Generate track elevation profile using custom interpolation from a dictionary of station-elevation points
        
        Args:
            elevation_points_dict: Dictionary with station values (in feet) as keys and elevations (feet above sea level) as values
                                  Example: {2000: 150, 2500: 175, 3000: 200}
            interval: Station interval in feet for generating intermediate points (default: 10 ft)
            
        Returns:
            List of (station, elevation) tuples
        """
        if not elevation_points_dict or len(elevation_points_dict) < 2:
            return []
            
        # Convert dictionary to list of (station, elevation) tuples and sort by station
        elevation_points = [(station, elevation) for station, elevation in elevation_points_dict.items()]
        elevation_points.sort(key=lambda x: x[0])
        
        # Find the start and end stations
        start_station_value = elevation_points[0][0]
        end_station_value = elevation_points[-1][0]
        
        # Generate a list of stations at regular intervals
        stations = []
        current_station = start_station_value
        while current_station <= end_station_value:
            stations.append(current_station)
            current_station += interval
            
        # Add the end station if it's not already included
        if end_station_value not in stations:
            stations.append(end_station_value)
            
        # Generate elevation values using custom interpolation
        result = []
        
        for station in stations:
            # Find the two elevation points that bracket this station
            if station <= elevation_points[0][0]:
                # Before the first point, use the first elevation
                elevation = elevation_points[0][1]
            elif station >= elevation_points[-1][0]:
                # After the last point, use the last elevation
                elevation = elevation_points[-1][1]
            else:
                # Find the two points that bracket this station
                for i in range(len(elevation_points) - 1):
                    station1, elev1 = elevation_points[i]
                    station2, elev2 = elevation_points[i + 1]
                    
                    if station1 <= station <= station2:
                        # Linear interpolation between the two points
                        if station2 == station1:  # Avoid division by zero
                            elevation = elev1
                        else:
                            ratio = (station - station1) / (station2 - station1)
                            elevation = elev1 + ratio * (elev2 - elev1)
                        break
                else:
                    # This should never happen if the code is correct
                    elevation = None
            
            if elevation is not None:
                result.append((station, round(elevation, 1)))
        
        # Update the track elevation profile with these values
        if result:
            # Merge with existing track elevation points if any
            if self.track_elevation_points:
                # Remove any existing points in the range we're updating
                self.track_elevation_points = [
                    (s, e) for s, e in self.track_elevation_points 
                    if s < start_station_value or s > end_station_value
                ]
                # Add the new points
                self.track_elevation_points.extend(result)
                # Sort by station
                self.track_elevation_points.sort(key=lambda x: x[0])
            else:
                # Just use the new points
                self.track_elevation_points = result
            
            # Update relative elevation points
            self.set_track_elevation_profile(self.track_elevation_points)
            
        return result 