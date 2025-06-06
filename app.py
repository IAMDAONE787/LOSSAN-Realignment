# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import numpy as np
from folium.plugins import AntPath
from utils import create_curved_path, create_circular_curve, create_spiral_curve
from utils.engineering_coords import (
    calculate_track_parameters, 
    station_to_gis, 
    parse_station,
    parse_angle,
    calculate_radius_from_degree_of_curve
)
from utils.spiral_curve import create_railway_spiral, add_railway_spiral_to_map
from utils.circular_curve import create_railway_circular_curve, add_railway_circular_curve_to_map
from utils.tangent_line import add_railway_tangent_to_map
from utils.railway_curve import add_complete_railway_curve_to_map, add_complete_railway_alignment_to_map
from utils.railway_alignment import RailwayAlignment, TangentSegment, CurveSegment

def format_station(station_value):
    """Format a station value as XX+XX.XX"""
    station_main = int(station_value / 100)
    station_decimal = station_value - (station_main * 100)
    return f"{station_main}+{station_decimal:.2f}"

try:
    from shapely.geometry import LineString, Point
except ImportError:
    st.error("Failed to import Shapely. Please check your installation.")
    LineString = None
    Point = None

# Set page config first
st.set_page_config(layout="wide")

# Hide default Streamlit footer and add padding
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    /* Make the main content area fill available space but not overflow */
    .main {
        flex: 1 1 auto;
        overflow: auto;
    }
    /* Make overall container fill the viewport exactly */
    .stApp {
        display: flex;
        flex-direction: column;
        height: 100vh;
        overflow: hidden;
    }
    /* Fix the footer at the bottom */
    .custom-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 10px 20px;
        border-top: 1px solid #ddd;
        z-index: 999;
    }
    /* Ensure content doesn't get hidden behind the footer */
    [data-testid="stAppViewBlockContainer"] {
        padding-bottom: 60px;
    }
    /* Adjust for sidebar */
    [data-testid="stSidebar"][aria-expanded="true"] ~ div .custom-footer {
        left: var(--sidebar-width, 22rem);
    }
    [data-testid="stSidebar"][aria-expanded="false"] ~ div .custom-footer {
        left: 0;
    }
    /* Adjust the height of the map container */
    iframe {
        height: calc(100vh - 200px) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("LOSSAN Rail Realignment Explorer")

# Create a container for the main content
main_content = st.container()

with main_content:
    # --- 1. define your four alignments (lat, lon) lists here ---
    ALIGNMENTS = {
        "Blue Route: Under Crest Canyon": {
            "coords": [
                (32.9720408, -117.2664554),
                (32.9676162, -117.2653677),
                (32.9636421, -117.2633048),
                (32.9558076, -117.2566718),
                (32.9491315, -117.2547255),
                (32.9383269, -117.2473140),
                (32.9306534, -117.2445875),
                (32.9251512, -117.2425307),
                (32.9162438, -117.2371537),
            ],
            "color": "blue",
        },
        "Purple Route: Under Camino Del Mar": {
            "coords": [
                (32.9720408, -117.2664554),
                (32.9676162, -117.2653677),
                (32.9649757, -117.2655738),
                (32.9579593, -117.2649714),
                (32.9480552, -117.2612477),
                (32.9400607, -117.2610541),
                (32.9351700+0.00005, -117.2587578+0.00005),
                (32.9162438+0.00005, -117.2371537+0.00005),
            ],
            "color": "magenta",
        },
        "Green Route: Del Mar Bluffs Double-Track": {
            "coords": [
                (32.9720408, -117.2664554),
                (32.9676162, -117.2653677),
                (32.9649757, -117.2655738),
                (32.9608866, -117.2681671),
                (32.9556471, -117.2670344),
                (32.9457051, -117.2631553),
                (32.9387049, -117.2612257),
                (32.9351700, -117.2587578),
                (32.9162438, -117.2371537),
            ],
            "color": "green",
        },
    }

    # --- 2. address input & geocoding ---
    address = st.sidebar.text_input("Search address", value=st.session_state.get("address", ""))
    search = st.sidebar.button("Search")

    # Initialize session state for location if not present
    if "location" not in st.session_state:
        st.session_state["location"] = None

    if search and address:
        geolocator = Nominatim(user_agent="lossan_app")
        location = geolocator.geocode(address)
        if location is None:
            st.sidebar.error("Address not found")
            st.session_state["location"] = None
        else:
            st.session_state["address"] = address
            st.session_state["location"] = location

    # Use session state location for display
    location = st.session_state.get("location", None)
    address = st.session_state.get("address", "")

    # --- 3. build the Folium map ---
    # default center over Del Mar
    center = (32.975, -117.245)
    initial_zoom = 13
    if location:
        center = (location.latitude, location.longitude)
        initial_zoom = 15

    m = folium.Map(location=center, zoom_start=initial_zoom, tiles="OpenStreetMap")

    # Dictionary to store expanded coordinates for each alignment
    expanded_alignments = {}

    # add routes for Blue, Purple, and Green tracks
    for name, data in ALIGNMENTS.items():
        # Get original coordinates
        coords = data["coords"]
        
        # Generate a smooth path with straight segments and curved corners
        smoothed_coords = []
        
        # Need at least 3 points to have corners to smooth
        if len(coords) < 3:
            smoothed_coords = coords.copy()
        else:
            # Process each vertex (where two segments meet)
            for i in range(len(coords)):
                # First point - just add it
                if i == 0:
                    smoothed_coords.append(coords[i])
                    continue
                    
                # Last point - just add it
                if i == len(coords) - 1:
                    smoothed_coords.append(coords[i])
                    continue
                    
                # This is a vertex between two segments
                p1 = coords[i-1]  # Previous point
                p2 = coords[i]    # Current vertex
                p3 = coords[i+1]  # Next point
                
                # Calculate distances
                dist1 = geodesic(p1, p2).meters
                dist2 = geodesic(p2, p3).meters
                
                # Skip very short segments
                if dist1 < 20 or dist2 < 20:
                    smoothed_coords.append(p2)
                    continue
                
                # Calculate vectors
                v1 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
                v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
                
                # Normalize vectors
                v1_norm = v1 / np.linalg.norm(v1)
                v2_norm = v2 / np.linalg.norm(v2)
                
                # Calculate angle between segments
                dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
                angle = np.degrees(np.arccos(dot_product))
                
                # Skip if angle is very small (almost straight)
                if angle < 5:
                    smoothed_coords.append(p2)
                    continue
                    
                # Determine turn direction using cross product
                cross_product = v1_norm[0]*v2_norm[1] - v1_norm[1]*v2_norm[0]
                direction = 'right' if cross_product < 0 else 'left'
                
                # Define how much of each segment to use for the curve
                # Use a fraction of the shorter segment, but limit curve length
                curve_length = min(dist1, dist2) * 0.3  # Use 30% of shorter segment
                curve_length = min(curve_length, 200)   # But no more than 200 meters
                curve_length = max(curve_length, 50)    # And no less than 50 meters
                
                # Calculate points for the start and end of the curve
                # Move back from p2 along v1 by curve_length
                curve_start_factor = curve_length / dist1
                curve_start = (
                    p2[0] - v1_norm[0] * curve_length / 111000,  # Convert meters to degrees lat
                    p2[1] - v1_norm[1] * curve_length / (111000 * np.cos(np.radians(p2[0])))  # Convert to degrees lon
                )
                
                # Move forward from p2 along v2 by curve_length
                curve_end_factor = curve_length / dist2
                curve_end = (
                    p2[0] + v2_norm[0] * curve_length / 111000,  # Convert meters to degrees lat
                    p2[1] + v2_norm[1] * curve_length / (111000 * np.cos(np.radians(p2[0])))  # Convert to degrees lon
                )
                
                # Add straight segment from previous point to curve start
                # Only do this for points after the first vertex
                if i > 1:
                    # Create a few points along the straight segment for better visualization
                    for j in range(1, 4):
                        t = j / 4
                        lat = smoothed_coords[-1][0] + t * (curve_start[0] - smoothed_coords[-1][0])
                        lon = smoothed_coords[-1][1] + t * (curve_start[1] - smoothed_coords[-1][1])
                        smoothed_coords.append((lat, lon))
                
                # Choose curve type based on angle
                if angle > 60:
                    # For sharper turns, use circular curve
                    curve_radius = curve_length * 3  # Larger radius for smoother curve
                    curve_points = create_circular_curve(
                        start_point=curve_start,
                        end_point=curve_end,
                        radius=curve_radius,
                        direction=direction,
                        steps=10
                    )
                else:
                    # For gentler turns, use spiral curve
                    curve_points = create_spiral_curve(
                        start_point=curve_start,
                        end_point=curve_end,
                        direction=direction,
                        steps=10
                    )
                
                # Add all curve points
                smoothed_coords.extend(curve_points)
        
        # Store expanded coordinates for distance calculations
        expanded_alignments[name] = smoothed_coords
        
        # Add a solid base line for better visibility
        folium.PolyLine(
            locations=smoothed_coords,
            color=data["color"],
            weight=7,
            opacity=0.7,
            tooltip=name
        ).add_to(m)
        
        # Add animated path on top
        AntPath(
            locations=smoothed_coords,
            dash_array=[10, 15],
            delay=800,
            color=data["color"],
            pulseColor='#FFFFFF',
            paused=False,
            weight=4,
            opacity=0.9,
            tooltip=name
        ).add_to(m)

    # === YELLOW TRACK ENGINEERING MODEL ===
    # Create the yellow track using the engineering specifications and directly add to map
    
    # Known engineering data for the first curve of the yellow track
    station_2000_coords = (32.9740081, -117.2669915)  # 20+00 station
    station_2500_coords = (32.9726647, -117.2666647)  # 25+00 station
    
    # Create a new Railway Alignment for the Yellow route
    yellow_alignment = RailwayAlignment(name="Yellow Route: Engineering Alignment", color="#FFD700")  # Gold yellow - less bright
    
    # Add reference points
    yellow_alignment.add_reference_point("STA_2000", station_2000_coords, 2000)
    yellow_alignment.add_reference_point("STA_2500", station_2500_coords, 2500)
    
    # Calculate track parameters based on reference points
    track_params = yellow_alignment.calculate_track_params("STA_2000", "STA_2500")
    
    # Define segments for the Yellow route
    
    # First tangent segment
    yellow_alignment.add_tangent("20+00", "24+04.67", name="Initial Tangent")
    
    # First spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="24+04.67", 
        sc_station="25+44.67", 
        cs_station="30+43.75", 
        st_station="31+83.75",
        degree_of_curve="9 00'00\"", 
        direction="right",
        name="First Curve"
    )
    
    # Second tangent segment
    yellow_alignment.add_tangent("31+83.75", "37+45.96", name="Middle Tangent")
    
    # Second spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="37+45.96", 
        sc_station="39+05.96",  # 39+05.96 = 37+45.96 + 160' (corrected spiral length)
        cs_station="40+60.67", 
        st_station="42+20.67",  # 42+20.67 = 40+60.67 + 160' (corrected spiral length)
        degree_of_curve="9 30'00\"",  # Corrected degree of curve: 9° 30' 00"
        direction="left",
        name="Second Curve"
    )
    
    # Third tangent segment (extended alignment)
    extended_tangent = yellow_alignment.add_tangent("42+20.67", "75+17.38", name="Extended Tangent")
    
    # Manually set bearing for the extended tangent
    # This is useful to follow the coastline more accurately
    extended_tangent.manual_bearing = 142.25  # Southeast direction (0=North, 90=East, 180=South)
    
    # Third spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="75+17.38", 
        sc_station="79+17.38",  # 79+17.38 = 75+17.38 + 400' (spiral length)
        cs_station="87+52.17", 
        st_station="91+52.17",  # 91+52.17 = 87+52.17 + 400' (spiral length)
        degree_of_curve="2 24'00\"",  # Degree of curve: 2° 24' 00"
        direction="right",
        name="Third Curve"
    )
    
    # Fourth tangent segment
    yellow_alignment.add_tangent("91+52.17", "94+72.45", name="Fourth Tangent")
    
    # Fourth spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="94+72.45", 
        sc_station="98+72.45",  # 98+72.45 = 94+72.45 + 400' (spiral length)
        cs_station="119+62.32", 
        st_station="123+62.32",  # 123+62.32 = 119+62.32 + 400' (spiral length)
        degree_of_curve="2 24'00\"",  # Degree of curve: 2° 24' 00"
        direction="left",
        name="Fourth Curve"
    )
    
    # Fifth tangent segment
    fifth_tangent = yellow_alignment.add_tangent("123+62.32", "162+59.46", name="Fifth Tangent")
    fifth_tangent.manual_bearing = 171  # Southeast direction (0=North, 90=East, 180=South)
    
    # Fifth spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="162+59.46", 
        sc_station="169+09.46",  # 169+09.46 = 162+59.46 + 650' (spiral length)
        cs_station="175+18.79",  # Note: This was labeled as SC in the query but should be CS
        st_station="181+68.79",  # 181+68.79 = 175+18.79 + 650' (spiral length)
        degree_of_curve="0 44'30\"",  # Degree of curve: 0° 44' 30" (very gentle curve)
        direction="left",
        name="Fifth Curve"
    )
    
    # Sixth tangent segment
    yellow_alignment.add_tangent("181+68.79", "196+22.24", name="Sixth Tangent")
    
    # Sixth spiral-curve-spiral segment (MT1 CURVE #6)
    yellow_alignment.add_curve(
        ts_station="196+22.24", 
        sc_station="202+72.24",  # 202+72.24 = 196+22.24 + 650' (spiral length from box)
        cs_station="208+28.94", 
        st_station="214+78.94",  # 216+43.12 = 209+93.12 + 650' (spiral length from box)
        degree_of_curve="0 44'30\"",  # Degree of curve from box: 0° 44' 30"
        direction="right",
        name="Sixth Curve (MT1 CURVE #6)"
    )
    
    # Seventh tangent segment
    seventh_tangent = yellow_alignment.add_tangent("214+78.94", "235+49.79", name="Seventh Tangent")
    
    # Seventh spiral-curve-spiral segment (CURVE #7)
    yellow_alignment.add_curve(
        ts_station="235+49.79", 
        sc_station="242+29.79",  # 242+29.79 = 235+49.79 + 680' (spiral length)
        cs_station="275+32.84", 
        st_station="282+12.84",  # 282+12.84 = 275+32.84 + 680' (spiral length)
        degree_of_curve="0 49'11\"",  # Degree of curve: 0° 49' 11"
        direction="right",  # Alternating direction from previous curve
        name="Seventh Curve"
    )
    
    # Eighth tangent segment
    eighth_tangent = yellow_alignment.add_tangent("282+12.84", "285+53.12", name="Eighth Tangent")
    
    # Eighth spiral-curve-spiral segment (CURVE #8)
    yellow_alignment.add_curve(
        ts_station="285+53.12", 
        sc_station="287+93.12",  # 287+93.12 = 285+53.12 + 240' (spiral length)
        cs_station="294+53.38", 
        st_station="296+93.38",  # 296+93.38 = 294+53.38 + 240' (spiral length)
        degree_of_curve="0 15'00\"",  # Degree of curve: 0° 15' 00"
        direction="right",  # Alternating direction from previous curve
        name="Eighth Curve"
    )
    
    # Ninth tangent segment
    ninth_tangent = yellow_alignment.add_tangent("296+93.38", "304+93.02", name="Ninth Tangent")
    
    # Add the entire alignment to the map
    yellow_alignment.add_to_map(
        m=m, 
        start_ref_point_name="STA_2000", 
        track_params=track_params
    )
    
    # Add animated outline to each segment of the yellow alignment
    for i, segment in enumerate(yellow_alignment.segments):
        segment_name = segment.name
        segment_tooltip = segment.name
        
        if segment.type == "tangent":
            segment_tooltip = f"{segment.name} ({segment.start_station} to {segment.end_station})"
        elif segment.type == "spiral_curve_spiral":
            curve_info = f"{segment.degree_value:.2f}° curve, {segment.direction} turn"
            radius_info = f"R={int(segment.radius_ft)}'"
            spiral_info = f"{int(segment.entry_spiral_length)}' spirals"
            segment_tooltip = f"{segment.name} ({segment.ts_station} to {segment.st_station})\n{curve_info}, {radius_info}, {spiral_info}"
        
        # Add AntPath for this segment
        if segment.type == "tangent":
            # For tangent segments, use regular dash pattern
            dash_array = [10, 20]
            delay = 800
        else:
            # For curve segments, use shorter dash pattern for more animated feel
            dash_array = [5, 15]
            delay = 600
            
        AntPath(
            locations=yellow_alignment.segment_coords[i],
            dash_array=dash_array,
            delay=delay,
            color='#FFD700',
            pulseColor='#FFFFFF',
            paused=False,
            weight=4,
            opacity=0.9,
            tooltip=segment_tooltip
        ).add_to(m)
    
    # Print out bearings at key points for debugging
    print("\nBearings at key points in railway alignment:")
    for i, segment in enumerate(yellow_alignment.segments):
        if segment.type == "tangent":
            bearing_str = f"{segment.manual_bearing}° (manual)" if segment.manual_bearing is not None else "calculated"
            print(f"Tangent {i+1} ({segment.name}): {bearing_str}")
        elif segment.type == "spiral_curve_spiral":
            print(f"Curve {i+1} ({segment.name}):")
            print(f"  TS bearing: {segment.ts_bearing:.2f}°")
            print(f"  SC bearing: {segment.sc_bearing:.2f}°")
            print(f"  CS bearing: {segment.cs_bearing:.2f}°")
            print(f"  ST bearing: {segment.st_bearing:.2f}°")
            print(f"  Direction: {segment.direction}")
            print(f"  Radius: {segment.radius_ft:.2f} ft")
            print(f"  Degree of curve: {segment.degree_value:.4f}°")

    # if we have a valid location, plot it + compute distances
    if location:
        addr_pt = (location.latitude, location.longitude)
        folium.Marker(addr_pt, tooltip=address, icon=folium.Icon(color="red")).add_to(m)

        st.sidebar.markdown("## Distances to Each Alignment")
        for name, data in expanded_alignments.items():
            # Create a LineString from the coordinates
            smoothed_coords = data
            
            # Create a LineString from the smoothed coordinates
            line = LineString([(lon, lat) for lat, lon in smoothed_coords])
            pt = Point(location.longitude, location.latitude)

            # find nearest point on the line
            nearest = line.interpolate(line.project(pt))
            nearest_lat, nearest_lon = nearest.y, nearest.x

            # geodesic distance in meters
            dist_m = geodesic(addr_pt, (nearest_lat, nearest_lon)).meters
            
            # Convert to different units and round
            dist_ft = round(dist_m * 3.28084)  # Convert meters to feet
            dist_m_rounded = round(dist_m / 10) * 10  # Round to nearest 10 meters
            dist_km = round(dist_m / 1000, 1)  # Round to 0.1 km
            dist_miles = round(dist_m * 0.000621371, 1)  # Round to 0.1 miles

            # draw a connector
            folium.PolyLine(
                [addr_pt, (nearest_lat, nearest_lon)],
                color="blue" if "Blue" in name else "magenta" if "Purple" in name else "green" if "Green" in name else "#FF7700",
                weight=2,
                dash_array="5,5"
            ).add_to(m)

            st.sidebar.write(f"**{name}:**")
            st.sidebar.write(f"- {dist_ft} ft")
            st.sidebar.write(f"- {dist_m_rounded} m")
            st.sidebar.write(f"- {dist_km} km")
            st.sidebar.write(f"- {dist_miles} mi")
            
        # Calculate distance to yellow track
        yellow_line = LineString([(lon, lat) for lat, lon in yellow_alignment.all_coords])
        pt = Point(location.longitude, location.latitude)
        
        # Find nearest point on the yellow track
        nearest = yellow_line.interpolate(yellow_line.project(pt))
        nearest_lat, nearest_lon = nearest.y, nearest.x
        
        # Calculate geodesic distance in meters
        dist_m = geodesic(addr_pt, (nearest_lat, nearest_lon)).meters
        
        # Convert to different units and round
        dist_ft = round(dist_m * 3.28084)  # Convert meters to feet
        dist_m_rounded = round(dist_m / 10) * 10  # Round to nearest 10 meters
        dist_km = round(dist_m / 1000, 1)  # Round to 0.1 km
        dist_miles = round(dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (nearest_lat, nearest_lon)],
            color="#FF7700",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Yellow track
        st.sidebar.write("**Yellow Route: Engineering Alignment:**")
        st.sidebar.write(f"- {dist_ft} ft")
        st.sidebar.write(f"- {dist_m_rounded} m")
        st.sidebar.write(f"- {dist_km} km")
        st.sidebar.write(f"- {dist_miles} mi")
        
        # Add more information about which segment of the yellow track is closest
        # Find which segment the nearest point belongs to
        min_distance = float('inf')
        closest_segment = None
        segment_index = None
        
        for i, segment in enumerate(yellow_alignment.segments):
            segment_linestring = LineString([(lon, lat) for lat, lon in yellow_alignment.segment_coords[i]])
            segment_nearest = segment_linestring.interpolate(segment_linestring.project(pt))
            segment_dist = geodesic(addr_pt, (segment_nearest.y, segment_nearest.x)).meters
            
            if segment_dist < min_distance:
                min_distance = segment_dist
                closest_segment = segment
                segment_index = i
        
        if closest_segment:
            # Bold header for closest segment
            st.sidebar.markdown(f"**Closest to: {closest_segment.name}**")
            
            # Determine approximate station of the closest point
            if closest_segment.type == "tangent":
                # Calculate percentage along the segment
                percentage = segment_linestring.project(pt) / segment_linestring.length
                
                # Interpolate station value
                station_value = closest_segment.start_station_value + percentage * (closest_segment.end_station_value - closest_segment.start_station_value)
                
                # Format station
                station_formatted = format_station(station_value)
                
                st.sidebar.write(f"Approximate Station: {station_formatted}")
                
            elif closest_segment.type == "spiral_curve_spiral":
                # For curves, show the type of element (entry spiral, circular curve, exit spiral)
                # Determine which part of the curve is closest
                
                # Calculate total curve length
                total_length = closest_segment.entry_spiral_length + closest_segment.circular_arc_length + closest_segment.exit_spiral_length
                
                # Get normalized distance along the curve
                curve_distance = segment_linestring.project(pt) / segment_linestring.length * total_length
                
                if curve_distance < closest_segment.entry_spiral_length:
                    # In entry spiral
                    percentage = curve_distance / closest_segment.entry_spiral_length
                    station_value = closest_segment.ts_station_value + percentage * (closest_segment.sc_station_value - closest_segment.ts_station_value)
                    element_type = "Entry Spiral"
                elif curve_distance < closest_segment.entry_spiral_length + closest_segment.circular_arc_length:
                    # In circular curve
                    distance_in_curve = curve_distance - closest_segment.entry_spiral_length
                    percentage = distance_in_curve / closest_segment.circular_arc_length
                    station_value = closest_segment.sc_station_value + percentage * (closest_segment.cs_station_value - closest_segment.sc_station_value)
                    element_type = "Circular Curve"
                else:
                    # In exit spiral
                    distance_in_spiral = curve_distance - closest_segment.entry_spiral_length - closest_segment.circular_arc_length
                    percentage = distance_in_spiral / closest_segment.exit_spiral_length
                    station_value = closest_segment.cs_station_value + percentage * (closest_segment.st_station_value - closest_segment.cs_station_value)
                    element_type = "Exit Spiral"
                
                # Format station
                station_formatted = format_station(station_value)
                
                st.sidebar.write(f"Element: {element_type}")
                st.sidebar.write(f"Approximate Station: {station_formatted}")
                
                # Add information about the curve
                if element_type == "Circular Curve":
                    radius_ft = closest_segment.radius_ft
                    degree_curve = closest_segment.degree_value
                    st.sidebar.write(f"Radius: {int(radius_ft)} ft")
                    st.sidebar.write(f"Degree of Curve: {degree_curve:.2f}°")

    # --- 4. render ---
    # Set the map height to fill available space while leaving room for header and footer
    st_folium(m, width="100%")

# --- 5. Footer with credits and disclaimer ---
# Create footer using native Streamlit elements
st.markdown("<div class='custom-footer'>", unsafe_allow_html=True)
footer_cols = st.columns([3, 1])
with footer_cols[0]:
    st.markdown("""
    The four proposed routes and their distance calculations are based on the most recent SANDAG documentation.
    """)
with footer_cols[1]:
    st.markdown("""
    **Created by:** Nathan Qiu  
    **Contact:** [nathanqiu07@gmail.com](mailto:nathanqiu07@gmail.com)
    """)
st.markdown("</div>", unsafe_allow_html=True)
