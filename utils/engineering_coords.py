import numpy as np
from geopy.distance import geodesic
import math

def calculate_track_parameters(point1, station1, point2, station2):
    """
    Calculate track direction and scale based on two known points and their stations.
    
    Args:
        point1: Tuple (lat, lon) for the first known point
        station1: Station value for the first point (in feet, e.g., 2000 for 20+00)
        point2: Tuple (lat, lon) for the second known point
        station2: Station value for the second point (in feet, e.g., 2500 for 25+00)
        
    Returns:
        Dictionary with track bearing, scale, and direction vector
    """
    
    #print(f"point1: {point1}, station1: {station1}, point2: {point2}, station2: {station2}")
    
    # Convert points to numpy arrays
    p1 = np.array(point1)
    p2 = np.array(point2)
    
    # Calculate vector and distance between points
    vector = p2 - p1
    gis_distance = np.linalg.norm(vector)
    
    # Calculate bearing
    bearing_rad = np.arctan2(vector[1], vector[0])
    bearing_deg = np.degrees(bearing_rad)
    
    # Calculate distance between stations
    station_distance = station2 - station1
    
    # Calculate scale (GIS units per foot)
    scale = gis_distance / station_distance
    
    # Normalize direction vector
    direction = vector / np.linalg.norm(vector)

    #print(f"gis_distance: {gis_distance}, station_distance: {station_distance}")

    #print(f"bearing_rad: {bearing_rad}, bearing_deg: {bearing_deg}, scale: {scale}, direction: {direction}")
    
    return {
        'bearing_rad': bearing_rad,
        'bearing_deg': bearing_deg,
        'scale': scale,
        'direction': direction
    }

def station_to_gis(reference_point, reference_station, target_station, track_params, alignment=None):
    """
    Convert a station value to GIS coordinates.
    
    Args:
        reference_point: Tuple (lat, lon) for the reference point
        reference_station: Station value for the reference point (in feet)
        target_station: Station value to convert (in feet)
        track_params: Track parameters from calculate_track_parameters
        alignment: Optional RailwayAlignment object to use for more accurate positioning
        
    Returns:
        Tuple (lat, lon) for the target station
    """
    # If alignment is provided, try to use it for more accurate positioning
    if alignment is not None and hasattr(alignment, 'all_coords') and alignment.all_coords:
        try:
            # Find the segment that contains the target station
            current_station = reference_station
            for i, segment in enumerate(alignment.segments):
                segment_start_station = current_station
                segment_end_station = current_station
                
                if segment.type == "tangent":
                    segment_end_station = segment_start_station + segment.length_ft
                elif segment.type == "spiral_curve_spiral":
                    segment_end_station = segment_start_station + segment.entry_spiral_length + segment.circular_arc_length + segment.exit_spiral_length
                
                # Check if the target station is within this segment
                if segment_start_station <= target_station <= segment_end_station:
                    # Calculate the percentage along the segment
                    segment_length = segment_end_station - segment_start_station
                    percentage = (target_station - segment_start_station) / segment_length
                    
                    # Get the coordinates at that percentage along the segment
                    segment_coords = alignment.segment_coords[i]
                    index = int(percentage * (len(segment_coords) - 1))
                    return segment_coords[index]
                
                current_station = segment_end_station
                
            # If we couldn't find the segment, fall back to the original method
            print("Could not find segment containing station, falling back to vector calculation")
        except Exception as e:
            print(f"Error using alignment for station_to_gis: {e}")
            # Fall back to the original method
    
    # Original method using vector calculation
    # Calculate distance in GIS units
    station_distance = target_station - reference_station
    gis_distance = station_distance * track_params['scale']
    
    # Calculate the offset
    offset = gis_distance * track_params['direction']
    
    # Apply offset to reference point
    target_point = np.array(reference_point) + offset
    
    return (target_point[0], target_point[1])

def parse_station(station_str):
    """
    Parse a station string (e.g., "24+04.67") to a numeric value in feet.
    
    Args:
        station_str: Station string in the format "XX+YY.ZZ"
        
    Returns:
        Station value in feet
    """
    parts = station_str.split('+')
    if len(parts) != 2:
        raise ValueError(f"Invalid station format: {station_str}")
    
    hundreds = float(parts[0]) * 100
    feet = float(parts[1])
    
    return hundreds + feet

def parse_angle(angle_str):
    """
    Parse an angle string (e.g., "9 00'00\"") to degrees.
    
    Args:
        angle_str: Angle string in DMS format
        
    Returns:
        Angle in decimal degrees
    """
    # Extract degrees, minutes, seconds
    parts = angle_str.replace(' ', ' ').replace("'", ' ').replace('"', ' ').split()
    
    degrees = float(parts[0])
    minutes = float(parts[1]) if len(parts) > 1 else 0
    seconds = float(parts[2]) if len(parts) > 2 else 0
    
    return degrees + minutes/60 + seconds/3600

def calculate_radius_from_degree_of_curve(degree_of_curve):
    """
    Calculate radius from degree of curvature (arc definition).
    In US railway engineering, Dc is defined as the central angle in degrees
    subtended by a 100-foot arc.
    
    Args:
        degree_of_curve: Degree of curvature in decimal degrees
        
    Returns:
        Radius in feet
    """
    if degree_of_curve <= 0:
        return float('inf')  # Straight line
    
    # Formula: R = 5729.578 / Dc (for arc definition)
    radius = 5729.578 / degree_of_curve
    
    return radius 

def format_station(station_value):
    """Format a station value as XX+XX.XX"""
    station_main = int(station_value / 100)
    station_decimal = station_value - (station_main * 100)
    return f"{station_main}+{station_decimal:.2f}" 