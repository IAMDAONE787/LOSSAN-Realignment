import streamlit as st
import folium
from streamlit_folium import st_folium
from utils.railway_alignment import RailwayAlignment
from utils.engineering_coords import parse_station

def main():
    """
    Demo application showing how to use track type sections in RailwayAlignment
    """
    st.title("Track Type Sections Demo")
    
    # Create a map centered on Del Mar
    m = folium.Map(location=(32.975, -117.245), zoom_start=13, tiles="OpenStreetMap")
    
    # Create a sample railway alignment
    yellow_alignment = RailwayAlignment(name="Yellow Route: Engineering Alignment", color="#FFD700")
    
    # Add reference points
    station_2000_coords = (32.9740081, -117.2669915)  # 20+00 station
    station_2500_coords = (32.9726647, -117.2666647)  # 25+00 station
    
    yellow_alignment.add_reference_point("STA_2000", station_2000_coords, 2000)
    yellow_alignment.add_reference_point("STA_2500", station_2500_coords, 2500)
    
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
        sc_station="39+05.96",
        cs_station="40+60.67", 
        st_station="42+20.67",
        degree_of_curve="9 30'00\"",
        direction="left",
        name="Second Curve"
    )
    
    # Third tangent segment
    yellow_alignment.add_tangent("42+20.67", "75+17.38", name="Extended Tangent")
    
    # Third spiral-curve-spiral segment
    yellow_alignment.add_curve(
        ts_station="75+17.38", 
        sc_station="79+17.38",
        cs_station="87+52.17", 
        st_station="91+52.17",
        degree_of_curve="2 24'00\"",
        direction="right",
        name="Third Curve"
    )
    
    # Calculate track parameters
    track_params = yellow_alignment.calculate_track_params("STA_2000", "STA_2500")
    
    # Add the alignment to the map
    yellow_alignment.add_to_map(
        m=m, 
        start_ref_point_name="STA_2000", 
        track_params=track_params,
        add_markers=True  # Show reference points
    )
    
    # Now define track type sections
    # 1. Bridge section from start to third curve
    yellow_alignment.add_track_type_section(
        track_type="Bridge",
        start_station="20+00",
        end_station="79+17.38",  # SC point of third curve
        color="#FFD700",
        tooltip="Yellow Track: Bridge Section"
    )
    
    # 2. Cut and Cover Tunnel for the circular part of the third curve
    yellow_alignment.add_track_type_section(
        track_type="Cut and Cover Tunnel",
        start_station="79+17.38",  # SC point of third curve
        end_station="87+52.17",  # CS point of third curve
        color="#FFD700",
        tooltip="Yellow Track: Cut and Cover Tunnel"
    )
    
    # 3. Bored Tunnel for the exit spiral of the third curve
    yellow_alignment.add_track_type_section(
        track_type="Bored Tunnel",
        start_station="87+52.17",  # CS point of third curve
        end_station="91+52.17",  # ST point of third curve
        color="#FFD700",
        tooltip="Yellow Track: Bored Tunnel"
    )
    
    # Render the map
    st_folium(m, width="100%", height=600)
    
    # Display information about the track type sections
    st.subheader("Track Type Sections")
    
    for track_type, sections in yellow_alignment.track_types.items():
        if sections:
            st.write(f"**{track_type}:** {len(sections)} section(s)")
            
            for i, section in enumerate(sections):
                st.write(f"  - Section {i+1}: {section.start_station} to {section.end_station}")

if __name__ == "__main__":
    main() 