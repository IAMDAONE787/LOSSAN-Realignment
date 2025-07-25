import numpy as np

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