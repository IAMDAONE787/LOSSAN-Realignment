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
    
    def __init__(self, track_type, start_station, end_station, color=None, tooltip=None):
        """
        Initialize a track type section
        
        Args:
            track_type: Type of track construction (e.g., "Bored Tunnel", "Bridge")
            start_station: Starting station value or string
            end_station: Ending station value or string
            color: Color for this section (optional)
            tooltip: Tooltip text to display on hover (optional)
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
        self.tooltip = tooltip or f"{track_type} ({self.start_station} to {self.end_station})"
        self.coords = []
        
    def add_to_map(self, m, coords, color=None, weight=7, opacity=0.9, add_ant_path=True):
        """
        Add this track section to the map
        
        Args:
            m: Folium map object
            coords: List of coordinates for this section
            color: Override color (optional)
            weight: Line weight
            opacity: Line opacity
            add_ant_path: Whether to add animated ant path
        """
        self.coords = coords
        use_color = color or self.color
        
        # Add base polyline
        folium.PolyLine(
            locations=coords,
            color=use_color,
            weight=weight,
            opacity=opacity,
            tooltip=self.tooltip
        ).add_to(m)
        
        # Add animated path if requested
        if add_ant_path:
            from folium.plugins import AntPath
            AntPath(
                locations=coords,
                dash_array=[10, 20],
                delay=800,
                color=use_color,
                pulseColor='white',
                paused=False,
                weight=weight - 2,  # Slightly thinner for the animated path
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
    
    def add_track_type_section(self, track_type, start_station, end_station, color=None, tooltip=None):
        """
        Add a track type section to the alignment
        
        Args:
            track_type: Type of track construction (e.g., "Bored Tunnel", "Bridge")
            start_station: Starting station value or string
            end_station: Ending station value or string
            color: Color for this section (optional)
            tooltip: Tooltip text to display on hover (optional)
        
        Returns:
            The created TrackTypeSection object
        """
        section = TrackTypeSection(
            track_type=track_type,
            start_station=start_station,
            end_station=end_station,
            color=color or self.color,
            tooltip=tooltip
        )
        
        self.track_type_sections.append(section)
        
        # Add to the appropriate track type list
        if track_type in self.track_types:
            self.track_types[track_type].append(section)
        else:
            self.track_types[track_type] = [section]
            
        return section
    
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
                # Add a solid base line first for better visibility
                folium.PolyLine(
                    locations=coords,
                    color=section.color or self.color,
                    weight=8,  # Slightly thicker for the base
                    opacity=0.9,
                    tooltip=section.tooltip
                ).add_to(m)
                
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