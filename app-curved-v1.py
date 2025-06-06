# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import numpy as np

try:
    from shapely.geometry import LineString, Point
except ImportError:
    st.error("Failed to import Shapely. Please check your installation.")
    LineString = None
    Point = None

# Set page config first
st.set_page_config(layout="wide")

# Function to create curved segments between points
def create_curved_path(coords, curve_factor=0.2, steps=20):
    """
    Convert a sequence of points into a curved path using quadratic bezier curves.
    
    Args:
        coords: List of coordinate tuples (lat, lon)
        curve_factor: How curved the path should be (0-1)
        steps: Number of points to generate along each curve
        
    Returns:
        List of interpolated coordinates for a curved path
    """
    if len(coords) < 3:
        return coords  # Not enough points to curve
    
    curved_coords = [coords[0]]  # Start with the first point
    
    for i in range(len(coords) - 2):
        p0 = np.array(coords[i])
        p1 = np.array(coords[i + 1])
        p2 = np.array(coords[i + 2])
        
        # Create a control point by moving perpendicular to the line
        v1 = p1 - p0
        v2 = p2 - p1
        
        # Midpoint of the two segments
        mid1 = (p0 + p1) / 2
        mid2 = (p1 + p2) / 2
        
        # Perpendicular vector to create curve
        perp1 = np.array([-v1[1], v1[0]])
        perp2 = np.array([-v2[1], v2[0]])
        
        # Normalize and scale by curve factor
        if np.linalg.norm(perp1) > 0:
            perp1 = perp1 / np.linalg.norm(perp1) * curve_factor * np.linalg.norm(v1)
        if np.linalg.norm(perp2) > 0:
            perp2 = perp2 / np.linalg.norm(perp2) * curve_factor * np.linalg.norm(v2)
        
        # Control point is the waypoint with some perpendicular offset
        control = p1 + (perp1 + perp2) / 2
        
        # Generate points along the quadratic Bezier curve
        for t in np.linspace(0, 1, steps):
            # Quadratic Bezier formula: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
            intermediate = (1-t)**2 * mid1 + 2*(1-t)*t * control + t**2 * mid2
            curved_coords.append((intermediate[0], intermediate[1]))
    
    # Add the last point
    curved_coords.append(coords[-1])
    
    return curved_coords

# Function to generate a circular curve path
def create_circular_curve(start_point, radius, degree_of_curve, central_angle, direction='right', steps=40):
    """
    Generate points along a circular curve using railway engineering parameters.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the curve
        radius: Radius of the curve in feet
        degree_of_curve: The degree of curvature (Dc) in decimal degrees
        central_angle: The central angle subtended by the curve in decimal degrees
        direction: 'right' or 'left' to indicate turning direction
        steps: Number of points to generate along the curve
    
    Returns:
        List of coordinate tuples (lat, lon) forming the circular curve
    """
    # Convert to radians
    central_angle_rad = np.radians(central_angle)
    
    # Determine the sign for the angle based on direction
    sign = -1 if direction == 'right' else 1
    
    # Calculate the arc length
    arc_length = radius * central_angle_rad
    
    # Generate points along the curve
    points = []
    for i in range(steps + 1):
        # Angle from the center to the current point
        angle = sign * (i / steps) * central_angle_rad
        
        # Calculate offset from the start point
        dx = radius * np.sin(angle)
        dy = radius * (1 - np.cos(angle))
        
        # Apply the offset to the start point (simplified - assuming flat earth near the start point)
        # This is a rough approximation for small distances
        lat_offset = dy * 0.00000899  # ~0.00000899 degrees per meter at Earth's surface
        lon_offset = dx * 0.00001176 / np.cos(np.radians(start_point[0]))  # Adjust for latitude
        
        lat = start_point[0] + lat_offset
        lon = start_point[1] + lon_offset
        
        points.append((lat, lon))
    
    return points

