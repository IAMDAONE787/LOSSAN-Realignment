import numpy as np
from math import sin, cos, atan2, radians, degrees
from utils.engineering_coords import calculate_radius_from_degree_of_curve
import folium

def create_spiral_curve(start_point, end_point, direction='right', steps=20):
    """
    Generate points along a spiral curve (clothoid) between two points.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the spiral
        end_point: Tuple (lat, lon) for the end of the spiral
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the spiral
    
    Returns:
        List of coordinate tuples (lat, lon) forming the spiral curve
    """
    # Convert to numpy arrays
    p1 = np.array(start_point)
    p2 = np.array(end_point)
    
    # Calculate vector and distance between points
    v = p2 - p1
    dist = np.linalg.norm(v)
    
    # If the distance is too small, return just the points
    if dist < 0.00001:
        return [start_point, end_point]
    
    # Normalize the vector
    v_norm = v / dist
    
    # Calculate bearing/azimuth
    bearing = np.arctan2(v_norm[1], v_norm[0])
    
    # Calculate perpendicular vector based on direction
    perp = np.array([-v_norm[1], v_norm[0]]) if direction == 'left' else np.array([v_norm[1], -v_norm[0]])
    
    # Scale factors for lat/lon to approximate meters at this latitude
    lat_scale = 111000  # meters per degree of latitude
    lon_scale = 111000 * np.cos(np.radians(start_point[0]))  # meters per degree of longitude
    avg_scale = (lat_scale + lon_scale) / 2
    
    # Convert the distance to meters for the spiral calculation
    spiral_length = dist * avg_scale
    
    # Use a reasonable clothoid parameter for a gentle curve
    # A is the clothoid parameter, related to radius * spiral length
    A = np.sqrt(spiral_length * 2000)  # Use a large radius for gentle curves
    
    # Sign for the direction
    sign = -1 if direction == 'right' else 1
    
    # Generate spiral in the local coordinate system
    points = []
    for i in range(steps + 1):
        t = i / steps
        s = t * spiral_length
        
        # Fresnel integrals approximation (clothoid/Euler spiral)
        # For small values, use simplified formula
        if s < 0.01:
            x = s
            y = 0
        else:
            # Standard clothoid equations
            x = s - (s**5) / (40 * A**4) + (s**9) / (3456 * A**8)
            y = sign * ((s**3) / (6 * A**2) - (s**7) / (336 * A**6))
        
        # Rotate and scale back to lat/lon coordinates
        x_rot = x * np.cos(bearing) - y * np.sin(bearing)
        y_rot = x * np.sin(bearing) + y * np.cos(bearing)
        
        # Convert back to lat/lon
        lat = start_point[0] + (x_rot / avg_scale)
        lon = start_point[1] + (y_rot / lon_scale)
        
        points.append((lat, lon))
    
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

