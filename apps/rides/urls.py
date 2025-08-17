from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # ACTIVE VIEWSETS - Only import the ones we actually use
    LocationViewSet, 
    RidePassengerViewSet,
    RideRequestViewSet, 
    DriverDashboardView, 
    EnhancedRideViewSet,  # Main ride management (replaces old RideViewSet)
    VehicleVerificationView, 
    ReviewViewSet,  # Main review system (replaces RideReviewViewSet)
    
    # DEPRECATED - Remove these imports when cleaning up
    # RideViewSet,  # DEPRECATED: Use EnhancedRideViewSet instead
    # PassengerRideSearchView,  # DEPRECATED: Use EnhancedRideViewSet.search_rides_enhanced() instead  
    # RideReviewViewSet,  # DEPRECATED: Use ReviewViewSet instead
)

app_name = 'rides'

router = DefaultRouter()
# MAIN ENDPOINTS - These are the active ones
router.register('rides', EnhancedRideViewSet, basename='ride')  # ✅ Enhanced ride management
router.register('locations', LocationViewSet)  # ✅ Workplace locations
router.register('ride-passengers', RidePassengerViewSet)  # ✅ Passenger management
router.register('ride-requests', RideRequestViewSet, basename='riderequest')  # ✅ Join requests
router.register('driver-dashboard', DriverDashboardView, basename='driver-dashboard')  # ✅ Driver dashboard
router.register('vehicle-verification', VehicleVerificationView, basename='vehicle-verification')  # ✅ Vehicle verification
router.register('user-reviews', ReviewViewSet, basename='user-reviews')  # ✅ Review system

# TEMPORARY COMPATIBILITY ENDPOINTS - Support mobile app's old URL patterns
# These redirect to the correct ViewSet methods
from .views import EnhancedRideViewSet
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response

# Create temporary views that redirect to the correct endpoints
@api_view(['GET'])
def available_rides_compat(request):
    """Compatibility endpoint for /api/rides/available_rides/"""
    viewset = EnhancedRideViewSet()
    viewset.request = request
    viewset.format_kwarg = None
    viewset.action = 'available_rides'  # Set the action attribute
    viewset.kwargs = {}  # Add kwargs attribute
    viewset.args = ()    # Add args attribute
    return viewset.available_rides(request)

@api_view(['GET']) 
def my_offered_rides_compat(request):
    """Compatibility endpoint for /api/rides/my_offered_rides/"""
    viewset = EnhancedRideViewSet()
    viewset.request = request
    viewset.format_kwarg = None
    viewset.action = 'my_offered_rides'  # Set the action attribute
    viewset.kwargs = {}  # Add kwargs attribute
    viewset.args = ()    # Add args attribute
    return viewset.my_offered_rides(request)

@api_view(['GET'])
def my_joined_rides_compat(request):
    """Compatibility endpoint for /api/rides/my_joined_rides/"""
    viewset = EnhancedRideViewSet()
    viewset.request = request
    viewset.format_kwarg = None
    viewset.action = 'my_joined_rides'  # Set the action attribute
    viewset.kwargs = {}  # Add kwargs attribute
    viewset.args = ()    # Add args attribute
    return viewset.my_joined_rides(request)

@api_view(['GET'])
def pending_requests_compat(request):
    """Compatibility endpoint for /api/ride-passengers/pending_requests_for_my_rides/"""
    viewset = RidePassengerViewSet()
    viewset.request = request  
    viewset.format_kwarg = None
    viewset.action = 'pending_requests_for_my_rides'  # Set the action attribute
    viewset.kwargs = {}  # Add kwargs attribute
    viewset.args = ()    # Add args attribute
    return viewset.pending_requests_for_my_rides(request)

@api_view(['GET'])
def get_route_compat(request):
    """Compatibility endpoint for /get-route/"""
    try:
        from rest_framework.response import Response
        from rest_framework import status
        import logging
        import json
        
        logger = logging.getLogger(__name__)
        
        # Get parameters from query string
        start_lat = float(request.query_params.get('start_lat'))
        start_lng = float(request.query_params.get('start_lng'))
        end_lat = float(request.query_params.get('end_lat'))
        end_lng = float(request.query_params.get('end_lng'))
        preference = request.query_params.get('preference', 'fastest')
        
        # Validate coordinates
        if not all([start_lat, start_lng, end_lat, end_lng]):
            return Response({
                'success': False,
                'error': 'Missing required coordinates'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use route service to calculate route
        from apps.rides.route_service import calculate_route_distance
        
        route_result = calculate_route_distance(
            start_lat=start_lat,
            start_lng=start_lng,
            end_lat=end_lat,
            end_lng=end_lng,
            preference=preference
        )
        
        # Parse polyline data
        polyline_data = route_result.get('polyline', '')
        route_coordinates = []
        
        if polyline_data:
            try:
                # Parse JSON coordinate array format
                if polyline_data.startswith('['):
                    route_coordinates = json.loads(polyline_data)
                else:
                    # Handle other polyline formats if needed
                    logger.warning(f"Unsupported polyline format: {polyline_data[:50]}...")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse polyline data: {e}")
        
        return Response({
            'success': True,
            'route': route_coordinates,
            'distance_km': route_result.get('distance_km', 0),
            'duration_minutes': route_result.get('duration_minutes', 0),
            'provider': route_result.get('provider', 'unknown')
        })
        
    except (ValueError, TypeError) as e:
        from rest_framework.response import Response
        from rest_framework import status
        return Response({
            'success': False,
            'error': f'Invalid coordinates: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        from rest_framework.response import Response
        from rest_framework import status
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Route calculation error: {e}")
        return Response({
            'success': False,
            'error': 'Route calculation failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def past_rides_compat(request):
    """Compatibility endpoint for /api/rides/past_rides_with_reviews/"""
    viewset = EnhancedRideViewSet()
    viewset.request = request
    viewset.format_kwarg = None
    viewset.action = 'past_rides_with_reviews'  # Set the action attribute
    viewset.kwargs = {}  # Add kwargs attribute
    viewset.args = ()    # Add args attribute
    return viewset.past_rides_with_reviews(request)

# DEPRECATED ENDPOINTS - Remove these when cleaning up deprecated viewsets
# router.register('passenger-search', PassengerRideSearchView, basename='passenger-search')  # ❌ Use EnhancedRideViewSet.search_rides_enhanced() instead
# router.register('reviews', RideReviewViewSet, basename='reviews')  # ❌ Use ReviewViewSet instead

urlpatterns = [
    path('', include(router.urls)),
    
    # Route calculation endpoint
    path('get-route/', get_route_compat, name='get-route'),
    
    # TEMPORARY COMPATIBILITY ENDPOINTS for mobile app
    path('available_rides/', available_rides_compat, name='available-rides-compat'),
    path('my_offered_rides/', my_offered_rides_compat, name='my-offered-rides-compat'), 
    path('my_joined_rides/', my_joined_rides_compat, name='my-joined-rides-compat'),
    path('past_rides_with_reviews/', past_rides_compat, name='past-rides-with-reviews-compat'),
    path('ride-passengers/pending_requests_for_my_rides/', pending_requests_compat, name='pending-requests-compat'),
]