"""
Route calculation service for Carwaan backend
Handles road-based distance calculation with multiple routing providers
"""

import requests
import json
import math
import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class RouteCalculationError(Exception):
    """Exception raised when route calculation fails"""
    pass


class RouteProvider:
    """Base class for route providers"""
    
    def calculate_route(self, start_lat: float, start_lng: float, 
                       end_lat: float, end_lng: float, 
                       preference: str = 'fastest') -> Dict[str, Any]:
        """Calculate route between two points"""
        raise NotImplementedError


class OpenRouteServiceProvider(RouteProvider):
    """OpenRouteService routing provider"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openrouteservice.org/v2/directions/driving-car"
    
    def calculate_route(self, start_lat: float, start_lng: float, 
                       end_lat: float, end_lng: float, 
                       preference: str = 'fastest') -> Dict[str, Any]:
        """Calculate route using OpenRouteService with GET request"""
        
        preference_map = {
            'fastest': 'fastest',
            'shortest': 'shortest',
            'balanced': 'recommended'
        }
        
        # Round coordinates to 6 decimal places for better precision
        rounded_start_lat = round(start_lat, 6)
        rounded_start_lng = round(start_lng, 6)
        rounded_end_lat = round(end_lat, 6)
        rounded_end_lng = round(end_lng, 6)
        
        # Prepare query parameters for GET request
        # OpenRouteService GET API expects start=lng,lat&end=lng,lat format
        params = {
            'api_key': self.api_key,
            'start': f"{rounded_start_lng},{rounded_start_lat}",  # lng,lat format
            'end': f"{rounded_end_lng},{rounded_end_lat}"         # lng,lat format
        }
        
        # Add preference if not fastest (default)
        ors_preference = preference_map.get(preference, 'fastest')
        if ors_preference != 'fastest':
            params['preference'] = ors_preference
        
        headers = {
            'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        }
        
        try:
            # Log the request details for debugging
            logger.info(f"OpenRouteService GET request: {self.base_url}")
            logger.info(f"Original coordinates: start_lat={start_lat}, start_lng={start_lng}, end_lat={end_lat}, end_lng={end_lng}")
            logger.info(f"Request params: {params}")
            
            response = requests.get(self.base_url, params=params, headers=headers, timeout=10)
            
            # Log response details for debugging
            logger.info(f"OpenRouteService response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"OpenRouteService error response: {response.text}")
            
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"OpenRouteService response keys: {data.keys()}")
            
            # Handle different response formats from OpenRouteService
            if 'features' in data and len(data['features']) > 0:
                # GeoJSON FeatureCollection format (from POST API)
                feature = data['features'][0]
                properties = feature.get('properties', {})
                summary = properties.get('summary', {})
                geometry = feature.get('geometry', {})
                
                # Convert coordinate array to encoded polyline for consistency
                coordinates = geometry.get('coordinates', [])
                encoded_polyline = self._encode_polyline(coordinates) if coordinates else ''
                
                return {
                    'distance_km': round(summary.get('distance', 0) / 1000, 2),  # Convert meters to km, 2 decimal places
                    'duration_minutes': round(summary.get('duration', 0) / 60, 2),  # Convert seconds to minutes, 2 decimal places
                    'polyline': encoded_polyline,
                    'provider': 'openrouteservice',
                    'preference': preference,
                    'instructions': self._extract_instructions(properties.get('segments', []))
                }
            elif 'routes' in data and len(data['routes']) > 0:
                # Standard routes format (from GET API)
                route = data['routes'][0]
                summary = route.get('summary', {})
                
                # Convert coordinate array to encoded polyline for consistency
                geometry = route.get('geometry', [])
                encoded_polyline = self._encode_polyline(geometry) if geometry else ''
                
                return {
                    'distance_km': round(summary.get('distance', 0) / 1000, 2),  # Convert meters to km, 2 decimal places
                    'duration_minutes': round(summary.get('duration', 0) / 60, 2),  # Convert seconds to minutes, 2 decimal places
                    'polyline': encoded_polyline,
                    'provider': 'openrouteservice',
                    'preference': preference,
                    'instructions': self._extract_instructions(route.get('segments', []))
                }
            else:
                # Unknown response format
                logger.error(f"Unknown OpenRouteService response format: {data}")
                raise RouteCalculationError("Unknown OpenRouteService response format")
            
        except requests.RequestException as e:
            # Log more specific error information
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(f"OpenRouteService 404: No route found between coordinates ({start_lat}, {start_lng}) to ({end_lat}, {end_lng}). This may indicate the area is not covered by OpenRouteService.")
                elif status_code == 403:
                    logger.error(f"OpenRouteService 403: API key may be invalid or quota exceeded")
                elif status_code == 401:
                    logger.error(f"OpenRouteService 401: API key unauthorized - check your API key")
                else:
                    logger.error(f"OpenRouteService HTTP {status_code}: {e}")
            else:
                logger.error(f"OpenRouteService network error: {e}")
            raise RouteCalculationError(f"OpenRouteService failed: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"OpenRouteService response parsing error: {e}")
            raise RouteCalculationError(f"Invalid OpenRouteService response: {e}")
    
    def _extract_instructions(self, segments: List[Dict]) -> List[str]:
        """Extract turn-by-turn instructions from route segments"""
        instructions = []
        for segment in segments:
            for step in segment.get('steps', []):
                instruction = step.get('instruction')
                if instruction:
                    instructions.append(instruction)
        return instructions
    
    def _is_within_coverage(self, lat: float, lng: float) -> bool:
        """
        Check if coordinates are within OpenRouteService coverage area.
        OpenRouteService primarily covers:
        - Europe: lat 35-71, lng -25 to 45
        - Some parts of North America, Australia, etc.
        
        For this app (Carwaan in Pakistan), coordinates will be around:
        - Pakistan: lat 23-37, lng 60-77
        
        OpenRouteService may not have full coverage for Pakistan.
        """
        # Pakistan coordinates roughly
        if 23 <= lat <= 37 and 60 <= lng <= 77:
            # In Pakistan region - OpenRouteService coverage may be limited
            logger.info(f"Coordinates in Pakistan region: {lat}, {lng} - ORS coverage may be limited")
            return True  # Try anyway, fallback will handle if it fails
        
        # Europe (main coverage area)
        if 35 <= lat <= 71 and -25 <= lng <= 45:
            return True
        
        # Add other known coverage areas as needed
        # For now, return True to attempt the request
        return True
    
    def _encode_polyline(self, coordinates):
        """
        Encode coordinate array to polyline string
        This converts OpenRouteService coordinate format to the frontend-expected format
        """
        try:
            if not coordinates:
                return ''
            
            # OpenRouteService returns [longitude, latitude] pairs
            # Convert to [latitude, longitude] format for map display
            lat_lng_pairs = []
            for coord in coordinates:
                if len(coord) >= 2:
                    lat_lng_pairs.append([coord[1], coord[0]])  # Convert [lng, lat] to [lat, lng]
            
            if not lat_lng_pairs:
                return ''
            
            # Return JSON string of [lat, lng] coordinates for the frontend
            # This format is compatible with most mapping libraries like Leaflet, Google Maps, etc.
            return json.dumps(lat_lng_pairs)
            
        except Exception as e:
            logger.warning(f"Failed to encode polyline: {e}")
            return ''
    
    @classmethod
    def get_distance_and_duration(cls, start_lat, start_lng, end_lat, end_lng):
        """
        Get distance and duration between two points using OpenRouteService
        This method provides compatibility with the old interface
        
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
            # Get API key from settings - use the correct environment variable name
            api_key = getattr(settings, 'OPENROUTE_SERVICE_API_KEY', None)
            
            # Debug: Print API key status
            print(f"API Key available: {bool(api_key)}")
            if api_key:
                print(f"API Key length: {len(api_key)}")
            
            if not api_key:
                # Fall back to Haversine calculation
                provider = HaversineProvider()
                result = provider.calculate_route(start_lat, start_lng, end_lat, end_lng)
                return {
                    'distance_km': round(result['distance_km'], 2),
                    'duration_minutes': round(result['duration_minutes'], 2),
                    'polyline': result['polyline'],
                    'success': True,
                    'error': 'Used Haversine fallback - no API key'
                }
            
            # Use OpenRouteService
            provider = cls(api_key)
            result = provider.calculate_route(start_lat, start_lng, end_lat, end_lng)
            
            return {
                'distance_km': round(result['distance_km'], 2),
                'duration_minutes': round(result['duration_minutes'], 2),
                'polyline': str(result['polyline']),
                'success': True,
                'error': None
            }
            
        except Exception as e:
            # Debug: Print the actual error
            print(f"OpenRouteService error: {str(e)}")
            
            # Fall back to Haversine calculation
            try:
                provider = HaversineProvider()
                result = provider.calculate_route(start_lat, start_lng, end_lat, end_lng)
                return {
                    'distance_km': round(result['distance_km'], 2),
                    'duration_minutes': round(result['duration_minutes'], 2),
                    'polyline': result['polyline'],
                    'success': True,
                    'error': f'API failed, used Haversine: {str(e)}'
                }
            except Exception as fallback_error:
                return {
                    'distance_km': 0.0,
                    'duration_minutes': 0,
                    'polyline': '',
                    'success': False,
                    'error': f'All methods failed: {str(fallback_error)}'
                }


