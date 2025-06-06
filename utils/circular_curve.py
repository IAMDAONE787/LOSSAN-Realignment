import numpy as np
from math import sin, cos, atan2, radians, degrees, asin
from utils.engineering_coords import calculate_radius_from_degree_of_curve
import folium

def create_circular_curve(start_point, end_point, radius, direction='right', steps=20):
    """
    Generate points along a circular curve between two points.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the curve
        end_point: Tuple (lat, lon) for the end of the curve
        radius: Radius of the curve in meters
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the curve
    
    Returns:
        List of coordinate tuples (lat, lon) forming the circular curve
    """
    # Convert points to numpy arrays
    p1 = np.array(start_point)
    p2 = np.array(end_point)
    
    # Calculate the vector and distance between points
    v = p2 - p1
    dist = np.linalg.norm(v)
    
    # Skip tiny segments or straight lines
    if dist < 0.00001:
        return [start_point, end_point]
    
    # Normalize the vector
    v_norm = v / dist
    
    # Calculate the perpendicular vector based on direction
    # For right turns, perpendicular is (y, -x), for left turns it's (-y, x)
    perp = np.array([-v_norm[1], v_norm[0]]) if direction == 'left' else np.array([v_norm[1], -v_norm[0]])
    
    # The actual radius needs to be adjusted for the Earth's surface at this latitude
    # This is a rough approximation - 1 degree lat = ~111km, 1 degree lon varies with latitude
    lat_scale = 111000  # meters per degree of latitude
    lon_scale = 111000 * np.cos(np.radians(start_point[0]))  # meters per degree of longitude
    
    # Scale radius to degrees based on average of lat/lon scales
    avg_scale = (lat_scale + lon_scale) / 2
    radius_deg = radius / avg_scale
    
    # Calculate the center of the circle
    # If radius is very large compared to segment length, use a flatter curve
    if radius_deg < dist / 2:
        radius_deg = dist / 2  # Ensure radius is reasonable
    
    # Calculate central angle based on chord length and radius
    central_angle = 2 * np.arcsin(dist / (2 * radius_deg))
    
    # Determine center position
    # For a circle with the given radius passing through both points
    center = (p1 + p2) / 2 + perp * np.sqrt(radius_deg**2 - (dist/2)**2)
    
    # Generate points along the arc
    points = []
    
    # Calculate start angle
    start_vector = p1 - center
    start_angle = np.arctan2(start_vector[1], start_vector[0])
    
    # Calculate sweep angle based on direction
    sweep = central_angle if direction == 'left' else -central_angle
    
    # Generate points
    for i in range(steps + 1):
        t = i / steps
        angle = start_angle + t * sweep
        x = center[0] + radius_deg * np.cos(angle)
        y = center[1] + radius_deg * np.sin(angle)
        points.append((x, y))
    
    return points

# Helper functions for coordinate conversion (simplified)
def _get_xy(lat, lon, lon_ref):
    """Convert geographic coordinates to local XY in feet."""
    R = 20925525.0  # Earth radius in feet
    x = radians(lon - lon_ref) * R * cos(radians(lat))
    y = radians(lat - lat_ref) * R if 'lat_ref' in locals() else radians(lat) * R
    return x, y

def _to_latlon(x, y, lat_ref, lon_ref):
    """Convert local XY coordinates (feet) back to geographic coordinates."""
    R = 20925525.0  # Earth radius in feet
    lat = degrees(y / R) + (lat_ref if 'lat_ref' in locals() else 0)
    lon = degrees(x / (R * cos(radians(lat)))) + lon_ref
    return lat, lon

