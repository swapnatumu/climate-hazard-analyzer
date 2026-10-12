"""Preset demo regions for Andhra Pradesh and Telangana.

Cities are points (snapped to the nearest ERA5 cell). Areas are approximate rectangles
(not official boundaries), each within the 2°×2° bbox limit.
Coordinates are approximate city-centre values.
"""

CITIES = [
    # Telangana
    {"id": "hyderabad", "name": "Hyderabad", "state": "Telangana", "lat": 17.385, "lon": 78.487},
    {"id": "warangal", "name": "Warangal", "state": "Telangana", "lat": 17.969, "lon": 79.594},
    {"id": "karimnagar", "name": "Karimnagar", "state": "Telangana", "lat": 18.439, "lon": 79.129},
    {"id": "nizamabad", "name": "Nizamabad", "state": "Telangana", "lat": 18.673, "lon": 78.094},
    {"id": "khammam", "name": "Khammam", "state": "Telangana", "lat": 17.247, "lon": 80.151},
    # Andhra Pradesh
    {"id": "visakhapatnam", "name": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.687, "lon": 83.219},
    {"id": "vijayawada", "name": "Vijayawada", "state": "Andhra Pradesh", "lat": 16.506, "lon": 80.648},
    {"id": "guntur", "name": "Guntur", "state": "Andhra Pradesh", "lat": 16.307, "lon": 80.437},
    {"id": "tirupati", "name": "Tirupati", "state": "Andhra Pradesh", "lat": 13.629, "lon": 79.419},
    {"id": "nellore", "name": "Nellore", "state": "Andhra Pradesh", "lat": 14.443, "lon": 79.987},
    {"id": "kurnool", "name": "Kurnool", "state": "Andhra Pradesh", "lat": 15.828, "lon": 78.037},
    {"id": "kakinada", "name": "Kakinada", "state": "Andhra Pradesh", "lat": 16.989, "lon": 82.248},
    {"id": "anantapur", "name": "Anantapur", "state": "Andhra Pradesh", "lat": 14.682, "lon": 77.601},
]

# bbox = [minLon, minLat, maxLon, maxLat]
AREAS = [
    {"id": "hyderabad-metro", "name": "Hyderabad metro region", "state": "Telangana",
     "bbox": [78.2, 17.2, 78.8, 17.7]},
    {"id": "north-telangana", "name": "North Telangana (Nizamabad–Karimnagar)", "state": "Telangana",
     "bbox": [77.9, 18.2, 79.5, 19.4]},
    {"id": "south-east-telangana", "name": "South-east Telangana (Nalgonda–Khammam)", "state": "Telangana",
     "bbox": [79.0, 16.6, 80.6, 17.6]},
    {"id": "north-coastal-ap", "name": "North Coastal AP (Visakhapatnam–Srikakulam)", "state": "Andhra Pradesh",
     "bbox": [82.8, 17.5, 84.2, 18.7]},
    {"id": "godavari-delta", "name": "Godavari delta", "state": "Andhra Pradesh",
     "bbox": [81.5, 16.3, 82.4, 17.2]},
    {"id": "krishna-delta", "name": "Krishna delta (Vijayawada–Guntur)", "state": "Andhra Pradesh",
     "bbox": [80.2, 15.8, 81.3, 16.7]},
    {"id": "rayalaseema", "name": "Rayalaseema (Kurnool–Anantapur)", "state": "Andhra Pradesh",
     "bbox": [77.2, 14.3, 78.6, 16.0]},
    {"id": "south-coastal-ap", "name": "South AP (Tirupati–Nellore)", "state": "Andhra Pradesh",
     "bbox": [79.2, 13.4, 80.3, 14.8]},
]