# Function to generate a spiral curve path (clothoid)
def create_spiral_curve(start_point, spiral_length, degree_of_curve, direction='right', azimuth_deg=90, steps=40):
    """
    Generate points along a spiral curve (clothoid) using railway engineering parameters.
    
    Args:
        start_point: Tuple (lat, lon) for the start of the spiral (TS point)
        spiral_length: Length of the spiral (Ls) in feet
        degree_of_curve: The final degree of curvature (Dc) in decimal degrees
        direction: 'right' or 'left' to indicate turning direction
        azimuth_deg: Bearing of the tangent at the start point in degrees (0=North, 90=East)
        steps: Number of points to generate along the spiral
    
    Returns:
        List of coordinate tuples (lat, lon) forming the spiral curve
    """
    # Convert degree of curvature to radius (using arc definition standard in US railway)
    radius = 5729.58 / degree_of_curve  # feet
    
    # Calculate the spiral parameter A
    A = np.sqrt(radius * spiral_length)
    
    # Determine sign for direction
    sign = -1 if direction == 'right' else 1
    
    # Generate local coordinates along the spiral
    points = []
    for i in range(steps + 1):
        # Distance along the spiral
        s = (i / steps) * spiral_length
        
        # Clothoid equations (Euler spiral)
        x = s - (s**5) / (40 * A**4) + (s**9) / (3456 * A**8)
        y = sign * ((s**3) / (6 * A**2) - (s**7) / (336 * A**6))
        
        # Rotate according to azimuth
        theta = np.radians(azimuth_deg)
        x_rot = x * np.cos(theta) - y * np.sin(theta)
        y_rot = x * np.sin(theta) + y * np.cos(theta)
        
        # Convert to lat/lon offsets (simplified approximation)
        lat_offset = y_rot * 0.00000899  # ~0.00000899 degrees per meter at Earth's surface
        lon_offset = x_rot * 0.00001176 / np.cos(np.radians(start_point[0]))  # Adjust for latitude
        
        lat = start_point[0] + lat_offset
        lon = start_point[1] + lon_offset
        
        points.append((lat, lon))
    
    return points

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
        "Yellow Route: San Dieguito → I-5": {
            "coords": [
                (32.9720408, -117.2664554),
                (32.9697782, -117.2616609),
                (32.9627864, -117.2548587),
                (32.9564772, -117.2458251),
                (32.9497203, -117.2442618),
                (32.9409542, -117.2428688),
                (32.9314144, -117.2430945),
                (32.9251512+0.00005, -117.2425307+0.00005),
                (32.9162438+0.00005, -117.2371537+0.00005),
            ],
            "color": "orange",
        },
        "Blue Route: Under Crest Canyon": {
            "coords": [
                (32.9720408, -117.2664554),
                (32.9676162, -117.2653677),
                (32.9636421, -117.2633048),#
                (32.9558076, -117.2566718),#
                (32.9491315, -117.2547255),#
                (32.9383269, -117.2473140),#
                (32.9306534, -117.2445875),#
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
                (32.9608866, -117.2681671),#
                (32.9556471, -117.2670344),#
                (32.9457051, -117.2631553),#
                (32.9387049, -117.2612257),#
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

    # add all four alignments with proper railway curves
    for name, data in ALIGNMENTS.items():
        # Get original coordinates
        orig_coords = data["coords"]
        
        # Create a single smooth path with no duplicates
        curved_coords = [orig_coords[0]]  # Start with the first point
        
        # Process each segment in sequence
        for i in range(len(orig_coords) - 1):
            start_point = orig_coords[i]
            end_point = orig_coords[i+1]
            
            # Calculate distance for this segment
            dist = geodesic(start_point, end_point).meters
            
            # Skip adding intermediate points for very short segments
            if dist < 100:
                continue
            
            # For longer segments, add smooth intermediate points
            num_points = max(5, min(20, int(dist / 100)))  # Scale points with distance
            
            for j in range(1, num_points):
                t = j / num_points
                
                # Simple linear interpolation for straighter segments
                if i == 0 or i == len(orig_coords) - 2:
                    # First and last segments are straighter
                    interp_lat = start_point[0] + t * (end_point[0] - start_point[0])
                    interp_lon = start_point[1] + t * (end_point[1] - start_point[1])
                else:
                    # Middle segments get a slight curve using quadratic interpolation
                    # Find previous and next points for context
                    prev_point = orig_coords[max(0, i-1)]
                    next_point = orig_coords[min(len(orig_coords)-1, i+2)]
                    
                    # Control point - slight offset perpendicular to the segment
                    dx = end_point[0] - start_point[0]
                    dy = end_point[1] - start_point[1]
                    
                    # Perpendicular vector (normalized and scaled)
                    length = np.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        perpx = -dy / length * 0.0001  # Scale factor adjusted for GPS coordinates
                        perpy = dx / length * 0.0001
                    else:
                        perpx, perpy = 0, 0
                    
                    # Midpoint with offset
                    midx = start_point[0] + t * dx + perpx
                    midy = start_point[1] + t * dy + perpy
                    
                    # Adjust curve based on segment's position in the overall path
                    curve_factor = 0.7  # Controls how much the path curves
                    interp_lat = (1-curve_factor) * (start_point[0] + t * dx) + curve_factor * midx
                    interp_lon = (1-curve_factor) * (start_point[1] + t * dy) + curve_factor * midy
                
                curved_coords.append((interp_lat, interp_lon))
        
        # Add the final point
        if curved_coords[-1] != orig_coords[-1]:
            curved_coords.append(orig_coords[-1])
        
        # Store the expanded coordinates for distance calculations
        expanded_alignments[name] = curved_coords
        
        # Add to map
        folium.PolyLine(
            curved_coords,
            color=data["color"],
            weight=4,
            tooltip=name
        ).add_to(m)

    # if we have a valid location, plot it + compute distances
    if location:
        addr_pt = (location.latitude, location.longitude)
        folium.Marker(addr_pt, tooltip=address, icon=folium.Icon(color="red")).add_to(m)

        st.sidebar.markdown("## Distances to Each Alignment")
        for name, data in ALIGNMENTS.items():
            # Use expanded coordinates for more accurate distance calculation
            curved_coords = expanded_alignments[name]
            
            # Create a LineString from the curved coordinates
            line = LineString([(lon, lat) for lat, lon in curved_coords])
            pt = Point(location.longitude, location.latitude)

            # find nearest point on the line
            nearest = line.interpolate(line.project(pt))
            nearest_lat, nearest_lon = nearest.y, nearest.x

            # geodesic distance in meters
            dist_m = geodesic(addr_pt, (nearest_lat, nearest_lon)).meters
            
            # Convert to different units and round
            dist_m_rounded = round(dist_m / 10) * 10  # Round to nearest 10 meters
            dist_km = round(dist_m / 1000, 1)  # Round to 0.1 km
            dist_miles = round(dist_m * 0.000621371, 1)  # Round to 0.1 miles

            # draw a connector
            folium.PolyLine(
                [addr_pt, (nearest_lat, nearest_lon)],
                color=data["color"],
                weight=2,
                dash_array="5,5"
            ).add_to(m)

            st.sidebar.write(f"**{name}:**")
            st.sidebar.write(f"- {dist_m_rounded} m")
            st.sidebar.write(f"- {dist_km} km")
            st.sidebar.write(f"- {dist_miles} mi")

    # --- 4. render ---
    # Set the map height to fill available space while leaving room for header and footer
    st_folium(m, width="100%")

# --- 5. Footer with credits and disclaimer ---
# Remove the spacer as we're using fixed positioning
# st.markdown("<div style='flex-grow: 1;'></div>", unsafe_allow_html=True)

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
