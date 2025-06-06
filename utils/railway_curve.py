import numpy as np
from math import radians, degrees
import folium
from utils.spiral_curve import add_railway_spiral_to_map
from utils.circular_curve import add_railway_circular_curve_to_map
from utils.tangent_line import add_railway_tangent_to_map

def add_complete_railway_curve_to_map(
    m, 
    ts_point,
    ts_bearing_deg,
    entry_spiral_length_ft,
    circular_arc_length_ft,
    exit_spiral_length_ft,
    radius_ft=None,
    degree_of_curve=None,
    direction='right',
    color="#FF7700",
    weight=8,
    opacity=1.0,
    add_white_pattern=True,
    add_markers=True,
    tooltips=None
):
    """
    Add a complete railway curve (spiral-curve-spiral) to a Folium map.
    
    Args:
        m: Folium map object
        ts_point: Tuple (lat, lon) for Tangent to Spiral (TS) point
        ts_bearing_deg: Initial bearing in degrees (0=North, 90=East)
        entry_spiral_length_ft: Length of the entry spiral in feet
        circular_arc_length_ft: Length of the circular arc in feet
        exit_spiral_length_ft: Length of the exit spiral in feet
        radius_ft: Radius of the circular curve in feet (alternative to degree_of_curve)
        degree_of_curve: Degree of curvature in decimal degrees (Dc), alternative to radius_ft
        direction: 'right' or 'left' to indicate turning direction
        color: Color of the curve lines
        weight: Width of the curve lines
        opacity: Opacity of the curve lines (0-1)
        add_white_pattern: If True, add white patterned lines for better visualization
        add_markers: If True, add markers at the key points (TS, SC, CS, ST)
        tooltips: Optional dictionary of custom tooltips for each segment
        
    Returns:
        Dictionary containing the coordinates of all segments and key points
    """
    # Process tooltips
    if tooltips is None:
        tooltips = {}
    
    default_tooltips = {
        "entry_spiral": f"Entry Spiral (TS to SC): {entry_spiral_length_ft} ft",
        "circular_curve": f"Circular Curve (SC to CS): {circular_arc_length_ft} ft",
        "exit_spiral": f"Exit Spiral (CS to ST): {exit_spiral_length_ft} ft"
    }
    
    # Use default tooltips for any missing tooltips
    for key, value in default_tooltips.items():
        if key not in tooltips:
            tooltips[key] = value
    
    # Calculate radius from degree of curve if needed
    if radius_ft is None and degree_of_curve is not None:
        radius_ft = 5729.58 / degree_of_curve
    elif radius_ft is None:
        raise ValueError("Either radius_ft or degree_of_curve must be provided")
    
    # 1. Entry spiral (TS to SC)
    entry_spiral_coords = add_railway_spiral_to_map(
        m=m,
        start_point=ts_point,
        bearing_deg=ts_bearing_deg,
        spiral_length_ft=entry_spiral_length_ft,
        radius_ft=radius_ft,
        direction=direction,
        steps=100,
        color=color,
        weight=weight,
        opacity=opacity,
        tooltip=tooltips["entry_spiral"]
    )
    
    # Add white pattern if requested
    if add_white_pattern:
        folium.PolyLine(
            locations=entry_spiral_coords,
            color="#FFFFFF",
            weight=2,
            opacity=0.8,
            dash_array="5,10",
            tooltip=tooltips["entry_spiral"]
        ).add_to(m)
    
    # Calculate SC point (end of entry spiral)
    sc_point = entry_spiral_coords[-1]
    
    # Calculate SC bearing
    spiral_deflection = (entry_spiral_length_ft**2) / (2 * radius_ft * entry_spiral_length_ft)
    spiral_deflection_deg = np.degrees(spiral_deflection)
    
    if direction == 'right':
        sc_bearing = ts_bearing_deg - spiral_deflection_deg
    else:  # left
        sc_bearing = ts_bearing_deg + spiral_deflection_deg
    
    # 2. Circular curve (SC to CS)
    circular_curve_coords = add_railway_circular_curve_to_map(
        m=m,
        start_point=sc_point,
        bearing_deg=sc_bearing,
        arc_length_ft=circular_arc_length_ft,
        radius_ft=radius_ft,
        direction=direction,
        steps=100,
        color=color,
        weight=weight,
        opacity=opacity,
        tooltip=tooltips["circular_curve"]
    )
    
    # Add white pattern if requested
    if add_white_pattern:
        folium.PolyLine(
            locations=circular_curve_coords,
            color="#FFFFFF",
            weight=2,
            opacity=0.8,
            dash_array="10,5",
            tooltip=tooltips["circular_curve"]
        ).add_to(m)
    
    # Calculate CS point (end of circular curve)
    cs_point = circular_curve_coords[-1]
    
    # Calculate CS bearing
    circular_deflection_rad = circular_arc_length_ft / radius_ft
    circular_deflection_deg = np.degrees(circular_deflection_rad)
    
    if direction == 'right':
        cs_bearing = sc_bearing - circular_deflection_deg
    else:  # left
        cs_bearing = sc_bearing + circular_deflection_deg
    
    # 3. Exit spiral (CS to ST)
    exit_spiral_coords = add_railway_spiral_to_map(
        m=m,
        start_point=cs_point,
        bearing_deg=cs_bearing,
        spiral_length_ft=exit_spiral_length_ft,
        radius_ft=radius_ft,
        direction=direction,
        steps=100,
        color=color,
        weight=weight,
        opacity=opacity,
        tooltip=tooltips["exit_spiral"]
    )
    
    # Add white pattern if requested
    if add_white_pattern:
        folium.PolyLine(
            locations=exit_spiral_coords,
            color="#FFFFFF",
            weight=2,
            opacity=0.8,
            dash_array="5,10",
            tooltip=tooltips["exit_spiral"]
        ).add_to(m)
    
    # Calculate ST point (end of exit spiral)
    st_point = exit_spiral_coords[-1]
    
    # Add markers for key points if requested
    if add_markers:
        # TS marker
        folium.Marker(
            location=ts_point,
            tooltip="TS: Tangent to Spiral",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        
        # SC marker
        folium.Marker(
            location=sc_point,
            tooltip="SC: Spiral to Curve",
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(m)
        
        # CS marker
        folium.Marker(
            location=cs_point,
            tooltip="CS: Curve to Spiral",
            icon=folium.Icon(color="purple", icon="info-sign")
        ).add_to(m)
        
        # ST marker
        folium.Marker(
            location=st_point,
            tooltip="ST: Spiral to Tangent",
            icon=folium.Icon(color="orange", icon="info-sign")
        ).add_to(m)
    
    # Return all coordinates and key points
    return {
        "entry_spiral_coords": entry_spiral_coords,
        "circular_curve_coords": circular_curve_coords,
        "exit_spiral_coords": exit_spiral_coords,
        "ts_point": ts_point,
        "sc_point": sc_point,
        "cs_point": cs_point,
        "st_point": st_point,
        "all_coords": entry_spiral_coords + circular_curve_coords + exit_spiral_coords
    }

def add_complete_railway_alignment_to_map(
    m,
    ts_point,
    ts_bearing_deg,
    entry_spiral_length_ft,
    circular_arc_length_ft,
    exit_spiral_length_ft,
    start_tangent_length_ft=0,
    end_tangent_length_ft=0,
    radius_ft=None,
    degree_of_curve=None,
    direction='right',
    color="#FF7700",
    weight=8,
    opacity=1.0,
    add_white_pattern=True,
    add_markers=True,
    tooltips=None
):
    """
    Add a complete railway alignment with optional tangents before and after the curve.
    
    Args:
        m: Folium map object
        ts_point: Tuple (lat, lon) for Tangent to Spiral (TS) point
        ts_bearing_deg: Initial bearing in degrees (0=North, 90=East)
        entry_spiral_length_ft: Length of the entry spiral in feet
        circular_arc_length_ft: Length of the circular arc in feet
        exit_spiral_length_ft: Length of the exit spiral in feet
        start_tangent_length_ft: Length of tangent before TS (0 for none)
        end_tangent_length_ft: Length of tangent after ST (0 for none)
        radius_ft: Radius of the circular curve in feet (alternative to degree_of_curve)
        degree_of_curve: Degree of curvature in decimal degrees (Dc), alternative to radius_ft
        direction: 'right' or 'left' to indicate turning direction
        color: Color of the curve lines
        weight: Width of the curve lines
        opacity: Opacity of the curve lines (0-1)
        add_white_pattern: If True, add white patterned lines for better visualization
        add_markers: If True, add markers at the key points
        tooltips: Optional dictionary of custom tooltips for each segment
        
    Returns:
        Dictionary containing the coordinates of all segments and key points
    """
    result = {}
    
    # Process tooltips
    if tooltips is None:
        tooltips = {}
    
    default_tooltips = {
        "start_tangent": "Starting Tangent",
        "entry_spiral": f"Entry Spiral (TS to SC): {entry_spiral_length_ft} ft",
        "circular_curve": f"Circular Curve (SC to CS): {circular_arc_length_ft} ft",
        "exit_spiral": f"Exit Spiral (CS to ST): {exit_spiral_length_ft} ft",
        "end_tangent": "Ending Tangent"
    }
    
    # Use default tooltips for any missing tooltips
    for key, value in default_tooltips.items():
        if key not in tooltips:
            tooltips[key] = value
    
    # Start point for beginning of alignment
    start_point = ts_point
    
    # If there's a starting tangent, add it and update TS point
    if start_tangent_length_ft > 0:
        # Calculate the starting point by going backwards along the tangent
        # This works because we know the bearing at TS
        reversed_bearing = (ts_bearing_deg + 180) % 360
        
        # Add tangent section backwards from TS
        start_tangent_coords = add_railway_tangent_to_map(
            m=m,
            start_point=ts_point,
            bearing_deg=reversed_bearing,
            length_ft=start_tangent_length_ft,
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=tooltips["start_tangent"],
            num_points=20
        )
        
        # Starting point is at the beginning of the tangent
        start_point = start_tangent_coords[-1]
        result["start_tangent_coords"] = start_tangent_coords
    
    # Add the curved section (spiral-curve-spiral)
    curve_result = add_complete_railway_curve_to_map(
        m=m,
        ts_point=ts_point,
        ts_bearing_deg=ts_bearing_deg,
        entry_spiral_length_ft=entry_spiral_length_ft,
        circular_arc_length_ft=circular_arc_length_ft,
        exit_spiral_length_ft=exit_spiral_length_ft,
        radius_ft=radius_ft,
        degree_of_curve=degree_of_curve,
        direction=direction,
        color=color,
        weight=weight,
        opacity=opacity,
        add_white_pattern=add_white_pattern,
        add_markers=add_markers,
        tooltips={
            "entry_spiral": tooltips["entry_spiral"],
            "circular_curve": tooltips["circular_curve"],
            "exit_spiral": tooltips["exit_spiral"]
        }
    )
    
    # Update result with curve data
    result.update(curve_result)
    
    # If there's an ending tangent, add it
    if end_tangent_length_ft > 0:
        st_point = curve_result["st_point"]
        
        # Calculate ST bearing (after exit spiral)
        spiral_deflection = (exit_spiral_length_ft**2) / (2 * radius_ft * exit_spiral_length_ft)
        spiral_deflection_deg = np.degrees(spiral_deflection)
        
        # Calculate the bearing at ST
        cs_bearing = curve_result["cs_bearing"] if "cs_bearing" in curve_result else None
        if cs_bearing is None:
            # Recalculate CS bearing if not provided
            sc_bearing = result.get("sc_bearing")
            if sc_bearing is None:
                # Recalculate SC bearing if not provided
                spiral_deflection = (entry_spiral_length_ft**2) / (2 * radius_ft * entry_spiral_length_ft)
                spiral_deflection_deg = np.degrees(spiral_deflection)
                if direction == 'right':
                    sc_bearing = ts_bearing_deg - spiral_deflection_deg
                else:  # left
                    sc_bearing = ts_bearing_deg + spiral_deflection_deg
                
            circular_deflection_rad = circular_arc_length_ft / radius_ft
            circular_deflection_deg = np.degrees(circular_deflection_rad)
            if direction == 'right':
                cs_bearing = sc_bearing - circular_deflection_deg
            else:  # left
                cs_bearing = sc_bearing + circular_deflection_deg
        
        # Final bearing at ST
        if direction == 'right':
            st_bearing = cs_bearing - spiral_deflection_deg
        else:  # left
            st_bearing = cs_bearing + spiral_deflection_deg
        
        # Add ending tangent
        end_tangent_coords = add_railway_tangent_to_map(
            m=m,
            start_point=st_point,
            bearing_deg=st_bearing,
            length_ft=end_tangent_length_ft,
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=tooltips["end_tangent"],
            num_points=20
        )
        
        result["end_tangent_coords"] = end_tangent_coords
        
        # Add end tangent to all coordinates
        result["all_coords"] = result["all_coords"] + end_tangent_coords
    
    # Return the complete results
    return result 