# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

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
        "San Dieguito → I-5": {
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
        "Under Crest Canyon": {
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
        "Under Camino Del Mar": {
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
        "Del Mar Bluffs Double-Track": {
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
    # add all four alignments
    for name, data in ALIGNMENTS.items():
        folium.PolyLine(
            data["coords"],
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
            line = LineString([(lon, lat) for lat, lon in data["coords"]])
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
    **Disclaimer:** The displayed tracks and distance calculations are close estimates based on the routes displayed on the LOSSAN website.
    """)
with footer_cols[1]:
    st.markdown("""
    **Created by:** Nathan Qiu  
    **Contact:** [nathanqiu07@gmail.com](mailto:nathanqiu07@gmail.com)
    """)
st.markdown("</div>", unsafe_allow_html=True)
