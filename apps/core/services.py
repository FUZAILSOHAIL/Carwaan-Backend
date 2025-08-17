import requests
import logging
import os
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

class OpenRouteService:
    """Service for OpenRouteService API integration"""
    
    BASE_URL = "https://api.openrouteservice.org"
    API_KEY = os.getenv('OPENROUTE_SERVICE_API_KEY')
    
    @classmethod
    def _validate_api_key(cls):
        """Validate that API key is available"""
        if not cls.API_KEY:
            raise ValueError("OPENROUTE_SERVICE_API_KEY not found in environment variables")
        return cls.API_KEY
    
    @classmethod
    def get_distance_and_duration(cls, start_lat, start_lng, end_lat, end_lng):
        """
        Get distance and duration between two points using OpenRouteService
        
        Args:
            start_lat (float): Starting latitude
            start_lng (float): Starting longitude
            end_lat (float): Ending latitude
            end_lng (float): Ending longitude
            
        Returns:
            dict: {
                'distance_km': float,
                'duration_minutes': int,
                'polyline': str,
                'success': bool,
                'error': str (if any)
            }
        """
        try:
            api_key = cls._validate_api_key()
            
            headers = {
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
            }
            
            # Use GET request with query parameters as shown in the working example
            url = f"{cls.BASE_URL}/v2/directions/driving-car"
            params = {
                'api_key': api_key,
                'start': f"{start_lng},{start_lat}",  # longitude,latitude format
                'end': f"{end_lng},{end_lat}"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'features' in result and len(result['features']) > 0:
                    feature = result['features'][0]
                    properties = feature.get('properties', {})
                    summary = properties.get('summary', {})
                    
                    # Convert meters to kilometers
                    distance_km = round(summary.get('distance', 0) / 1000, 2)
                    
                    # Convert seconds to minutes
                    duration_minutes = round(summary.get('duration', 0) / 60)
                    
                    # Get geometry (polyline)
                    geometry = feature.get('geometry', {})
                    polyline = geometry.get('coordinates', [])
                    
                    return {
                        'distance_km': distance_km,
                        'duration_minutes': duration_minutes,
                        'polyline': str(polyline),  # Convert to string for consistency
                        'success': True,
                        'error': None
                    }
                else:
                    logger.error("No routes found in OpenRouteService response")
                    return cls._fallback_calculation(start_lat, start_lng, end_lat, end_lng)
                    
            else:
                logger.error(f"OpenRouteService API error: {response.status_code} - {response.text}")
                return cls._fallback_calculation(start_lat, start_lng, end_lat, end_lng)
                
        except requests.exceptions.Timeout:
            logger.error("OpenRouteService API timeout")
            return cls._fallback_calculation(start_lat, start_lng, end_lat, end_lng)
        except Exception as e:
            logger.error(f"OpenRouteService API error: {str(e)}")
            return cls._fallback_calculation(start_lat, start_lng, end_lat, end_lng)
    
    @classmethod
    def get_route_with_preferences(cls, start_lat, start_lng, end_lat, end_lng, preference='recommended'):
        """
        Get route with specific preferences using OpenRouteService
        
        Args:
            start_lat (float): Starting latitude
            start_lng (float): Starting longitude
            end_lat (float): Ending latitude
            end_lng (float): Ending longitude
            preference (str): Route preference ('recommended', 'fastest', 'shortest')
            
        Returns:
            dict: {
                'distance_km': float,
                'duration_minutes': int,
                'polyline': str,
                'success': bool,
                'error': str (if any),
                'preference': str
            }
        """
        try:
            api_key = cls._validate_api_key()
            
            headers = {
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
            }
            
            # Map preferences to OpenRouteService options
            preference_mapping = {
                'recommended': 'recommended',
                'fastest': 'fastest', 
                'shortest': 'shortest'
            }
            
            ors_preference = preference_mapping.get(preference, 'recommended')
            
            # Use GET request with query parameters
            url = f"{cls.BASE_URL}/v2/directions/driving-car"
            params = {
                'api_key': api_key,
                'start': f"{start_lng},{start_lat}",  # longitude,latitude format
                'end': f"{end_lng},{end_lat}"
            }
            
            # Add preference parameter if not recommended
            if ors_preference != 'recommended':
                params['preference'] = ors_preference
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'features' in result and len(result['features']) > 0:
                    feature = result['features'][0]
                    properties = feature.get('properties', {})
                    summary = properties.get('summary', {})
                    
                    # Convert meters to kilometers
                    distance_km = round(summary.get('distance', 0) / 1000, 2)
                    
                    # Convert seconds to minutes
                    duration_minutes = round(summary.get('duration', 0) / 60)
                    
                    # Get geometry (polyline)
                    geometry = feature.get('geometry', {})
                    polyline = geometry.get('coordinates', [])
                    
                    return {
                        'distance_km': distance_km,
                        'duration_minutes': duration_minutes,
                        'polyline': str(polyline),  # Convert to string for consistency
                        'success': True,
                        'error': None,
                        'preference': preference
                    }
                else:
                    logger.error("No routes found in OpenRouteService response")
                    return cls._fallback_calculation_with_preference(start_lat, start_lng, end_lat, end_lng, preference)
                    
            else:
                logger.error(f"OpenRouteService API error: {response.status_code} - {response.text}")
                return cls._fallback_calculation_with_preference(start_lat, start_lng, end_lat, end_lng, preference)
                
        except requests.exceptions.Timeout:
            logger.error("OpenRouteService API timeout")
            return cls._fallback_calculation_with_preference(start_lat, start_lng, end_lat, end_lng, preference)
        except Exception as e:
            logger.error(f"OpenRouteService API error: {str(e)}")
            return cls._fallback_calculation_with_preference(start_lat, start_lng, end_lat, end_lng, preference)

    @classmethod
    def _fallback_calculation_with_preference(cls, start_lat, start_lng, end_lat, end_lng, preference):
        """
        Fallback calculation with preference information
        """
        result = cls._fallback_calculation(start_lat, start_lng, end_lat, end_lng)
        result['preference'] = preference
        return result

    @classmethod
    def _fallback_calculation(cls, start_lat, start_lng, end_lat, end_lng):
        """
        Fallback calculation using Haversine formula
        """
        import math
        
        try:
            # Earth radius in kilometers
            R = 6371.0
            
            # Convert to radians
            lat1_rad = math.radians(start_lat)
            lon1_rad = math.radians(start_lng)
            lat2_rad = math.radians(end_lat)
            lon2_rad = math.radians(end_lng)
            
            # Differences
            dlon = lon2_rad - lon1_rad
            dlat = lat2_rad - lat1_rad
            
            # Haversine formula
            a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance_km = round(R * c, 2)
            
            # Estimate duration (assuming average speed of 40 km/h in city)
            duration_minutes = round((distance_km / 40) * 60)
            
            return {
                'distance_km': distance_km,
                'duration_minutes': duration_minutes,
                'polyline': '',
                'success': True,
                'error': 'Used fallback calculation'
            }
        except Exception as e:
            logger.error(f"Fallback calculation error: {str(e)}")
            return {
                'distance_km': 0.0,
                'duration_minutes': 0,
                'polyline': '',
                'success': False,
                'error': f'Calculation failed: {str(e)}'
            }
    
    @classmethod
    def get_route_with_waypoints(cls, coordinates_list):
        """
        Get route with multiple waypoints
        
        Args:
            coordinates_list (list): List of [longitude, latitude] pairs
            
        Returns:
            dict: Route information with distance, duration, and polyline
        """
        try:
            api_key = cls._validate_api_key()
            
            headers = {
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
            }
            
            # For multiple waypoints, we still need to use POST request
            # but with the correct format
            data = {
                "coordinates": coordinates_list,
                "instructions": False,
                "geometry": True,
                "elevation": False
            }
            
            url = f"{cls.BASE_URL}/v2/directions/driving-car"
            headers['Authorization'] = api_key
            headers['Content-Type'] = 'application/json'
            
            response = requests.post(url, json=data, headers=headers, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle both old and new response formats
                if 'routes' in result and len(result['routes']) > 0:
                    # Old format response
                    route = result['routes'][0]
                    summary = route['summary']
                    
                    return {
                        'distance_km': round(summary['distance'] / 1000, 2),
                        'duration_minutes': round(summary['duration'] / 60),
                        'polyline': route.get('geometry', ''),
                        'success': True,
                        'error': None
                    }
                elif 'features' in result and len(result['features']) > 0:
                    # New format response
                    feature = result['features'][0]
                    properties = feature.get('properties', {})
                    summary = properties.get('summary', {})
                    geometry = feature.get('geometry', {})
                    
                    return {
                        'distance_km': round(summary.get('distance', 0) / 1000, 2),
                        'duration_minutes': round(summary.get('duration', 0) / 60),
                        'polyline': str(geometry.get('coordinates', [])),
                        'success': True,
                        'error': None
                    }
            
            return {
                'distance_km': 0.0,
                'duration_minutes': 0,
                'polyline': '',
                'success': False,
                'error': 'No route found'
            }
            
        except Exception as e:
            logger.error(f"OpenRouteService waypoints error: {str(e)}")
            return {
                'distance_km': 0.0,
                'duration_minutes': 0,
                'polyline': '',
                'success': False,
                'error': str(e)
            }
        
