import folium
import numpy as np
from utils.engineering_coords import station_to_gis, format_station

class Portal:
    """Class representing a tunnel portal on a railway alignment"""
    
    def __init__(self, name, track_alignment, station_value, color=None, description=None):
        """
        Initialize a portal
        
        Args:
            name: Name of the portal
            track_alignment: RailwayAlignment object the portal belongs to
            station_value: Station value (e.g., 13000 for 130+00)
            color: Color for the portal marker (defaults to track color if None)
            description: Additional description for the portal popup
        """
        self.name = name
        self.track_alignment = track_alignment
        self.station_value = station_value
        self.color = color if color else track_alignment.color
        self.description = description if description else f"Portal at station {format_station(station_value)}"
        self.coordinates = None
        
    def calculate_coordinates(self):
        """Calculate the portal coordinates using the track alignment"""
        # Get reference point and station from the track alignment
        ref_point_name = list(self.track_alignment.reference_points.keys())[0]
        ref_point = self.track_alignment.reference_points[ref_point_name]["coords"]
        ref_station = self.track_alignment.reference_points[ref_point_name]["station"]
        
        # Calculate track parameters if needed
        if len(self.track_alignment.reference_points) >= 2:
            ref_point2_name = list(self.track_alignment.reference_points.keys())[1]
            track_params = self.track_alignment.calculate_track_params(ref_point_name, ref_point2_name)
        else:
            # If only one reference point, use the alignment's calculated parameters
            # This assumes the alignment has already been processed
            track_params = {
                'bearing_rad': 0,
                'bearing_deg': 0,
                'scale': 0.00001,
                'direction': np.array([0, 1])
            }
        
        # Calculate coordinates using station_to_gis
        self.coordinates = station_to_gis(
            reference_point=ref_point,
            reference_station=ref_station,
            target_station=self.station_value,
            track_params=track_params,
            alignment=self.track_alignment
        )
        
        return self.coordinates
    
    def add_to_map(self, m):
        """Add the portal marker to the map"""
        if not self.coordinates:
            self.calculate_coordinates()
        
        # Define custom icon for the portal
        portal_icon = folium.DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html=f"""
            <div style="
                background-color: {self.color};
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
            location=self.coordinates,
            tooltip=self.name,
            popup=f"<b>{self.name}</b><br>{self.description}",
            icon=portal_icon
        ).add_to(m) 