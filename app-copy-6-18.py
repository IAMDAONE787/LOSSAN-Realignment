# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import numpy as np
from folium.plugins import AntPath
from utils import create_curved_path, create_circular_curve, create_spiral_curve
from utils.engineering_coords import (
    calculate_track_parameters, 
    station_to_gis, 
    parse_station,
    parse_angle,
    calculate_radius_from_degree_of_curve,
    format_station
)
from utils.spiral_curve import create_railway_spiral, add_railway_spiral_to_map
from utils.circular_curve import create_railway_circular_curve, add_railway_circular_curve_to_map
from utils.tangent_line import add_railway_tangent_to_map
from utils.railway_curve import add_complete_railway_curve_to_map, add_complete_railway_alignment_to_map
from utils.railway_alignment import RailwayAlignment, TangentSegment, CurveSegment
from utils.portal import Portal
from opencage.geocoder import OpenCageGeocode

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
    .folium-map .leaflet-pane path:not(.yellow-bridge-overlay) {
        pointer-events: none !important;
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
    # Green track will now be an engineering track, so we'll remove it from ALIGNMENTS
    ALIGNMENTS = {}

    # --- 2. address input & geocoding ---
    st.sidebar.subheader("Search Location")
    
    # Simple text input for address without autocomplete
    address_input = st.sidebar.text_input("Enter address", value=st.session_state.get("address", ""))
    
    # Search button
    search = st.sidebar.button("Search")

    # Initialize session state for location if not present
    if "location" not in st.session_state:
        st.session_state["location"] = None

    if search and address_input:
        # Initialize OpenCage geocoder with API key
        opencage_api_key = "e4a3fe37fe3d469499dc77e798f65245"  # Replace with your OpenCage API key
        geocoder = OpenCageGeocode(opencage_api_key)
        
        try:
            # Define bounds for San Diego area
            socal_bounds = "-117.4,32.5,-116.8,33.3"  # San Diego County area
            
            # Perform geocoding with bounds constraint
            results = geocoder.geocode(address_input, bounds=socal_bounds)
            
            if results and len(results):
                # Extract location data from the first result
                location_data = results[0]
                
                # Create a location object with the required attributes
                class LocationResult:
                    def __init__(self, lat, lng, formatted):
                        self.latitude = lat
                        self.longitude = lng
                        self.address = formatted
                
                location = LocationResult(
                    location_data['geometry']['lat'],
                    location_data['geometry']['lng'],
                    location_data['formatted']
                )
                
                st.session_state["address"] = address_input
                st.session_state["location"] = location
            else:
                st.sidebar.error("Address not found")
                st.session_state["location"] = None
        except Exception as e:
            st.sidebar.error(f"Geocoding service error: {str(e)}")
            st.session_state["location"] = None

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
    yellow_first_tangent = yellow_alignment.add_tangent("20+00", "24+04.67", name="Initial Tangent")
    
    # First spiral-curve-spiral segment
    yellow_first_curve = yellow_alignment.add_curve(
        ts_station="24+04.67", 
        sc_station="25+44.67", 
        cs_station="30+43.75", 
        st_station="31+83.75",
        degree_of_curve="9 00'00\"", 
        direction="right",
        name="First Curve"
    )
    
    # Second tangent segment
    yellow_second_tangent = yellow_alignment.add_tangent("31+83.75", "37+45.96", name="Middle Tangent")
    
    # Second spiral-curve-spiral segment
    yellow_second_curve = yellow_alignment.add_curve(
        ts_station="37+45.96", 
        sc_station="39+05.96",  # 39+05.96 = 37+45.96 + 160' (corrected spiral length)
        cs_station="40+60.67", 
        st_station="42+20.67",  # 42+20.67 = 40+60.67 + 160' (corrected spiral length)
        degree_of_curve="9 30'00\"",  # Corrected degree of curve: 9° 30' 00"
        direction="left",
        name="Second Curve"
    )
    
    # Third tangent segment (extended alignment)
    yellow_third_tangent = yellow_alignment.add_tangent("42+20.67", "75+17.38", name="Extended Tangent")
    
    # Manually set bearing for the extended tangent
    # This is useful to follow the coastline more accurately
    yellow_third_tangent.manual_bearing = 142.25  # Southeast direction (0=North, 90=East, 180=South)
    
    # Third spiral-curve-spiral segment
    yellow_third_curve = yellow_alignment.add_curve(
        ts_station="75+17.38", 
        sc_station="79+17.38",  # 79+17.38 = 75+17.38 + 400' (spiral length)
        cs_station="87+52.17", 
        st_station="91+52.17",  # 91+52.17 = 87+52.17 + 400' (spiral length)
        degree_of_curve="2 24'00\"",  # Degree of curve: 2° 24' 00"
        direction="right",
        name="Third Curve"
    )
    
    # Fourth tangent segment
    yellow_fourth_tangent = yellow_alignment.add_tangent("91+52.17", "94+72.45", name="Fourth Tangent")
    
    # Fourth spiral-curve-spiral segment
    yellow_fourth_curve = yellow_alignment.add_curve(
        ts_station="94+72.45", 
        sc_station="98+72.45",  # 98+72.45 = 94+72.45 + 400' (spiral length)
        cs_station="119+62.32", 
        st_station="123+62.32",  # 123+62.32 = 119+62.32 + 400' (spiral length)
        degree_of_curve="2 24'00\"",  # Degree of curve: 2° 24' 00"
        direction="left",
        name="Fourth Curve"
    )
    
    # Fifth tangent segment
    yellow_fifth_tangent = yellow_alignment.add_tangent("123+62.32", "162+59.46", name="Fifth Tangent")
    yellow_fifth_tangent.manual_bearing = 171  # Southeast direction (0=North, 90=East, 180=South)
    
    # Fifth spiral-curve-spiral segment
    yellow_fifth_curve = yellow_alignment.add_curve(
        ts_station="162+59.46", 
        sc_station="169+09.46",  # 169+09.46 = 162+59.46 + 650' (spiral length)
        cs_station="175+18.79",  # Note: This was labeled as SC in the query but should be CS
        st_station="181+68.79",  # 181+68.79 = 175+18.79 + 650' (spiral length)
        degree_of_curve="0 44'30\"",  # Degree of curve: 0° 44' 30" (very gentle curve)
        direction="left",
        name="Fifth Curve"
    )
    
    # Sixth tangent segment
    yellow_sixth_tangent = yellow_alignment.add_tangent("181+68.79", "196+22.24", name="Sixth Tangent")
    
    # Sixth spiral-curve-spiral segment (MT1 CURVE #6)
    yellow_sixth_curve = yellow_alignment.add_curve(
        ts_station="196+22.24", 
        sc_station="202+72.24",  # 202+72.24 = 196+22.24 + 650' (spiral length from box)
        cs_station="208+28.94", 
        st_station="214+78.94",  # 216+43.12 = 209+93.12 + 650' (spiral length from box)
        degree_of_curve="0 44'30\"",  # Degree of curve from box: 0° 44' 30"
        direction="right",
        name="Sixth Curve (MT1 CURVE #6)"
    )
    
    # Seventh tangent segment
    yellow_seventh_tangent = yellow_alignment.add_tangent("214+78.94", "235+49.79", name="Seventh Tangent")
    
    # Seventh spiral-curve-spiral segment (CURVE #7)
    yellow_seventh_curve = yellow_alignment.add_curve(
        ts_station="235+49.79", 
        sc_station="242+29.79",  # 242+29.79 = 235+49.79 + 680' (spiral length)
        cs_station="275+32.84", 
        st_station="282+12.84",  # 282+12.84 = 275+32.84 + 680' (spiral length)
        degree_of_curve="0 49'11\"",  # Degree of curve: 0° 49' 11"
        direction="right",  # Alternating direction from previous curve
        name="Seventh Curve"
    )
    
    # Eighth tangent segment
    yellow_eighth_tangent = yellow_alignment.add_tangent("282+12.84", "285+53.12", name="Eighth Tangent")
    
    # Eighth spiral-curve-spiral segment (CURVE #8)
    yellow_eighth_curve = yellow_alignment.add_curve(
        ts_station="285+53.12", 
        sc_station="287+93.12",  # 287+93.12 = 285+53.12 + 240' (spiral length)
        cs_station="294+53.38", 
        st_station="296+93.38",  # 296+93.38 = 294+53.38 + 240' (spiral length)
        degree_of_curve="0 15'00\"",  # Degree of curve: 0° 15' 00"
        direction="right",  # Alternating direction from previous curve
        name="Eighth Curve"
    )
    
    # Ninth tangent segment
    yellow_ninth_tangent = yellow_alignment.add_tangent("296+93.38", "304+93.02", name="Ninth Tangent")
    
    # === BLUE TRACK ENGINEERING MODEL ===
    # Create the blue track using the engineering specifications and directly add to map

    # Create a new Railway Alignment for the Blue route
    blue_alignment = RailwayAlignment(name="Blue Route: Under Crest Canyon", color="blue")
    
    # Add reference points for the blue track
    blue_sta_500_coords = (32.9731225, -117.2667758)  # 5+00 station
    blue_sta_1000_coords = (32.9717752, -117.2664515)  # 10+00 station
    
    blue_alignment.add_reference_point("STA_500", blue_sta_500_coords, 500)
    blue_alignment.add_reference_point("STA_1000", blue_sta_1000_coords, 1000)
    
    # Calculate track parameters based on reference points
    blue_track_params = blue_alignment.calculate_track_params("STA_500", "STA_1000")
    
    # Define segments for the Blue route - initial tangent
    blue_first_tangent = blue_alignment.add_tangent("5+00", "17+46.12", name="Initial Tangent")
    
    # Add a curve similar to the first segment of the original blue route
    blue_first_curve = blue_alignment.add_curve(
        ts_station="17+46.12",
        sc_station="23+96.12",
        cs_station="54+05.81",
        st_station="60+55.81",
        degree_of_curve="0 48'00\"",
        direction="right",
        name="First Curve"
    )
    
    # Add next tangent
    blue_second_tangent = blue_alignment.add_tangent("60+55.81", "64+00.52", name="Second Tangent")
    blue_second_tangent.manual_bearing = 141.5  # Southeast direction (0=North, 90=East, 180=South)

    # Add second curve (sharper turn toward southeast)
    blue_second_curve = blue_alignment.add_curve(
        ts_station="64+00.52",
        sc_station="70+80.52",
        cs_station="96+80.99",
        st_station="103+60.99",
        degree_of_curve="0 49'35\"",
        direction="left",
        name="Second Curve"
    )
    
    # Add third tangent going southeast
    blue_third_tangent = blue_alignment.add_tangent("103+60.99", "116+60.92", name="Third Tangent")
    
    # Add the curve near Del Mar Heights Road
    blue_third_curve = blue_alignment.add_curve(
        ts_station="116+60.92",
        sc_station="123+40.92",
        cs_station="146+18.69",
        st_station="152+98.69",
        degree_of_curve="0 49'35\"",
        direction="right",
        name="Third Curve"
    )
    
    # Add fourth tangent 
    blue_fourth_tangent = blue_alignment.add_tangent("152+98.69", "156+48.69", name="Fourth Tangent")
    blue_fourth_tangent.manual_bearing = 141.5
    
    # Add fourth curve to align with endpoint
    blue_fourth_curve = blue_alignment.add_curve(
        ts_station="156+48.69",
        sc_station="163+28.69",
        cs_station="192+18.38",
        st_station="198+98.38",
        degree_of_curve="0 49'35\"",
        direction="left",
        name="Fourth Curve"
    )
    
    # Add fifth tangent to reach the end point
    blue_fifth_tangent = blue_alignment.add_tangent("198+98.38", "204+89.02", name="Fifth Tangent")
    #blue_fifth_tangent.manual_bearing = 170  # Southeast direction (0=North, 90=East, 180=South)
    
    # Add fifth curve
    blue_fifth_curve = blue_alignment.add_curve(
        ts_station="204+89.02",
        sc_station="211+69.02",
        cs_station="244+71.53",
        st_station="251+51.53",
        degree_of_curve="0 49'11\"",
        direction="right",
        name="Fifth Curve"
    )
    
    # Add sixth tangent
    blue_sixth_tangent = blue_alignment.add_tangent("251+51.53", "255+07.34", name="Sixth Tangent")
    
    # Add sixth curve
    blue_sixth_curve = blue_alignment.add_curve(
        ts_station="255+07.34",
        sc_station="257+27.34",
        cs_station="264+05.11",
        st_station="266+25.11",
        degree_of_curve="0 15'00\"",
        direction="left",
        name="Sixth Curve"
    )

    blue_seventh_tangent = blue_alignment.add_tangent("266+25.11", "274+32.35", name="Seventh Tangent")
    blue_seventh_tangent.manual_bearing = 135

    # === PURPLE TRACK ENGINEERING MODEL ===
    # Create the purple track using the engineering specifications and directly add to map

    # Create a new Railway Alignment for the Purple route
    purple_alignment = RailwayAlignment(name="Purple Route: Under Camino Del Mar", color="magenta")

    # Add reference points for the purple track
    purple_sta_500_coords = (32.9731225, -117.2667758)  # 5+00 station
    purple_sta_1000_coords = (32.9717752, -117.2664515)  # 10+00 station

    purple_alignment.add_reference_point("STA_500", purple_sta_500_coords, 500)
    purple_alignment.add_reference_point("STA_1000", purple_sta_1000_coords, 1000)

    # Calculate track parameters based on reference points
    purple_track_params = purple_alignment.calculate_track_params("STA_500", "STA_1000")

    # Define segments for the Purple route - initial tangent
    purple_first_tangent = purple_alignment.add_tangent("5+00", "33+23.02", name="Initial Tangent")

    # Add first curve (gentle curve to follow Camino Del Mar)
    purple_first_curve = purple_alignment.add_curve(
        ts_station="33+23.02",
        sc_station="35+73.02",
        cs_station="46+03.60",
        st_station="48+53.60", #48+53.60
        degree_of_curve="1 25'00\"", #1 00'00\"
        direction="left",
        name="First Curve"
    )

    # Add second tangent
    purple_second_tangent = purple_alignment.add_tangent("48+53.60", "51+91.55", name="Second Tangent")
    purple_second_tangent.manual_bearing = 181.75  # Southeast direction

    # Add second curve (sharper turn toward southeast)
    purple_second_curve = purple_alignment.add_curve(
        ts_station="51+91.55",
        sc_station="54+41.55",
        cs_station="71+12.55",
        st_station="73+62.55",
        degree_of_curve="1 00'00\"",
        direction="right",
        name="Second Curve"
    )

    # Add third tangent going southeast
    purple_third_tangent = purple_alignment.add_tangent("73+62.55", "91+37.23", name="Third Tangent")

    # Add the curve near Del Mar Heights Road
    purple_third_curve = purple_alignment.add_curve(
        ts_station="91+37.23",
        sc_station="94+37.23",
        cs_station="108+41.79",
        st_station="111+41.79",
        degree_of_curve="1 06'00\"",
        direction="left",
        name="Third Curve"
    )

    # Add fourth tangent 
    purple_fourth_tangent = purple_alignment.add_tangent("111+41.79", "114+31.56", name="Fourth Tangent")
    #purple_fourth_tangent.manual_bearing = 150  # More southerly direction

    # Add fourth curve to align with endpoint
    purple_fourth_curve = purple_alignment.add_curve(
        ts_station="114+31.56",
        sc_station="117+01.56",
        cs_station="152+41.45",
        st_station="155+11.45",
        degree_of_curve="1 03'30\"",
        direction="right",
        name="Fourth Curve"
    )

    # Add fifth tangent to reach the end point
    purple_fifth_tangent = purple_alignment.add_tangent("155+11.45", "183+01.22", name="Fifth Tangent")

    # Add fifth curve
    purple_fifth_curve = purple_alignment.add_curve(
        ts_station="183+01.22",
        sc_station="188+81.22",
        cs_station="197+17.88",
        st_station="202+97.88",
        degree_of_curve="0 30'00\"",
        direction="right",
        name="Fifth Curve"
    )

    # Add sixth tangent
    purple_sixth_tangent = purple_alignment.add_tangent("202+97.88", "226+46.37", name="Sixth Tangent")
    purple_sixth_tangent.manual_bearing = 133  # More southerly direction

    # Add sixth curve
    purple_sixth_curve = purple_alignment.add_curve(
        ts_station="226+46.37",
        sc_station="233+26.37",
        cs_station="237.58+89",
        st_station="244+38.89",
        degree_of_curve="0 49'35\"",
        direction="left",
        name="Sixth Curve"
    )

    purple_seventh_tangent = purple_alignment.add_tangent("244+38.89", "280+89.19", name="Seventh Tangent")
    #purple_seventh_tangent.manual_bearing = 160  # More southerly direction

    

    # === GREEN TRACK ENGINEERING MODEL ===
    # Create the green track using the engineering specifications based on the purple track
    
    # Create a new Railway Alignment for the Green route
    green_alignment = RailwayAlignment(name="Green Route: Del Mar Bluffs Double-Track", color="green")
    
    # Add reference points for the green track
    green_sta_500_coords = (32.9731225, -117.2667758)  # 5+00 station
    #green_sta_1000_coords = (32.9716252, -117.2664515)  # 10+00 station (mannually edited)
    green_sta_1000_coords = (32.9717752, -117.2664515)  # 10+00 station
    
    green_alignment.add_reference_point("STA_500", green_sta_500_coords, 500)
    green_alignment.add_reference_point("STA_1000", green_sta_1000_coords, 1000)
    
    # Calculate track parameters directly using the engineering_coords function
    # This ensures precise alignment between reference points
    green_track_params = calculate_track_parameters(
        point1=green_sta_500_coords,
        station1=500,
        point2=green_sta_1000_coords,
        station2=1000
    )
    
    # Define segments for the Green route - initial tangent
    # First tangent from STA_500 to STA_1000 (exactly between reference points)
    green_first_tangent = green_alignment.add_tangent("5+00", "10+00", name="Initial Reference Tangent")
    
    # Continue with the rest of the alignment
    green_pre_tangent = green_alignment.add_tangent("10+00", "12+05.15", name="Pre-Curve Tangent")
    
    green_pre_curve = green_alignment.add_curve(
        ts_station="12+05.15",
        sc_station="14+15.15",
        cs_station="17+79.87",
        st_station="19+89.87",
        degree_of_curve="0 40'00\"",
        direction="left",
        name="First Curve"
    )
    
    # Add first curve (gentle curve to follow bluffs)
    green_first_curve = green_alignment.add_curve(
        ts_station="19+89.87",
        sc_station="35+22.79",
        cs_station="36+28.04",
        st_station="37+28.04",
        degree_of_curve="2 55'00\"", #2 09'01
        direction="left",
        name="First Curve"
    )
    
    # Add second tangent
    green_second_tangent = green_alignment.add_tangent("37+28.04", "53+08.78", name="Second Tangent")
    #green_second_tangent.manual_bearing = 178.5
    
    # Add second curve
    green_second_curve = green_alignment.add_curve(
        ts_station="53+08.78",
        sc_station="55+58.78",
        cs_station="60+27.97",
        st_station="62+77.96",
        degree_of_curve="4 09'00\"",
        direction="right",
        name="Second Curve"
    )
    
    # Add third tangent
    green_third_tangent = green_alignment.add_tangent("62+77.96", "71+41.19", name="Third Tangent")
    
    # Add third curve
    green_third_curve = green_alignment.add_curve(
        ts_station="71+41.19",
        sc_station="73+81.19",
        cs_station="76+68.70",
        st_station="79+08.70",
        degree_of_curve="1 20'00\"",
        direction="right",
        name="Third Curve"
    )
    
    # Add fourth tangent
    green_fourth_tangent = green_alignment.add_tangent("79+08.70", "101+45.73", name="Fourth Tangent")
    green_fourth_tangent.manual_bearing = 161
    
    # Add fourth curve
    green_fourth_curve = green_alignment.add_curve(
        ts_station="101+45.73",
        sc_station="105+05.73",
        cs_station="109+96.76",
        st_station="113+56.76",
        degree_of_curve="0 44'35\"",
        direction="left",
        name="Fourth Curve"
    )
    
    # Add fifth tangent
    green_fifth_tangent = green_alignment.add_tangent("113+56.76", "129+11.51", name="Fifth Tangent")
    
    # Add fifth curve
    green_fifth_curve = green_alignment.add_curve(
        ts_station="129+11.51",
        sc_station="131+61.51",
        cs_station="138+79.54",
        st_station="141+29.54",
        degree_of_curve="2 45'00\"", #3 07'00
        direction="right",
        name="Fifth Curve"
    )
    
    # Add sixth tangent
    green_sixth_tangent = green_alignment.add_tangent("141+29.54", "187+10.02", name="Sixth Tangent")
    #green_sixth_tangent.manual_bearing = 135
    
    # Add sixth curve
    green_sixth_curve = green_alignment.add_curve(
        ts_station="187+10.02",
        sc_station="192+90.02",
        cs_station="201+26.67",
        st_station="207+06.67",
        degree_of_curve="0 30'00\"",
        direction="right",
        name="Sixth Curve"
    )
    
    # Add seventh tangent
    green_seventh_tangent = green_alignment.add_tangent("207+06.67", "230+55.17", name="Seventh Tangent")
    
    # Add seventh curve
    green_seventh_curve = green_alignment.add_curve(
        ts_station="230+55.17",
        sc_station="237+35.17",
        cs_station="241+67.68",
        st_station="248+47.68",
        degree_of_curve="0 45'35\"",
        direction="left",
        name="Seventh Curve"
    )

    # Add eighth tangent
    green_eighth_tangent = green_alignment.add_tangent("248+47.68", "284+97.94", name="Eighth Tangent")


    # === NORTHERN YELLOW TRACK ENGINEERING MODEL ===
    # Create the Northern Yellow track following the San Dieguito River path shown in the image
    
    # Create a new Railway Alignment for the Northern Yellow route with orange color
    northern_yellow_alignment = RailwayAlignment(name="Northern Yellow Route", color="orange")
    
    # Use the same reference points as the original Yellow track
    northern_yellow_alignment.add_reference_point("STA_2000", station_2000_coords, 2000)
    northern_yellow_alignment.add_reference_point("STA_2500", station_2500_coords, 2500)
    
    # Calculate track parameters based on reference points - same as yellow track
    northern_yellow_track_params = yellow_alignment.calculate_track_params("STA_2000", "STA_2500")
    
    # Define segments for the Northern Yellow route
    # Start further back with initial tangent from the coast
    northern_yellow_first_tangent = northern_yellow_alignment.add_tangent("10+00", "19+00", name="First Tangent")
    
    # First curve to approach the river
    northern_yellow_first_curve = northern_yellow_alignment.add_curve(
        ts_station="19+00",
        sc_station="22+00",
        cs_station="25+00",
        st_station="28+00",
        degree_of_curve="9 00'00\"",
        direction="right",
        name="First Curve"
    )
    
    # Second tangent (along Del Mar Fairgrounds)
    northern_yellow_second_tangent = northern_yellow_alignment.add_tangent("28+00", "35+00", name="Second Tangent")
    
    # Second curve
    northern_yellow_river_curve = northern_yellow_alignment.add_curve(
        ts_station="35+00",
        sc_station="37+00",
        cs_station="40+00",
        st_station="43+00",
        degree_of_curve="7 00'00\"",
        direction="right",
        name="Second Curve"
    )
    
    # Third tangent (along the south side of Del Mar Racing)
    northern_yellow_third_tangent = northern_yellow_alignment.add_tangent("43+00", "65+00", name="Third Tangent")
    northern_yellow_third_tangent.manual_bearing = 75

    # Third curve
    northern_yellow_third_curve = northern_yellow_alignment.add_curve(
        ts_station="65+00",
        sc_station="68+00",
        cs_station="73+00",
        st_station="76+00",
        degree_of_curve="9 30'00\"",
        direction="left",
        name="Third Curve"
    )

    # Fourth Tangent
    northern_yellow_fourth_tangent = northern_yellow_alignment.add_tangent("76+00", "120+00", name="Fourth Tangent")
    northern_yellow_fourth_tangent.manual_bearing = 163
    
    # Fourth spiral-curve-spiral segment
    northern_yellow_fourth_curve = northern_yellow_alignment.add_curve(
        ts_station="120+00",
        sc_station="125+00",
        cs_station="126+00",
        st_station="131+00",
        degree_of_curve="2 00'00\"",
        direction="left",
        name="Fourth Curve"
    )
    
    # Fifth tangent segment
    northern_yellow_fifth_tangent = northern_yellow_alignment.add_tangent("123+62.32", "175+59.46", name="Fifth Tangent")
    northern_yellow_fifth_tangent.manual_bearing = 171  # Southeast direction (0=North, 90=East, 180=South)
    
    # Fifth spiral-curve-spiral segment
    northern_yellow_fifth_curve = northern_yellow_alignment.add_curve(
        ts_station="175+59.46",
        sc_station="182+09.46",
        cs_station="188+18.79",
        st_station="194+68.79",
        degree_of_curve="0 44'30\"",
        direction="left",
        name="Fifth Curve"
    )
    
    # Sixth tangent segment
    northern_yellow_sixth_tangent = northern_yellow_alignment.add_tangent("194+68.79", "209+22.24", name="Sixth Tangent")
    
    # Sixth spiral-curve-spiral segment (MT1 CURVE #6)
    northern_yellow_sixth_curve = northern_yellow_alignment.add_curve(
        ts_station="209+22.24", 
        sc_station="215+72.24",
        cs_station="221+28.94", 
        st_station="227+78.94",
        degree_of_curve="0 44'30\"",
        direction="right",
        name="Sixth Curve (MT1 CURVE #6)"
    )
    
    # Seventh tangent segment
    northern_yellow_seventh_tangent = northern_yellow_alignment.add_tangent("227+78.94", "248+49.79", name="Seventh Tangent")
    
    # Seventh spiral-curve-spiral segment (CURVE #7)
    northern_yellow_seventh_curve = northern_yellow_alignment.add_curve(
        ts_station="248+49.79", 
        sc_station="255+29.79",
        cs_station="288+32.84", 
        st_station="295+12.84",
        degree_of_curve="0 49'11\"",
        direction="right",
        name="Seventh Curve"
    )
    
    # Eighth tangent segment
    northern_yellow_eighth_tangent = northern_yellow_alignment.add_tangent("295+12.84", "298+53.12", name="Eighth Tangent")
    
    # Eighth spiral-curve-spiral segment (CURVE #8)
    northern_yellow_eighth_curve = northern_yellow_alignment.add_curve(
        ts_station="298+53.12", 
        sc_station="300+93.12",
        cs_station="307+53.38", 
        st_station="309+93.38",
        degree_of_curve="0 15'00\"",
        direction="right",
        name="Eighth Curve"
    )
    
    # Ninth tangent segment
    northern_yellow_ninth_tangent = northern_yellow_alignment.add_tangent("309+93.38", "317+93.02", name="Ninth Tangent")
    # Add CSS to disable hover/tooltips on original polylines
    css = """
    <style>
    .folium-map .leaflet-pane path:not(.yellow-bridge-overlay) {
        pointer-events: none !important;
    }
    </style>
    """
    
    # Add the CSS to the map
    m.get_root().html.add_child(folium.Element(css))
    
    # Add the entire alignment to the map
    yellow_alignment.add_to_map(
        m=m, 
        start_ref_point_name="STA_2000", 
        track_params=track_params,
        add_markers=False  # Hide all pin points
    )
    
    # Add the blue alignment to the map
    blue_alignment.add_to_map(
        m=m,
        start_ref_point_name="STA_500",
        track_params=blue_track_params,
        add_markers=False  # Hide all pin points
    )
    
    # Add the purple alignment to the map
    purple_alignment.add_to_map(
        m=m,
        start_ref_point_name="STA_500",
        track_params=purple_track_params,
        add_markers=False  # Hide all pin points
    )
    
    # Add the green alignment to the map
    green_alignment.add_to_map(
        m=m,
        start_ref_point_name="STA_500",
        track_params=green_track_params,
        add_markers=False  # Hide all pin points
    )
    
    # Add the Northern Yellow alignment to the map
    northern_yellow_alignment.add_to_map(
        m=m,
        start_ref_point_name="STA_2000",
        track_params=northern_yellow_track_params,
        add_markers=False  # Hide all pin points
    )
    
    # Define all portals using the Portal class
    portals = [
        # Blue track portals
        Portal(
            name="Jimmy Durante Blvd Portal",
            track_alignment=blue_alignment,
            station_value=2600,  # 26+00
            color="blue",
            description="Western portal of the Blue Route tunnel under Jimmy Durante Blvd"
        ),
        
        # Purple track portals
        Portal(
            name="Torrey Pines Rd West Portal",
            track_alignment=purple_alignment,
            station_value=13000,  # 130+00
            color="magenta",
            description="Western portal of the Purple Route tunnel under Torrey Pines Road"
        ),
        
        # Yellow track portals
        Portal(
            name="Racetrack View Dr Portal",
            track_alignment=yellow_alignment,
            station_value=8200,  # 82+00
            color="red",
            description="Northern portal of the Yellow Route tunnel at Racetrack View Drive"
        ),
        
        Portal(
            name="I-5 Knoll Portal",
            track_alignment=yellow_alignment,
            station_value=parse_station("235+49.79"),  # TS station of the seventh curve
            color="#B8860B",  # Dark goldenrod
            description="Southern portal of the Yellow Route tunnel at I-5 Knoll"
        )
    ]
    
    # Add all portals to the map
    for portal in portals:
        portal.add_to_map(m)
    
    # Add an animated green path overlay
    if green_alignment.all_coords:
        # Add a solid base line
        folium.PolyLine(
            locations=green_alignment.all_coords,
            color='green',
            weight=7,
            opacity=0.7,
            tooltip="Green Route: Del Mar Bluffs Double-Track"
        ).add_to(m)
        
        # Add animated path
        AntPath(
            locations=green_alignment.all_coords,
            dash_array=[10, 20],
            delay=800,
            color='green',
            pulseColor='white',
            paused=False,
            weight=5,
            opacity=0.9,
            tooltip="Green Route: Del Mar Bluffs Double-Track",
            className="green-route-overlay"  # Special class to allow hover
        ).add_to(m)
    
    # Add an animated blue path overlay
    if blue_alignment.all_coords:
        # Add a solid base line
        folium.PolyLine(
            locations=blue_alignment.all_coords,
            color='blue',
            weight=7,
            opacity=0.7,
            tooltip="Blue Route: Under Crest Canyon"
        ).add_to(m)
        
        # Add animated path
        AntPath(
            locations=blue_alignment.all_coords,
            dash_array=[10, 20],
            delay=800,
            color='blue',
            pulseColor='white',
            paused=False,
            weight=5,
            opacity=0.9,
            tooltip="Blue Route: Under Crest Canyon",
            className="blue-route-overlay"  # Special class to allow hover
        ).add_to(m)
    
    # Add an animated purple path overlay
    if purple_alignment.all_coords:
        # Add a solid base line
        folium.PolyLine(
            locations=purple_alignment.all_coords,
            color='magenta',
            weight=7,
            opacity=0.7,
            tooltip="Purple Route: Under Camino Del Mar"
        ).add_to(m)
        
        # Add animated path
        AntPath(
            locations=purple_alignment.all_coords,
            dash_array=[10, 20],
            delay=800,
            color='magenta',
            pulseColor='white',
            paused=False,
            weight=5,
            opacity=0.9,
            tooltip="Purple Route: Under Camino Del Mar",
            className="purple-route-overlay"  # Special class to allow hover
        ).add_to(m)
    
    # Add animated path for the Northern Yellow track
    if northern_yellow_alignment.all_coords:
        # Add a solid base line
        folium.PolyLine(
            locations=northern_yellow_alignment.all_coords,
            color='orange',
            weight=7,
            opacity=0.7,
            tooltip="Northern Yellow Route"
        ).add_to(m)
        
        # Add animated path
        AntPath(
            locations=northern_yellow_alignment.all_coords,
            dash_array=[10, 20],
            delay=800,
            color='orange',
            pulseColor='white',
            paused=False,
            weight=5,
            opacity=0.9,
            tooltip="Northern Yellow Route",
            className="northern-yellow-route-overlay"  # Special class to allow hover
        ).add_to(m)
    
    # Add Jimmy Durante Blvd Portal marker on the blue track at station 26+00
    # Use the improved station_to_gis function with the alignment parameter
    from utils.engineering_coords import station_to_gis
    
    # Get the blue track's reference points
    blue_ref_point = blue_alignment.reference_points["STA_500"]["coords"]
    blue_ref_station = blue_alignment.reference_points["STA_500"]["station"]
    
    # Calculate the coordinates for station 26+00 using the improved function
    jimmy_durante_station = 2600  # 26+00
    jimmy_durante_portal_point = station_to_gis(
        reference_point=blue_ref_point,
        reference_station=blue_ref_station,
        target_station=jimmy_durante_station,
        track_params=blue_track_params,
        alignment=blue_alignment  # Pass the alignment object
    )
    
    print(f"Jimmy Durante Portal coordinates: {jimmy_durante_portal_point}")
    
    # Define custom icon for the Jimmy Durante Portal
    jimmy_durante_icon = folium.DivIcon(
        icon_size=(30, 30),
        icon_anchor=(15, 15),
        html="""
        <div style="
            background-color: blue;
            width: 24px;
            height: 24px;
            border-radius: 12px;
            border: 3px solid white;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 16px;
        ">T</div>
        """
    )
    
    # Add the marker to the map
    folium.Marker(
        location=jimmy_durante_portal_point,
        tooltip="Jimmy Durante Blvd Portal",
        popup="<b>Jimmy Durante Blvd Portal</b>",
        icon=jimmy_durante_icon
    ).add_to(m)
    
    # Find SC point of the third curve for Racetrack View Dr Portal marker
    racetrack_portal_point = None
    
    # Calculate the coordinates for station 82+00 on the yellow track
    yellow_ref_point = yellow_alignment.reference_points["STA_2000"]["coords"]
    yellow_ref_station = yellow_alignment.reference_points["STA_2000"]["station"]
    
    # Calculate the coordinates for station 82+00 using the station_to_gis function
    racetrack_station = 8200  # 82+00
    racetrack_portal_point = station_to_gis(
        reference_point=yellow_ref_point,
        reference_station=yellow_ref_station,
        target_station=racetrack_station,
        track_params=track_params,
        alignment=yellow_alignment  # Pass the alignment object
    )
    
    print(f"Racetrack View Dr Portal coordinates at 82+00: {racetrack_portal_point}")
    
    # Find which segment is the Third Curve for the bridge segment
    segment_index_limit = None
    for i, segment in enumerate(yellow_alignment.segments):
        if segment.type == "spiral_curve_spiral" and segment.name == "Third Curve":
            segment_index_limit = i
            break
    
    # Collect coordinates for "Yellow Track: Bridge" segment
    bridge_segment_coords = []
    
    # If we found the Third Curve, collect all coordinates up to its SC point
    if segment_index_limit is not None:
        # Add all coordinates from previous segments
        for i in range(segment_index_limit):
            bridge_segment_coords.extend(yellow_alignment.segment_coords[i])
        
        # Get the SC point directly from the third curve - this is the Racetrack View Portal location
        third_curve = yellow_alignment.segments[segment_index_limit]
        sc_point = third_curve.sc_point
        
        # Debug print to verify coordinates
        print(f"SC Point coordinates: {sc_point}")
        
        # For the third curve, we'll add ALL points from TS to a point BEYOND the SC point
        # and then trim it back to ensure we don't end short
        
        # Get the first half of the third curve with extra points
        third_curve_coords = yellow_alignment.segment_coords[segment_index_limit]
        
        # Take the first 40% of points to ensure we go beyond the SC point
        # (the entry spiral is typically about 30% of the total curve)
        points_to_include = int(len(third_curve_coords) * 0.4)
        bridge_segment_coords.extend(third_curve_coords[:points_to_include])
        
        # Now determine which point in our collected coordinates is closest to the SC point
        closest_idx = -1
        min_distance = float('inf')
        
        # Start from the halfway point of our bridge segment to speed up the search
        start_idx = len(bridge_segment_coords) // 2
        for i in range(start_idx, len(bridge_segment_coords)):
            point = bridge_segment_coords[i]
            dx = point[0] - sc_point[0]
            dy = point[1] - sc_point[1]
            distance = dx*dx + dy*dy
            
            if distance < min_distance:
                min_distance = distance
                closest_idx = i
        
        # Trim the bridge coordinates to end at the closest point to SC
        if closest_idx > 0:
            bridge_segment_coords = bridge_segment_coords[:closest_idx+1]
        
        # Always make sure the exact SC point is the last point
        if not (bridge_segment_coords[-1][0] == sc_point[0] and bridge_segment_coords[-1][1] == sc_point[1]):
            bridge_segment_coords.append(sc_point)
            
        # Debug print to verify the endpoint
        print(f"Bridge segment endpoint: {bridge_segment_coords[-1]}")
        print(f"Bridge segment length: {len(bridge_segment_coords)} points")
    
    # Create a "Yellow Track: Bridge" overlay for the entire segment
    
    if bridge_segment_coords:
        # Add a solid, thick line first to completely cover the original
        yellow_bridge_line = folium.PolyLine(
            locations=bridge_segment_coords,
            color='#FFD700',
            weight=9,  # Extra thick to ensure complete coverage
            opacity=1.0,
            tooltip="Yellow Track: Bridge",
            className="yellow-bridge-overlay"  # Special class to allow hover
        ).add_to(m)
        
        # Add animated path on top with the same special class
        AntPath(
            locations=bridge_segment_coords,
            dash_array=[10, 20],
            delay=800,
            color='#FFD700',
            pulseColor='#FFFFFF',
            paused=False,
            weight=5,  # Slightly thicker to ensure it's on top
            opacity=0.95,
            tooltip="Yellow Track: Bridge",
            className="yellow-bridge-overlay"  # Special class to allow hover
        ).add_to(m)
    
    # Add animated paths for the rest of the alignment (after the bridge section)
    if segment_index_limit is not None:
        # Add the rest of the third curve (after SC point)
        third_curve = yellow_alignment.segments[segment_index_limit]
        third_curve_coords = yellow_alignment.segment_coords[segment_index_limit]
        
        entry_spiral_length = third_curve.entry_spiral_length
        circular_arc_length = third_curve.circular_arc_length
        exit_spiral_length = third_curve.exit_spiral_length
        total_curve_length = entry_spiral_length + circular_arc_length + exit_spiral_length
        
        # Calculate approximately how many points to include for each portion
        if len(third_curve_coords) > 0:
            points_per_unit = len(third_curve_coords) / total_curve_length
            entry_spiral_points = int(entry_spiral_length * points_per_unit)
            circular_arc_points = int(circular_arc_length * points_per_unit)
            
            # Extract the circular curve coordinates (for Cut and Cover tunnel)
            circular_curve_start = entry_spiral_points
            circular_curve_end = entry_spiral_points + circular_arc_points
            circular_curve_coords = third_curve_coords[circular_curve_start:circular_curve_end]
            
            # Extract the exit spiral coordinates
            exit_spiral_coords = third_curve_coords[circular_curve_end:]
            
            # Add the remaining portion of the entry spiral (after the portal)
            entry_spiral_after_portal = third_curve_coords[entry_spiral_points//2:entry_spiral_points]
            if entry_spiral_after_portal:
                AntPath(
                    locations=entry_spiral_after_portal,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip=f"{third_curve.name} - Entry Spiral"
                ).add_to(m)
            
            # Add the circular curve with Cut and Cover tunnel label but same appearance
            if circular_curve_coords:
                yellow_cut_and_cover_line_1 = folium.PolyLine(
                    locations=circular_curve_coords,
                    color='#FFD700',
                    weight=9,  # Extra thick to ensure complete coverage
                    opacity=1.0,
                    tooltip="Yellow Track: Cut and Cover Tunnel",
                    className="yellow-cut-and-cover-overlay"  # Special class to allow hover
                ).add_to(m)
                
                AntPath(
                    locations=circular_curve_coords,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip="Yellow Track: Cut and Cover Tunnel",
                    className="yellow-cut-and-cover-overlay"
                ).add_to(m)
            
            # Add the exit spiral
            if exit_spiral_coords:
                yellow_bored_tunnel_line = folium.PolyLine(
                    locations=exit_spiral_coords,
                    color='#FFD700',
                    weight=9,  # Extra thick to ensure complete coverage
                    opacity=1.0,
                    tooltip="Yellow Track: Bored Tunnel",
                ).add_to(m)

                AntPath(
                    locations=exit_spiral_coords,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip="Yellow Track: Bored Tunnel"
                ).add_to(m)
        
        
        # Combine all remaining segments after the cut and cover tunnel into one "Bored Tunnel" segment
        if segment_index_limit is not None:
            # Collect all coordinates from remaining segments
            bored_tunnel_coords = []
            
            # First add the exit spiral of the third curve if not already added
            if segment_index_limit < len(yellow_alignment.segments) and not exit_spiral_coords:
                third_curve = yellow_alignment.segments[segment_index_limit]
                third_curve_coords = yellow_alignment.segment_coords[segment_index_limit]
                
                # Calculate segment boundaries
                points_per_unit = len(third_curve_coords) / total_curve_length
                entry_spiral_points = int(entry_spiral_length * points_per_unit)
                circular_arc_points = int(circular_arc_length * points_per_unit)
                exit_spiral_start = entry_spiral_points + circular_arc_points
                
                # Add exit spiral points
                bored_tunnel_coords.extend(third_curve_coords[exit_spiral_start:])
        
            # Add a flag to track if we've already processed the 7th tangent
            processed_seventh_tangent = False
        
        # Then add all remaining segments
        for i in range(segment_index_limit + 1, len(yellow_alignment.segments)):
            segment = yellow_alignment.segments[i]
            segment_coords = yellow_alignment.segment_coords[i]
            
            # Special handling for the 7th tangent - split it into two halves
            if segment.type == "tangent" and segment.name == "Seventh Tangent":
                # Set the flag to indicate we've processed the 7th tangent
                processed_seventh_tangent = True
                
                # Find the next segment (7th curve)
                i5_knoll_portal_point = None
                for j, next_segment in enumerate(yellow_alignment.segments):
                    if next_segment.type == "spiral_curve_spiral" and next_segment.name == "Seventh Curve":
                        # Get the TS point of the 7th curve as the I-5 Knoll Portal location
                        i5_knoll_portal_point = next_segment.ts_point
                        break
                
                # Calculate the midpoint
                midpoint_index = len(segment_coords) // 2
                
                # First half of 7th tangent - add to bored tunnel
                first_half_coords = segment_coords[:midpoint_index]
                bored_tunnel_coords.extend(first_half_coords)
                
                # Second half of 7th tangent - add as separate "Cut and Cover Tunnel" segment
                # Only goes to the end of the tangent (beginning of 7th curve)
                second_half_coords = segment_coords[midpoint_index:]
                
                # Add the second half as a Cut and Cover Tunnel segment
                yellow_cut_and_cover_line_2 = folium.PolyLine(
                    locations=second_half_coords,
                    color='#FFD700',
                    weight=9,  # Extra thick to ensure complete coverage
                    opacity=1.0,
                    tooltip="Yellow Track: Cut and Cover Tunnel",
                    className="yellow-cut-and-cover-overlay"  # Special class to allow hover
                ).add_to(m)
                
                AntPath(
                    locations=second_half_coords,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip="Yellow Track: Cut and Cover Tunnel"
                ).add_to(m)
                
                # Add the I-5 Knoll Portal marker at the end of the cut and cover segment
                if i5_knoll_portal_point:
                    # Define custom icon for the I-5 Knoll Portal
                    knoll_portal_icon = folium.DivIcon(
                        icon_size=(30, 30),
                        icon_anchor=(15, 15),
                        html="""
                        <div style="
                            background-color: #B8860B;
                            width: 24px;
                            height: 24px;
                            border-radius: 12px;
                            border: 3px solid white;
                            box-shadow: 0 0 10px rgba(0,0,0,0.5);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                        ">T</div>
                        """
                    )
                    
                    folium.Marker(
                        location=i5_knoll_portal_point,
                        tooltip="I-5 Knoll Portal",
                        popup="<b>I-5 Knoll Portal</b>",
                        icon=knoll_portal_icon
                    ).add_to(m)
                
                # Since we've reached the 2nd cut and cover segment, stop adding segments to the bored tunnel
                # Add the bored tunnel segment now
                if bored_tunnel_coords:
                    yellow_bored_tunnel_line_2 = folium.PolyLine(
                        locations=bored_tunnel_coords,
                        color='#FFD700',
                        weight=9,  # Extra thick to ensure complete coverage
                        opacity=1.0,
                        tooltip="Yellow Track: Bored Tunnel",
                    ).add_to(m)
        
                    AntPath(
                        locations=bored_tunnel_coords,
                        dash_array=[10, 20],
                        delay=600,
                        color='#FFD700',
                        pulseColor='#FFFFFF',
                        paused=False,
                        weight=5,
                        opacity=0.9,
                        tooltip="Yellow Track: Bored Tunnel"
                    ).add_to(m)
                
                # Clear the bored tunnel coordinates as we don't want to add any more segments to it
                bored_tunnel_coords = []
            elif not processed_seventh_tangent:
                # For segments before the 7th tangent, add to bored tunnel
                bored_tunnel_coords.extend(segment_coords)
            elif segment.type == "spiral_curve_spiral" and segment.name == "Seventh Curve":
                # Handle the seventh curve separately (not part of cut and cover)
                
                # Split the curve into two halves
                midpoint_index = len(segment_coords) // 2
                first_half_coords = segment_coords[:midpoint_index]
                second_half_coords = segment_coords[midpoint_index:]
                
                # Add the first half as "U-Section"
                yellow_u_section_line = folium.PolyLine(
                    locations=first_half_coords,
                    color='#FFD700',
                    weight=9,  # Extra thick to ensure complete coverage
                    opacity=1.0,
                    tooltip="Yellow Track: U-Section",
                ).add_to(m)
                
                AntPath(
                    locations=first_half_coords,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip="Yellow Track: U-Section"
                ).add_to(m)
                
                # Add the second half as "Bored Tunnel"
                yellow_bored_tunnel_line_curve7 = folium.PolyLine(
                    locations=second_half_coords,
                    color='#FFD700',
                    weight=9,  # Extra thick to ensure complete coverage
                    opacity=1.0,
                    tooltip="Yellow Track",
                ).add_to(m)
                
                AntPath(
                    locations=second_half_coords,
                    dash_array=[10, 20],
                    delay=600,
                    color='#FFD700',
                    pulseColor='#FFFFFF',
                    paused=False,
                    weight=5,
                    opacity=0.9,
                    tooltip="Yellow Track"
                ).add_to(m)
            else:
                # For segments after the 7th curve, add them with the appropriate styling
                is_after_seventh_curve = False
                
                # Check if we're past the 7th curve
                for j, check_segment in enumerate(yellow_alignment.segments):
                    if check_segment.type == "spiral_curve_spiral" and check_segment.name == "Seventh Curve":
                        is_after_seventh_curve = i > j
                        break
                
                # All segments after the 7th curve should be plain "Yellow Track" segments
                if is_after_seventh_curve:
                    # For segments after the U-Section (second half of 7th curve), add as basic track
                    yellow_segment_line = folium.PolyLine(
                        locations=segment_coords,
                        color='#FFD700',
                        weight=9,  # Extra thick to ensure complete coverage
                        opacity=1.0,
                        tooltip="Yellow Track",
                    ).add_to(m)
                    
                    AntPath(
                        locations=segment_coords,
                        dash_array=[10, 20],
                        delay=600,
                        color='#FFD700',
                        pulseColor='#FFFFFF',
                        paused=False,
                        weight=5,
                        opacity=0.9,
                        tooltip="Yellow Track"
                    ).add_to(m)
                else:
                    # For segments between the 1st and 2nd cut and cover tunnels, maintain as cut and cover
                    yellow_segment_line = folium.PolyLine(
                        locations=segment_coords,
                        color='#FFD700',
                        weight=9,  # Extra thick to ensure complete coverage
                        opacity=1.0,
                        tooltip="Yellow Track: Cut and Cover Tunnel",
                    ).add_to(m)
                    
                    AntPath(
                        locations=segment_coords,
                        dash_array=[10, 20],
                        delay=600,
                        color='#FFD700',
                        pulseColor='#FFFFFF',
                        paused=False,
                        weight=5,
                        opacity=0.9,
                        tooltip="Yellow Track: Cut and Cover Tunnel"
                    ).add_to(m)
        
        # We've already rendered the bored tunnel segment earlier when we reached the 2nd cut and cover tunnel
        # So we don't need to render it again here
        #if bored_tunnel_coords:
        #    yellow_bored_tunnel_line_2 = folium.PolyLine(
        #        locations=bored_tunnel_coords,
        #        color='#FFD700',
        #        weight=9,  # Extra thick to ensure complete coverage
        #        opacity=1.0,
        #        tooltip="Yellow Track: Bored Tunnel",
        #    ).add_to(m)
        #
        #    AntPath(
        #        locations=bored_tunnel_coords,
        #        dash_array=[10, 20],
        #        delay=600,
        #        color='#FFD700',
        #        pulseColor='#FFFFFF',
        #        paused=False,
        #        weight=5,
        #        opacity=0.9,
        #        tooltip="Yellow Track: Bored Tunnel"
        #    ).add_to(m)
    
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

        # Create Point object for shapely operations
        pt = Point(location.longitude, location.latitude)

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
                color="magenta" if "Purple" in name else "green" if "Green" in name else "#FF7700",
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
        yellow_nearest = yellow_line.interpolate(yellow_line.project(pt))
        yellow_nearest_lat, yellow_nearest_lon = yellow_nearest.y, yellow_nearest.x
        yellow_dist_m = geodesic(addr_pt, (yellow_nearest_lat, yellow_nearest_lon)).meters
        
        # Convert to different units and round
        yellow_dist_ft = round(yellow_dist_m * 3.28084)  # Convert meters to feet
        yellow_dist_m_rounded = round(yellow_dist_m / 10) * 10  # Round to nearest 10 meters
        yellow_dist_km = round(yellow_dist_m / 1000, 1)  # Round to 0.1 km
        yellow_dist_miles = round(yellow_dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (yellow_nearest_lat, yellow_nearest_lon)],
            color="#FF7700",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Yellow track
        st.sidebar.write("**Yellow Route: Engineering Alignment:**")
        st.sidebar.write(f"- {yellow_dist_ft} ft")
        st.sidebar.write(f"- {yellow_dist_m_rounded} m")
        st.sidebar.write(f"- {yellow_dist_km} km")
        st.sidebar.write(f"- {yellow_dist_miles} mi")
        
        # Calculate distance to blue track
        blue_line = LineString([(lon, lat) for lat, lon in blue_alignment.all_coords])
        blue_nearest = blue_line.interpolate(blue_line.project(pt))
        blue_nearest_lat, blue_nearest_lon = blue_nearest.y, blue_nearest.x
        blue_dist_m = geodesic(addr_pt, (blue_nearest_lat, blue_nearest_lon)).meters
        
        # Convert to different units and round
        blue_dist_ft = round(blue_dist_m * 3.28084)  # Convert meters to feet
        blue_dist_m_rounded = round(blue_dist_m / 10) * 10  # Round to nearest 10 meters
        blue_dist_km = round(blue_dist_m / 1000, 1)  # Round to 0.1 km
        blue_dist_miles = round(blue_dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (blue_nearest_lat, blue_nearest_lon)],
            color="blue",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Blue track
        st.sidebar.write("**Blue Route: Under Crest Canyon:**")
        st.sidebar.write(f"- {blue_dist_ft} ft")
        st.sidebar.write(f"- {blue_dist_m_rounded} m")
        st.sidebar.write(f"- {blue_dist_km} km")
        st.sidebar.write(f"- {blue_dist_miles} mi")
        
        # Calculate distance to purple track
        purple_line = LineString([(lon, lat) for lat, lon in purple_alignment.all_coords])
        purple_nearest = purple_line.interpolate(purple_line.project(pt))
        purple_nearest_lat, purple_nearest_lon = purple_nearest.y, purple_nearest.x
        purple_dist_m = geodesic(addr_pt, (purple_nearest_lat, purple_nearest_lon)).meters
        
        # Convert to different units and round
        purple_dist_ft = round(purple_dist_m * 3.28084)  # Convert meters to feet
        purple_dist_m_rounded = round(purple_dist_m / 10) * 10  # Round to nearest 10 meters
        purple_dist_km = round(purple_dist_m / 1000, 1)  # Round to 0.1 km
        purple_dist_miles = round(purple_dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (purple_nearest_lat, purple_nearest_lon)],
            color="magenta",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Purple track
        st.sidebar.write("**Purple Route: Under Camino Del Mar:**")
        st.sidebar.write(f"- {purple_dist_ft} ft")
        st.sidebar.write(f"- {purple_dist_m_rounded} m")
        st.sidebar.write(f"- {purple_dist_km} km")
        st.sidebar.write(f"- {purple_dist_miles} mi")
        
        # Calculate distance to green track
        green_line = LineString([(lon, lat) for lat, lon in green_alignment.all_coords])
        green_nearest = green_line.interpolate(green_line.project(pt))
        green_nearest_lat, green_nearest_lon = green_nearest.y, green_nearest.x
        green_dist_m = geodesic(addr_pt, (green_nearest_lat, green_nearest_lon)).meters
        
        # Convert to different units and round
        green_dist_ft = round(green_dist_m * 3.28084)  # Convert meters to feet
        green_dist_m_rounded = round(green_dist_m / 10) * 10  # Round to nearest 10 meters
        green_dist_km = round(green_dist_m / 1000, 1)  # Round to 0.1 km
        green_dist_miles = round(green_dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (green_nearest_lat, green_nearest_lon)],
            color="green",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Green track
        st.sidebar.write("**Green Route: Del Mar Bluffs Double-Track:**")
        st.sidebar.write(f"- {green_dist_ft} ft")
        st.sidebar.write(f"- {green_dist_m_rounded} m")
        st.sidebar.write(f"- {green_dist_km} km")
        st.sidebar.write(f"- {green_dist_miles} mi")
        
        # Calculate distance to Northern Yellow track
        northern_yellow_line = LineString([(lon, lat) for lat, lon in northern_yellow_alignment.all_coords])
        northern_yellow_nearest = northern_yellow_line.interpolate(northern_yellow_line.project(pt))
        northern_yellow_nearest_lat, northern_yellow_nearest_lon = northern_yellow_nearest.y, northern_yellow_nearest.x
        northern_yellow_dist_m = geodesic(addr_pt, (northern_yellow_nearest_lat, northern_yellow_nearest_lon)).meters
        
        # Convert to different units and round
        northern_yellow_dist_ft = round(northern_yellow_dist_m * 3.28084)  # Convert meters to feet
        northern_yellow_dist_m_rounded = round(northern_yellow_dist_m / 10) * 10  # Round to nearest 10 meters
        northern_yellow_dist_km = round(northern_yellow_dist_m / 1000, 1)  # Round to 0.1 km
        northern_yellow_dist_miles = round(northern_yellow_dist_m * 0.000621371, 1)  # Round to 0.1 miles
        
        # Draw a connector
        folium.PolyLine(
            [addr_pt, (northern_yellow_nearest_lat, northern_yellow_nearest_lon)],
            color="orange",
            weight=2,
            dash_array="5,5"
        ).add_to(m)
        
        # Display the distance to Northern Yellow track
        st.sidebar.write("**Northern Yellow Route:**")
        st.sidebar.write(f"- {northern_yellow_dist_ft} ft")
        st.sidebar.write(f"- {northern_yellow_dist_m_rounded} m")
        st.sidebar.write(f"- {northern_yellow_dist_km} km")
        st.sidebar.write(f"- {northern_yellow_dist_miles} mi")
        
        # Find which segment of the northern yellow track is closest
        northern_yellow_min_distance = float('inf')
        northern_yellow_closest_segment = None
        northern_yellow_segment_index = None
        
        for i, segment in enumerate(northern_yellow_alignment.segments):
            segment_linestring = LineString([(lon, lat) for lat, lon in northern_yellow_alignment.segment_coords[i]])
            segment_nearest = segment_linestring.interpolate(segment_linestring.project(pt))
            segment_dist = geodesic(addr_pt, (segment_nearest.y, segment_nearest.x)).meters
            
            if segment_dist < northern_yellow_min_distance:
                northern_yellow_min_distance = segment_dist
                northern_yellow_closest_segment = segment
                northern_yellow_segment_index = i
        
        if northern_yellow_closest_segment:
            # Bold header for closest segment
            st.sidebar.markdown(f"**Closest Northern Yellow segment: {northern_yellow_closest_segment.name}**")
            
            # Determine approximate station of the closest point
            if northern_yellow_closest_segment.type == "tangent":
                # Calculate percentage along the segment
                segment_linestring = LineString([(lon, lat) for lat, lon in northern_yellow_alignment.segment_coords[northern_yellow_segment_index]])
                percentage = segment_linestring.project(pt) / segment_linestring.length
                
                # Interpolate station value
                station_value = northern_yellow_closest_segment.start_station_value + percentage * (northern_yellow_closest_segment.end_station_value - northern_yellow_closest_segment.start_station_value)
                
                # Format station
                station_formatted = format_station(station_value)
                
                st.sidebar.write(f"Approximate Station: {station_formatted}")
                
            elif northern_yellow_closest_segment.type == "spiral_curve_spiral":
                # For curves, show the type of element (entry spiral, circular curve, exit spiral)
                # Determine which part of the curve is closest
                
                # Calculate total curve length
                total_length = northern_yellow_closest_segment.entry_spiral_length + northern_yellow_closest_segment.circular_arc_length + northern_yellow_closest_segment.exit_spiral_length
                
                # Get normalized distance along the curve
                segment_linestring = LineString([(lon, lat) for lat, lon in northern_yellow_alignment.segment_coords[northern_yellow_segment_index]])
                curve_distance = segment_linestring.project(pt) / segment_linestring.length * total_length
                
                if curve_distance < northern_yellow_closest_segment.entry_spiral_length:
                    # In entry spiral
                    percentage = curve_distance / northern_yellow_closest_segment.entry_spiral_length
                    station_value = northern_yellow_closest_segment.ts_station_value + percentage * (northern_yellow_closest_segment.sc_station_value - northern_yellow_closest_segment.ts_station_value)
                    element_type = "Entry Spiral"
                elif curve_distance < northern_yellow_closest_segment.entry_spiral_length + northern_yellow_closest_segment.circular_arc_length:
                    # In circular curve
                    distance_in_curve = curve_distance - northern_yellow_closest_segment.entry_spiral_length
                    percentage = distance_in_curve / northern_yellow_closest_segment.circular_arc_length
                    station_value = northern_yellow_closest_segment.sc_station_value + percentage * (northern_yellow_closest_segment.cs_station_value - northern_yellow_closest_segment.sc_station_value)
                    element_type = "Circular Curve"
                else:
                    # In exit spiral
                    distance_in_spiral = curve_distance - northern_yellow_closest_segment.entry_spiral_length - northern_yellow_closest_segment.circular_arc_length
                    percentage = distance_in_spiral / northern_yellow_closest_segment.exit_spiral_length
                    station_value = northern_yellow_closest_segment.cs_station_value + percentage * (northern_yellow_closest_segment.st_station_value - northern_yellow_closest_segment.cs_station_value)
                    element_type = "Exit Spiral"
                
                # Format station
                station_formatted = format_station(station_value)
                
                st.sidebar.write(f"Element: {element_type}")
                st.sidebar.write(f"Approximate Station: {station_formatted}")
                
                # Add information about the curve
                if element_type == "Circular Curve":
                    radius_ft = northern_yellow_closest_segment.radius_ft
                    degree_curve = northern_yellow_closest_segment.degree_value
                    st.sidebar.write(f"Radius: {int(radius_ft)} ft")
                    st.sidebar.write(f"Degree of Curve: {degree_curve:.2f}°")

    # Add the Racetrack View Dr Portal marker
    if racetrack_portal_point:
        # Define custom icon with shadow, larger size, and more prominent appearance
        tunnel_icon = folium.DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html="""
            <div style="
                background-color: red;
                width: 24px;
                height: 24px;
                border-radius: 12px;
                border: 3px solid white;
                box-shadow: 0 0 10px rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 16px;
            ">T</div>
            """
        )
        
        folium.Marker(
            location=racetrack_portal_point,
            tooltip="Racetrack View Dr Portal",
            popup="<b>Racetrack View Dr Portal</b><br>Yellow Track Station 82+00",
            icon=tunnel_icon
        ).add_to(m)

    # --- 4. render ---
    # Set the map height to fill available space while leaving room for header and footer
    st_folium(m, width="100%")

# --- 5. Footer with credits and disclaimer ---
# Create footer using native Streamlit elements
st.markdown("<div class='custom-footer'>", unsafe_allow_html=True)
footer_cols = st.columns([3, 1])
with footer_cols[0]:
    st.markdown("""
    Disclaimer:
    The four proposed routes and their associated distance calculations presented in this interactive map are based on the most recent publicly available documentation from SANDAG: San Diego LOSSAN Rail Realignment Project Post Value Analysis Study Assessment – Appendix A: Exhibits of the Staff-Recommended Alignments (published May 16, 2025). This tool is for informational and educational purposes only and is not an official source of project data. Users should refer directly to SANDAG for authoritative and up-to-date project information. 
    """)
with footer_cols[1]:
    st.markdown("""
    **Created by:** Nathan Qiu  
    **Contact:** [nathanqiu07@gmail.com](mailto:nathanqiu07@gmail.com)
    """)
st.markdown("</div>", unsafe_allow_html=True)

