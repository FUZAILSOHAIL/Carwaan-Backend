#!/usr/bin/env python3
"""
Test script for route calculation service
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.rides.route_service import calculate_route_distance
import json

def test_route_calculation():
    """Test route calculation with Karachi coordinates"""
    
    # Test with valid Karachi coordinates that have OpenRouteService coverage
    # Using coordinates from the working example: start=67.0364,24.9352&end=67.1140,24.9313
    start_lat = 24.9352  # Latitude
    start_lng = 67.0364  # Longitude 
    end_lat = 24.9313    # Latitude
    end_lng = 67.1140    # Longitude
    
    print('🚗 Testing route calculation between Karachi coordinates...')
    print(f'📍 Start: {start_lat}, {start_lng} (lat, lng)')
    print(f'📍 End: {end_lat}, {end_lng} (lat, lng)')
    print(f'📍 OpenRouteService format: start={start_lng},{start_lat} end={end_lng},{end_lat}')
    print()
    
    try:
        # Test fastest route
        print('Testing FASTEST route preference...')
        result = calculate_route_distance(start_lat, start_lng, end_lat, end_lng, 'fastest')
        print('✅ Route calculation successful!')
        print(f"📊 Provider: {result.get('provider', 'unknown')}")
        print(f"📏 Distance: {result.get('distance_km', 0)} km")
        print(f"⏱️ Duration: {result.get('duration_minutes', 0)} minutes")
        polyline = result.get('polyline', '')
        print(f"🛣️ Polyline length: {len(str(polyline))}")
        
        # Test polyline format
        if polyline:
            try:
                import json
                if polyline.startswith('['):
                    coords = json.loads(polyline)
                    print(f"📍 Polyline format: JSON array with {len(coords)} points")
                    if len(coords) > 0:
                        print(f"📍 First point: {coords[0]} (should be [lat, lng])")
                        print(f"📍 Last point: {coords[-1]} (should be [lat, lng])")
                else:
                    print(f"📍 Polyline format: Encoded string")
            except Exception as e:
                print(f"⚠️ Could not parse polyline: {e}")
        print()
        
        # Test shortest route
        print('Testing SHORTEST route preference...')
        result2 = calculate_route_distance(start_lat, start_lng, end_lat, end_lng, 'shortest')
        print(f"📊 Provider: {result2.get('provider', 'unknown')}")
        print(f"📏 Distance: {result2.get('distance_km', 0)} km")
        print(f"⏱️ Duration: {result2.get('duration_minutes', 0)} minutes")
        print()
        
        return True
        
    except Exception as e:
        print(f'❌ Route calculation failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print('🧪 Route Service Test Script')
    print('=' * 40)
    success = test_route_calculation()
    print('=' * 40)
    if success:
        print('✅ All tests passed!')
    else:
        print('❌ Some tests failed!')
