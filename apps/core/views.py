import logging
import polyline
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .services import OpenRouteService

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_route(request):
    """
    Get route information between two points using OpenRouteService
    
    Parameters:
    - start: "longitude,latitude" format
    - end: "longitude,latitude" format  
    - preference: "fastest" (default), "shortest", or "recommended"
    
    Returns:
    - route: Array of [lat, lng] coordinates
    - distance_km: Route distance in kilometers
    - duration_minutes: Estimated travel time in minutes
    - polyline_encoded: Encoded polyline string for efficient transmission
    """
    try:
        start = request.GET.get('start')
        end = request.GET.get('end')
        preference = request.GET.get('preference', 'fastest')
        
        if not start or not end:
            return Response({
                'error': 'Missing coordinates. Provide start and end as "longitude,latitude"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Parse coordinates
            start_coords = start.split(',')
            end_coords = end.split(',')
            
            if len(start_coords) != 2 or len(end_coords) != 2:
                raise ValueError("Invalid coordinate format")
            
            start_lng, start_lat = float(start_coords[0]), float(start_coords[1])
            end_lng, end_lat = float(end_coords[0]), float(end_coords[1])
            
        except (ValueError, IndexError) as e:
            return Response({
                'error': 'Invalid coordinate format. Use "longitude,latitude"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get route from route calculation service
        try:
            from apps.rides.route_service import calculate_route_distance
            route_data = calculate_route_distance(
                start_lat=start_lat,
                start_lng=start_lng, 
                end_lat=end_lat,
                end_lng=end_lng,
                preference=preference
            )
            # Add success flag for compatibility
            route_data['success'] = True
        except Exception as e:
            logger.error(f"Route calculation error: {str(e)}")
            route_data = {
                'success': False,
                'error': f'Route calculation failed: {str(e)}'
            }
        
        if not route_data['success']:
            return Response({
                'error': route_data.get('error', 'Failed to calculate route')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Decode polyline to coordinate array
        route_coordinates = []
        if route_data.get('polyline'):
            try:
                # Polyline library expects encoded string
                decoded_coords = polyline.decode(route_data['polyline'])
                # Convert to [lat, lng] format for frontend
                route_coordinates = [[lat, lng] for lat, lng in decoded_coords]
            except Exception as e:
                logger.warning(f"Failed to decode polyline: {e}")
                # Fallback: create simple straight line
                route_coordinates = [[start_lat, start_lng], [end_lat, end_lng]]
        else:
            # Fallback: create simple straight line  
            route_coordinates = [[start_lat, start_lng], [end_lat, end_lng]]
        
        response_data = {
            'success': True,
            'route': route_coordinates,
            'distance_km': route_data.get('distance_km', 0),
            'duration_minutes': route_data.get('duration_minutes', 0),
            'polyline_encoded': route_data.get('polyline', ''),
            'preference': preference,
            'method': 'openrouteservice'
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Route API error: {str(e)}")
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_route_with_waypoints(request):
    """
    Get route with multiple waypoints
    
    POST body:
    {
        "coordinates": [[lng1, lat1], [lng2, lat2], [lng3, lat3], ...],
        "preference": "fastest" (optional)
    }
    
    Returns:
    - route: Array of [lat, lng] coordinates
    - distance_km: Total route distance
    - duration_minutes: Total travel time
    - waypoint_distances: Distance between each waypoint pair
    """
    try:
        data = request.data
        coordinates = data.get('coordinates', [])
        preference = data.get('preference', 'fastest')
        
        if not coordinates or len(coordinates) < 2:
            return Response({
                'error': 'At least 2 coordinate pairs required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate coordinate format
        try:
            for coord in coordinates:
                if len(coord) != 2:
                    raise ValueError("Each coordinate must have longitude and latitude")
                float(coord[0])  # longitude
                float(coord[1])  # latitude
        except (ValueError, IndexError, TypeError) as e:
            return Response({
                'error': 'Invalid coordinates format. Expected [[lng, lat], ...]'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get route from OpenRouteService
        route_data = OpenRouteService.get_route_with_waypoints_and_preference(
            coordinates_list=coordinates,
            preference=preference
        )
        
        if not route_data['success']:
            return Response({
                'error': route_data.get('error', 'Failed to calculate route')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Decode polyline to coordinates
        route_coordinates = []
        if route_data.get('polyline'):
            try:
                decoded_coords = polyline.decode(route_data['polyline'])
                route_coordinates = [[lat, lng] for lat, lng in decoded_coords]
            except Exception as e:
                logger.warning(f"Failed to decode polyline: {e}")
                # Fallback: connect waypoints directly
                route_coordinates = [[coord[1], coord[0]] for coord in coordinates]
        else:
            route_coordinates = [[coord[1], coord[0]] for coord in coordinates]
        
        response_data = {
            'success': True,
            'route': route_coordinates,
            'distance_km': route_data.get('distance_km', 0),
            'duration_minutes': route_data.get('duration_minutes', 0),
            'polyline_encoded': route_data.get('polyline', ''),
            'waypoint_count': len(coordinates),
            'preference': preference,
            'method': 'openrouteservice'
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Waypoint route API error: {str(e)}")
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_route_alternatives(request):
    """
    Get multiple route alternatives between two points
    
    Parameters:
    - start: "longitude,latitude" format
    - end: "longitude,latitude" format
    - count: Number of alternatives (default: 3, max: 5)
    
    Returns array of route options with different preferences
    """
    try:
        start = request.GET.get('start')
        end = request.GET.get('end') 
        count = min(int(request.GET.get('count', 3)), 5)  # Max 5 alternatives
        
        if not start or not end:
            return Response({
                'error': 'Missing coordinates'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            start_coords = start.split(',')
            end_coords = end.split(',')
            start_lng, start_lat = float(start_coords[0]), float(start_coords[1])
            end_lng, end_lat = float(end_coords[0]), float(end_coords[1])
        except (ValueError, IndexError):
            return Response({
                'error': 'Invalid coordinate format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get different route preferences
        preferences = ['fastest', 'shortest', 'recommended'][:count]
        alternatives = []
        
        for pref in preferences:
            route_data = OpenRouteService.get_route_with_preferences(
                start_lat=start_lat,
                start_lng=start_lng,
                end_lat=end_lat, 
                end_lng=end_lng,
                preference=pref
            )
            
            if route_data['success']:
                # Decode polyline
                route_coordinates = []
                if route_data.get('polyline'):
                    try:
                        decoded_coords = polyline.decode(route_data['polyline'])
                        route_coordinates = [[lat, lng] for lat, lng in decoded_coords]
                    except Exception:
                        route_coordinates = [[start_lat, start_lng], [end_lat, end_lng]]
                else:
                    route_coordinates = [[start_lat, start_lng], [end_lat, end_lng]]
                
                alternatives.append({
                    'preference': pref,
                    'route': route_coordinates,
                    'distance_km': route_data.get('distance_km', 0),
                    'duration_minutes': route_data.get('duration_minutes', 0),
                    'polyline_encoded': route_data.get('polyline', '')
                })
        
        return Response({
            'success': True,
            'alternatives': alternatives,
            'count': len(alternatives)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Route alternatives API error: {str(e)}")
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