def create_railway_circular_curve(start_point, end_point=None, bearing_deg=None, degree_of_curve=None, arc_length_ft=None, radius_ft=None, direction='left', steps=200):
    """
    Generate points along a railway circular curve using either endpoints and degree of curvature,
    or start point, bearing, and arc length.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the curve
        end_point: Tuple (lat, lon) for the end of the curve (optional)
        bearing_deg: Initial bearing in degrees (0=North, 90=East) (optional)
        degree_of_curve: Degree of curvature in decimal degrees (Dc)
        arc_length_ft: Length of the circular arc in feet (optional)
        radius_ft: Radius of the curve in feet (alternative to degree_of_curve)
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the curve
    
    Returns:
        List of coordinate tuples (lat, lon) forming the circular curve
    """
    # Extract coordinates
    lat0, lon0 = start_point
    
    # Mode 2: Using bearing and arc length (most common for railway design)
    if bearing_deg is not None and arc_length_ft is not None and (degree_of_curve is not None or radius_ft is not None):
        # Calculate radius from degree of curve if not provided
        if radius_ft is None:
            radius_ft = 5729.58 / degree_of_curve
        
        # Calculate central angle based on the arc length and radius
        central_angle_rad = arc_length_ft / radius_ft
        
        # Direction multiplier
        sign = 1 if direction.lower() == 'left' else -1
        
        # Initialize the points list with the start point
        points = [start_point]
        
        # Generate points along the arc
        for i in range(1, steps + 1):
            # Calculate arc distance for this point
            arc_dist = (i / steps) * arc_length_ft
            
            # Calculate the angle subtended at this point
            angle = arc_dist / radius_ft
            
            # Calculate the bearing to this point
            point_bearing_rad = radians(bearing_deg) + sign * angle
            
            # Calculate the straight-line distance (chord)
            chord = 2 * radius_ft * sin(angle / 2)
            
            # Calculate the bearing to the chord midpoint
            chord_bearing_rad = radians(bearing_deg) + sign * angle / 2
            
            # Calculate the offset from the starting point
            # North component (latitude) - positive is North
            north_offset = chord * cos(chord_bearing_rad)
            # East component (longitude) - positive is East
            east_offset = chord * sin(chord_bearing_rad)
            
            # Convert from feet to degrees
            lat_scale = 364000  # Approximate feet per degree of latitude
            lon_scale = lat_scale * cos(radians(lat0))  # Adjust for longitude at this latitude
            
            # Calculate the new coordinates
            new_lat = lat0 + north_offset / lat_scale
            new_lon = lon0 + east_offset / lon_scale
            
            # Add to the points list
            points.append((new_lat, new_lon))
        
        return points
    
    # Mode 1: Using endpoints and radius (less common for railway design)
    elif end_point is not None and (degree_of_curve is not None or radius_ft is not None):
        lat1, lon1 = end_point
        
        # Calculate radius from degree of curve if not provided
        if radius_ft is None:
            radius_ft = 5729.58 / degree_of_curve
        
        # Convert to XY coordinates to simplify calculations
        # Convert from degrees to feet
        lat_scale = 364000  # Approximate feet per degree of latitude
        lon_scale = lat_scale * cos(radians(lat0))  # Adjust for longitude at this latitude
        
        # Calculate offset in feet
        x0, y0 = 0, 0  # Start point (reference)
        x1 = (lon1 - lon0) * lon_scale  # East offset
        y1 = (lat1 - lat0) * lat_scale  # North offset
        
        # Calculate chord length
        chord_length = ((x1 - x0)**2 + (y1 - y0)**2)**0.5
        
        # Calculate central angle using chord length
        central_angle_rad = 2 * asin(chord_length / (2 * radius_ft))
        
        # Calculate chord bearing
        chord_bearing_rad = atan2(x1 - x0, y1 - y0)  # atan2(East, North)
        
        # Determine direction
        # If not specified, calculate it based on the layout
        if direction is None:
            # TODO: Determine direction based on the layout
            pass
        
        # Direction multiplier
        sign = 1 if direction.lower() == 'left' else -1
        
        # Calculate center of the circle
        # Distance from chord midpoint to center
        midchord_to_center = radius_ft * cos(central_angle_rad / 2) - (chord_length / 2)**2 / radius_ft
        
        # Generate points along the arc
        points = []
        for i in range(steps + 1):
            # Calculate progress along the arc (0 to 1)
            t = i / steps
            
            # Calculate angle for this point
            angle = t * central_angle_rad
            
            # Calculate position along the arc
            arc_bearing = chord_bearing_rad - sign * (central_angle_rad / 2) + sign * angle
            
            # Calculate distance from start (chord approximation)
            distance = 2 * radius_ft * sin(angle / 2)
            
            # Calculate offsets
            east_offset = distance * sin(arc_bearing)
            north_offset = distance * cos(arc_bearing)
            
            # Calculate new coordinates
            new_lon = lon0 + east_offset / lon_scale
            new_lat = lat0 + north_offset / lat_scale
            
            points.append((new_lat, new_lon))
        
        return points
    
    else:
        raise ValueError("Either (start_point, end_point, degree_of_curve/radius_ft) or (start_point, bearing_deg, arc_length_ft, and degree_of_curve/radius_ft) must be provided")

