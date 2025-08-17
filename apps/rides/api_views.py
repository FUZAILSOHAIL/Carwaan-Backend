"""
API views for route calculation endpoints
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .route_service import calculate_route_distance, get_route_alternatives
from apps.core.services import OpenRouteService
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
def calculate_route(request):
    """
    Calculate route between two points
    
    Expected JSON body:
    {
        "start_lat": 24.939106,
        "start_lng": 67.033946,
        "end_lat": 24.926132,
        "end_lng": 67.092689,
        "preference": "fastest"  // optional: "fastest", "shortest", "balanced"
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['start_lat', 'start_lng', 'end_lat', 'end_lng']
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'Missing required field: {field}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Get optional preference
        preference = data.get('preference', 'fastest')
        
        # Calculate route
        result = calculate_route_distance(
            start_lat=float(data['start_lat']),
            start_lng=float(data['start_lng']),
            end_lat=float(data['end_lat']),
            end_lng=float(data['end_lng']),
            preference=preference
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': f'Invalid data format: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Route calculation error: {str(e)}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def get_route_alternatives_api(request):
    """
    Get multiple route alternatives (fastest, shortest, balanced)
    
    Expected JSON body:
    {
        "start_lat": 24.939106,
        "start_lng": 67.033946,
        "end_lat": 24.926132,
        "end_lng": 67.092689
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['start_lat', 'start_lng', 'end_lat', 'end_lng']
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'Missing required field: {field}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Get route alternatives
        routes = get_route_alternatives(
            start_lat=float(data['start_lat']),
            start_lng=float(data['start_lng']),
            end_lat=float(data['end_lat']),
            end_lng=float(data['end_lng'])
        )
        
        return Response({
            'routes': routes,
            'count': len(routes)
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': f'Invalid data format: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Route alternatives error: {str(e)}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def calculate_route_with_waypoints(request):
    """
    Calculate route with multiple waypoints
    
    Expected JSON body:
    {
        "coordinates": [
            [67.033946, 24.939106],  // [lng, lat] format
            [67.050000, 24.930000],  // waypoint
            [67.092689, 24.926132]   // destination
        ]
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        if 'coordinates' not in data:
            return Response(
                {'error': 'Missing required field: coordinates'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        coordinates = data['coordinates']
        
        # Validate coordinates format
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            return Response(
                {'error': 'Coordinates must be a list with at least 2 points'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate route with waypoints
        result = OpenRouteService.get_route_with_waypoints(coordinates)
        
        return Response(result, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': f'Invalid data format: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Waypoints route error: {str(e)}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def route_service_status(request):
    """
    Get route service status and available providers
    """
    try:
        from .route_service import route_service
        
        return Response({
            'status': 'active',
            'providers_count': len(route_service.providers),
            'providers': [provider.__class__.__name__ for provider in route_service.providers],
            'api_key_configured': bool(getattr(request, 'OPENROUTE_SERVICE_API_KEY', None))
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Route service status error: {str(e)}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