class GoogleMapsProvider(RouteProvider):
    """Google Maps Directions API routing provider"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"
    
    def calculate_route(self, start_lat: float, start_lng: float, 
                       end_lat: float, end_lng: float, 
                       preference: str = 'fastest') -> Dict[str, Any]:
        """Calculate route using Google Maps Directions API"""
        
        # Google Maps parameters
        params = {
            'origin': f"{start_lat},{start_lng}",
            'destination': f"{end_lat},{end_lng}",
            'key': self.api_key,
            'mode': 'driving',
            'alternatives': 'false',  # Get only one route
            'units': 'metric'
        }
        
        # Add traffic model based on preference
        if preference == 'fastest':
            params['departure_time'] = 'now'
            params['traffic_model'] = 'best_guess'
        elif preference == 'shortest':
            params['avoid'] = 'highways'  # Prefer local roads for shortest distance
        # balanced uses default settings
        
        headers = {
            'Accept': 'application/json',
        }
        
        try:
            # Log the request details for debugging
            logger.info(f"Google Maps request: {self.base_url} with params: {params}")
            
            response = requests.get(self.base_url, params=params, headers=headers, timeout=10)
            
            # Log response details for debugging
            logger.info(f"Google Maps response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Google Maps error response: {response.text}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Check if the response is valid
            if data.get('status') != 'OK':
                error_msg = data.get('error_message', data.get('status', 'Unknown error'))
                logger.error(f"Google Maps API error: {error_msg}")
                raise RouteCalculationError(f"Google Maps API error: {error_msg}")
            
            if not data.get('routes'):
                raise RouteCalculationError("No routes found by Google Maps")
            
            route = data['routes'][0]
            leg = route['legs'][0]
            
            # Extract route information
            distance_m = leg['distance']['value']
            duration_s = leg['duration']['value']
            
            # Get polyline points
            polyline_points = route['overview_polyline']['points']
            
            # Extract turn-by-turn instructions
            instructions = []
            for step in leg['steps']:
                # Remove HTML tags from instructions
                instruction = re.sub('<[^<]+?>', '', step['html_instructions'])
                instructions.append(instruction)
            
            return {
                'distance_km': round(distance_m / 1000, 2),  # Convert meters to km
                'duration_minutes': round(duration_s / 60, 2),  # Convert seconds to minutes
                'polyline': polyline_points,  # Google's encoded polyline
                'provider': 'google_maps',
                'preference': preference,
                'instructions': instructions
            }
            
        except requests.RequestException as e:
            # Log more specific error information
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 403:
                    logger.error(f"Google Maps 403: API key may be invalid or quota exceeded")
                else:
                    logger.error(f"Google Maps HTTP {status_code}: {e}")
            else:
                logger.error(f"Google Maps network error: {e}")
            raise RouteCalculationError(f"Google Maps failed: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Google Maps response parsing error: {e}")
            raise RouteCalculationError(f"Invalid Google Maps response: {e}")


class HaversineProvider(RouteProvider):
    """Fallback provider using Haversine formula for straight-line distance"""
    
    def calculate_route(self, start_lat: float, start_lng: float, 
                       end_lat: float, end_lng: float, 
                       preference: str = 'fastest') -> Dict[str, Any]:
        """Calculate straight-line distance using Haversine formula"""
        
        distance_km = self._haversine_distance(start_lat, start_lng, end_lat, end_lng)
        
        # Estimate driving time based on distance and preference
        if preference == 'fastest':
            avg_speed = 45  # km/h for fastest route
        elif preference == 'shortest':
            avg_speed = 35  # km/h for shortest route
        else:
            avg_speed = 40  # km/h for balanced route
        
        # Add extra time for city driving
        if distance_km < 5:
            avg_speed *= 0.6  # Reduce speed for city driving
        elif distance_km < 20:
            avg_speed *= 0.8  # Mixed driving
        
        duration_minutes = (distance_km / avg_speed) * 60
        
        return {
            'distance_km': round(distance_km, 2),
            'duration_minutes': round(duration_minutes, 2),
            'polyline': '',  # No polyline for straight-line
            'provider': 'haversine',
            'preference': preference,
            'instructions': [
                f'Head towards destination ({end_lat:.4f}, {end_lng:.4f})',
                'You have arrived at your destination'
            ]
        }
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat_rad = math.radians(lat2 - lat1)
        delta_lng_rad = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat_rad / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng_rad / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return round(R * c, 2)


class RouteCalculationService:
    """Main service for route calculation"""
    
    def __init__(self):
        # Initialize providers in order of preference
        self.providers = []
        
        # Add Google Maps if API key is available (preferred for Pakistan)
        google_maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        if google_maps_api_key:
            self.providers.append(GoogleMapsProvider(google_maps_api_key))
            logger.info("Added Google Maps provider")
        
        # Add OpenRouteService if API key is available (good for Europe)
        ors_api_key = getattr(settings, 'OPENROUTE_SERVICE_API_KEY', None)
        if ors_api_key:
            self.providers.append(OpenRouteServiceProvider(ors_api_key))
            logger.info("Added OpenRouteService provider")
        
        # Always add Haversine as fallback
        self.providers.append(HaversineProvider())
        logger.info("Added Haversine fallback provider")
        
        logger.info(f"Initialized RouteCalculationService with {len(self.providers)} providers")
    
    def calculate_route(self, start_lat: float, start_lng: float, 
                       end_lat: float, end_lng: float, 
                       preference: str = 'fastest') -> Dict[str, Any]:
        """
        Calculate route between two points
        
        Args:
            start_lat: Starting latitude
            start_lng: Starting longitude
            end_lat: Ending latitude
            end_lng: Ending longitude
            preference: Route preference ('fastest', 'shortest', 'balanced')
        
        Returns:
            Dict containing route information
        """
        
        # Check if start and end are the same
        if self._is_same_location(start_lat, start_lng, end_lat, end_lng):
            return {
                'distance_km': 0.0,
                'duration_minutes': 0,
                'polyline': '',
                'provider': 'same_location',
                'preference': preference,
                'instructions': ['You are already at your destination']
            }
        
        # Create cache key
        cache_key = f"route_{start_lat}_{start_lng}_{end_lat}_{end_lng}_{preference}"
        
        # Try to get from cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info("Retrieved route from cache")
            return cached_result
        
        # Try each provider in order
        last_error = None
        for provider in self.providers:
            try:
                result = provider.calculate_route(start_lat, start_lng, end_lat, end_lng, preference)
                
                # Cache the result for 30 minutes
                cache.set(cache_key, result, 30 * 60)
                
                logger.info(f"Route calculated successfully using {result['provider']}")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                continue
        
        # If all providers failed, raise the last error
        if last_error:
            raise RouteCalculationError(f"All route providers failed. Last error: {last_error}")
        else:
            raise RouteCalculationError("No route providers available")
    
    def calculate_multiple_routes(self, start_lat: float, start_lng: float, 
                                 end_lat: float, end_lng: float) -> List[Dict[str, Any]]:
        """Calculate multiple route options (fastest, shortest, balanced)"""
        
        preferences = ['fastest', 'shortest', 'balanced']
        routes = []
        
        for preference in preferences:
            try:
                route = self.calculate_route(start_lat, start_lng, end_lat, end_lng, preference)
                routes.append(route)
            except Exception as e:
                logger.warning(f"Failed to calculate {preference} route: {e}")
        
        return routes
    
    def _is_same_location(self, lat1: float, lng1: float, lat2: float, lng2: float, 
                         threshold: float = 0.0001) -> bool:
        """Check if two locations are the same (within threshold)"""
        return (abs(lat1 - lat2) < threshold and abs(lng1 - lng2) < threshold)
    
    def estimate_fare(self, distance_km: float, departure_time, preference: str = 'fastest') -> Decimal:
        """Estimate fare based on route distance and preferences"""
        from .models import FareCalculator
        
        # Apply preference-based multiplier
        multiplier = Decimal('1.0')
        if preference == 'fastest':
            multiplier = Decimal('1.1')  # 10% premium for fastest route
        elif preference == 'shortest':
            multiplier = Decimal('0.95')  # 5% discount for shortest route
        
        fare_details = FareCalculator.calculate_individual_fare(distance_km, departure_time)
        base_fare = fare_details['fare_amount']
        
        return base_fare * multiplier


# Global instance
route_service = RouteCalculationService()


def calculate_route_distance(start_lat: float, start_lng: float, 
                           end_lat: float, end_lng: float, 
                           preference: str = 'fastest') -> Dict[str, Any]:
    """
    Convenience function to calculate route distance
    
    Returns:
        Dict with 'distance_km', 'duration_minutes', 'polyline', 'provider', etc.
    """
    return route_service.calculate_route(start_lat, start_lng, end_lat, end_lng, preference)


def get_route_alternatives(start_lat: float, start_lng: float, 
                          end_lat: float, end_lng: float) -> List[Dict[str, Any]]:
    """
    Get multiple route alternatives (fastest, shortest, balanced)
    """
    return route_service.calculate_multiple_routes(start_lat, start_lng, end_lat, end_lng)