def create_railway_spiral(start_point, bearing_deg, spiral_length_ft, degree_of_curve=None, radius_ft=None, direction='left', steps=200):
    """
    Generate points along a railway spiral curve (clothoid/Euler spiral) using engineering parameters.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the spiral (TS point)
        bearing_deg: Initial bearing in degrees (0=North, 90=East)
        spiral_length_ft: Length of the spiral in feet (Ls)
        degree_of_curve: Degree of curvature in decimal degrees (Dc), alternative to radius_ft
        radius_ft: Final curve radius in feet (R), alternative to degree_of_curve
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the spiral
        
    Returns:
        List of coordinate tuples (lat, lon) forming the spiral curve
    """
    # Extract coordinates
    lat_ts, lon_ts = start_point
    
    # Get radius from degree of curve if needed
    if radius_ft is None and degree_of_curve is not None:
        radius_ft = calculate_radius_from_degree_of_curve(degree_of_curve)
    elif radius_ft is None:
        raise ValueError("Either radius_ft or degree_of_curve must be provided")
    
    # Parameter A = sqrt(R*Ls) for spiral calculation
    A = np.sqrt(radius_ft * spiral_length_ft)
    
    # Generate points along the spiral
    # Use exact distances along the curve to ensure accurate station points
    s = np.linspace(0, spiral_length_ft, steps+1)
    
    # Calculate local x,y coordinates using Fresnel integrals
    x_local = s - s**5 / (40 * A**4) + s**9 / (3456 * A**8)
    y_local = (s**3) / (6 * A**2) - (s**7) / (336 * A**6)
    
    # Adjust for direction
    if direction.lower() == 'right':
        y_local *= -1
    
    # Convert bearing to radians - adjust for coordinate system
    # In GIS: 0° is North, 90° is East
    th = radians(bearing_deg)
    
    # Initialize arrays for final coordinates
    points = []
    
    # Start point is the first point
    points.append(start_point)
    
    # Calculate the remaining points using proper railway engineering
    for i in range(1, len(s)):
        # Get the distance along the spiral
        distance = s[i]
        
        # Calculate deflection angle at this point
        deflection = distance**2 / (2 * radius_ft * spiral_length_ft)
        
        # Calculate radius at this point
        R = radius_ft * spiral_length_ft / distance if distance > 0 else float('inf')
        
        # Calculate arc length and chord length
        arc_length = distance
        chord_length = arc_length * (1.0 - deflection**2 / 10.0)  # Approximation
        
        # Calculate chord bearing
        chord_bearing = bearing_deg
        if direction.lower() == 'left':
            chord_bearing += np.degrees(deflection / 2)
        else:
            chord_bearing -= np.degrees(deflection / 2)
        
        # Convert to radians
        chord_bearing_rad = radians(chord_bearing)
        
        # Calculate the offset from the starting point
        # North component (latitude) - positive is North
        north_offset = chord_length * np.cos(chord_bearing_rad)
        # East component (longitude) - positive is East
        east_offset = chord_length * np.sin(chord_bearing_rad)
        
        # Convert from feet to degrees
        lat_scale = 364000  # Approximate feet per degree of latitude
        lon_scale = lat_scale * np.cos(radians(lat_ts))  # Adjust for longitude at this latitude
        
        # Calculate the new coordinates
        new_lat = lat_ts + north_offset / lat_scale
        new_lon = lon_ts + east_offset / lon_scale
        
        # Add to the points list
        points.append((new_lat, new_lon))
    
    return points

def add_railway_spiral_to_map(m, start_point, bearing_deg, spiral_length_ft, 
                              degree_of_curve=None, radius_ft=None, 
                              direction='left', steps=200, 
                              color='orange', weight=6, opacity=0.9, 
                              tooltip=None, add_markers=False):
    """
    Add a railway spiral curve directly to a Folium map.
    
    Args:
        m: Folium map object (can be None to just calculate coordinates without adding to map)
        start_point: Tuple (lat, lon) for the start of the spiral (TS point)
        bearing_deg: Initial bearing in degrees (0=North, 90=East)
        spiral_length_ft: Length of the spiral in feet (Ls)
        degree_of_curve: Degree of curvature in decimal degrees (Dc), alternative to radius_ft
        radius_ft: Final curve radius in feet (R), alternative to degree_of_curve
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the spiral
        color: Color of the spiral line
        weight: Width of the spiral line
        opacity: Opacity of the spiral line (0-1)
        tooltip: Optional tooltip text for the spiral
        add_markers: If True, add markers at the start and end points
        
    Returns:
        List of coordinate tuples (lat, lon) forming the spiral curve
    """
    # Generate the spiral curve points
    spiral_coords = create_railway_spiral(
        start_point=start_point,
        bearing_deg=bearing_deg,
        spiral_length_ft=spiral_length_ft,
        degree_of_curve=degree_of_curve,
        radius_ft=radius_ft,
        direction=direction,
        steps=steps
    )

    #print(f"spiral_coords -1: {spiral_coords[-1]}, spiral_coords 0: {spiral_coords[0]}")
    
    # Add the spiral to the map if m is not None
    if m is not None:
        folium.PolyLine(
            locations=spiral_coords,
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=tooltip or f"Spiral Curve: {spiral_length_ft} ft, {direction} turn"
        ).add_to(m)
        
        # Add markers if requested
        if add_markers:
            # Start marker
            folium.Marker(
                location=spiral_coords[0],
                tooltip=f"Spiral Start: {start_point}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
            
            # End marker
            folium.Marker(
                location=spiral_coords[-1],
                tooltip=f"Spiral End",
                icon=folium.Icon(color="green", icon="info-sign")
            ).add_to(m)
    
    return spiral_coords 