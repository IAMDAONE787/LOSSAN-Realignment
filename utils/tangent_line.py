import folium
import numpy as np
from utils.engineering_coords import station_to_gis

def add_railway_tangent_to_map(m, start_point=None, end_point=None, bearing_deg=None, length_ft=None, 
                              start_station=None, ref_point=None, ref_station=None, track_params=None,
                              color='orange', weight=6, opacity=0.9, 
                              tooltip=None, num_points=11, add_markers=False):
    """
    Add a railway tangent (straight line) section to a Folium map.
    
    This function supports three modes:
    1. Direct coordinates: Provide start_point and end_point
    2. Bearing-based: Provide start_point, bearing_deg, and length_ft
    3. Station-based: Provide start_station, ref_point, ref_station, track_params, and length_ft
    
    Args:
        m: Folium map object
        start_point: Tuple (lat, lon) for the start of the tangent (optional for station-based mode)
        end_point: Tuple (lat, lon) for the end of the tangent (optional)
        bearing_deg: Bearing in degrees (0=North, 90=East) (optional)
        length_ft: Length of the tangent in feet (optional)
        start_station: Start station value (e.g., 2000 for 20+00) (optional)
        ref_point: Reference point coordinates (lat, lon) (optional)
        ref_station: Reference station value (optional)
        track_params: Track parameters dictionary from calculate_track_parameters (optional)
        color: Color of the tangent line
        weight: Width of the tangent line
        opacity: Opacity of the tangent line (0-1)
        tooltip: Optional tooltip text for the tangent
        num_points: Number of points to generate along the tangent
        add_markers: If True, add markers at the start and end points
        
    Returns:
        List of coordinate tuples (lat, lon) forming the tangent line
    """
    tangent_coords = []
    
    # Mode 1: Direct coordinates (start_point and end_point)
    if start_point is not None and end_point is not None:
        # Create a line with evenly spaced points
        for i in range(num_points):
            t = i / (num_points - 1)
            lat = start_point[0] + t * (end_point[0] - start_point[0])
            lon = start_point[1] + t * (end_point[1] - start_point[1])
            tangent_coords.append((lat, lon))
    
    # Mode 2: Start point, bearing and length
    elif start_point is not None and bearing_deg is not None and length_ft is not None:
        # Convert bearing to radians
        bearing_rad = np.radians(bearing_deg)
        
        # Calculate end point using bearing and distance
        # Approximate conversion from feet to degrees
        lat_ft_per_deg = 364000  # ~364,000 feet per degree of latitude
        lon_ft_per_deg = lat_ft_per_deg * np.cos(np.radians(start_point[0]))
        
        # Calculate offsets
        north_offset = length_ft * np.cos(bearing_rad) / lat_ft_per_deg
        east_offset = length_ft * np.sin(bearing_rad) / lon_ft_per_deg
        
        # Calculate end point
        end_lat = start_point[0] + north_offset
        end_lon = start_point[1] + east_offset
        
        end_point = (end_lat, end_lon)
        
        # Create line with evenly spaced points, ensuring the exact distance is used
        for i in range(num_points):
            t = i / (num_points - 1)
            lat = start_point[0] + t * (end_point[0] - start_point[0])
            lon = start_point[1] + t * (end_point[1] - start_point[1])
            tangent_coords.append((lat, lon))
    
    # Mode 3: Station-based with track parameters
    elif start_station is not None and ref_point is not None and ref_station is not None and track_params is not None and length_ft is not None:
        end_station = start_station + length_ft
        
        # Generate points along the tangent using station values
        # This ensures the distance along the track is exactly as specified
        for i in range(num_points):
            station = start_station + i * (length_ft) / (num_points - 1)
            coords = station_to_gis(ref_point, ref_station, station, track_params)
            tangent_coords.append(coords)
    
    else:
        raise ValueError("Invalid parameter combination. Must use one of these combinations:\n"
                        "1. (start_point, end_point)\n"
                        "2. (start_point, bearing_deg, length_ft)\n"
                        "3. (start_station, ref_point, ref_station, track_params, length_ft)")
    
    # Add the tangent to the map
    if m is not None:
        folium.PolyLine(
            locations=tangent_coords,
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=tooltip or "Tangent Line"
        ).add_to(m)
        
        # Add markers if requested
        if add_markers and tangent_coords:
            # Start marker
            folium.Marker(
                location=tangent_coords[0],
                tooltip=f"Tangent Start",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
            
            # End marker
            folium.Marker(
                location=tangent_coords[-1],
                tooltip=f"Tangent End",
                icon=folium.Icon(color="green", icon="info-sign")
            ).add_to(m)
    
    return tangent_coords 