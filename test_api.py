#!/usr/bin/env python3
"""
Test script for route API endpoint
"""
import requests
import json

def test_route_api():
    """Test the route calculation API endpoint"""
    
    # API endpoint
    url = "http://localhost:8000/api/routes/calculate/"
    
    # Test data with working Karachi coordinates
    data = {
        "start_lat": 24.9352,
        "start_lng": 67.0364,
        "end_lat": 24.9313,
        "end_lng": 67.1140,
        "preference": "fastest"
    }
    
    print('🌐 Testing route calculation API...')
    print(f'📍 URL: {url}')
    print(f'📝 Request data: {json.dumps(data, indent=2)}')
    print()
    
    try:
        response = requests.post(url, json=data, headers={'Content-Type': 'application/json'})
        
        print(f'📊 Response status: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print('✅ API call successful!')
            print(f"📊 Provider: {result.get('provider', 'unknown')}")
            print(f"📏 Distance: {result.get('distance_km', 0)} km")
            print(f"⏱️ Duration: {result.get('duration_minutes', 0)} minutes")
            
            polyline = result.get('polyline', '')
            print(f"🛣️ Polyline length: {len(str(polyline))}")
            
            # Test polyline format
            if polyline:
                try:
                    if polyline.startswith('['):
                        coords = json.loads(polyline)
                        print(f"📍 Polyline format: JSON array with {len(coords)} points")
                        if len(coords) > 0:
                            print(f"📍 First point: {coords[0]} (lat, lng)")
                            print(f"📍 Last point: {coords[-1]} (lat, lng)")
                    else:
                        print(f"📍 Polyline format: Encoded string")
                except Exception as e:
                    print(f"⚠️ Could not parse polyline: {e}")
            
            return True
        else:
            print(f'❌ API call failed: {response.text}')
            return False
            
    except Exception as e:
        print(f'❌ API call exception: {e}')
        return False

if __name__ == '__main__':
    print('🧪 Route API Test Script')
    print('=' * 50)
    success = test_route_api()
    print('=' * 50)
    if success:
        print('✅ API test passed!')
    else:
        print('❌ API test failed!')