def add_railway_circular_curve_to_map(m, start_point, bearing_deg=None, end_point=None, 
                                     degree_of_curve=None, arc_length_ft=None, radius_ft=None, 
                                     direction='left', steps=200,
                                     color='orange', weight=6, opacity=0.9, 
                                     tooltip=None, add_markers=False):
    """
    Add a railway circular curve directly to a Folium map.
    
    Args:
        m: Folium map object
        start_point: Tuple (lat, lon) for the start of the curve
        bearing_deg: Initial bearing in degrees (0=North, 90=East) (optional)
        end_point: Tuple (lat, lon) for the end of the curve (optional)
        degree_of_curve: Degree of curvature in decimal degrees (Dc)
        arc_length_ft: Length of the circular arc in feet (optional)
        radius_ft: Radius of the curve in feet (alternative to degree_of_curve)
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the curve
        color: Color of the curve line
        weight: Width of the curve line
        opacity: Opacity of the curve line (0-1)
        tooltip: Optional tooltip text for the curve
        add_markers: If True, add markers at the start and end points
        
    Returns:
        List of coordinate tuples (lat, lon) forming the circular curve
    """
    # Generate the circular curve points
    if end_point is not None and (degree_of_curve is not None or radius_ft is not None):
        # Endpoints mode
        curve_coords = create_railway_circular_curve(
            start_point=start_point,
            end_point=end_point,
            degree_of_curve=degree_of_curve,
            radius_ft=radius_ft,
            direction=direction,
            steps=steps
        )
        mode = "endpoints"
    elif bearing_deg is not None and arc_length_ft is not None and (degree_of_curve is not None or radius_ft is not None):
        # Bearing mode
        curve_coords = create_railway_circular_curve(
            start_point=start_point,
            bearing_deg=bearing_deg,
            arc_length_ft=arc_length_ft,
            degree_of_curve=degree_of_curve,
            radius_ft=radius_ft,
            direction=direction,
            steps=steps
        )
        mode = "bearing"
    else:
        raise ValueError("Either (start_point, end_point, and degree_of_curve/radius_ft) or (start_point, bearing_deg, arc_length_ft, and degree_of_curve/radius_ft) must be provided")
    
    # Add the curve to the map
    if radius_ft is None and degree_of_curve is not None:
        radius_ft = 5729.58 / degree_of_curve
        
    curve_info = f"R={int(radius_ft)}ft"
    if arc_length_ft:
        curve_info += f", L={int(arc_length_ft)}ft"
    if degree_of_curve:
        curve_info += f", Dc={degree_of_curve:.2f}°"
        
    folium.PolyLine(
        locations=curve_coords,
        color=color,
        weight=weight,
        opacity=opacity,
        tooltip=tooltip or f"Circular Curve: {curve_info}, {direction} turn"
    ).add_to(m)
    
    # Add markers if requested
    if add_markers:
        # Start marker
        folium.Marker(
            location=curve_coords[0],
            tooltip=f"Curve Start: {mode} mode",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        
        # End marker
        folium.Marker(
            location=curve_coords[-1],
            tooltip=f"Curve End",
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(m)
    
    return curve_coords 