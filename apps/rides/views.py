"""
RIDES APP VIEWSETS - ACTIVE vs DEPRECATED
==========================================

ACTIVE VIEWSETS (Use these):
✅ LocationViewSet - Workplace location management
✅ EnhancedRideViewSet - Main ride management (REPLACES old RideViewSet)
✅ RidePassengerViewSet - Passenger-ride relationship management
✅ RideRequestViewSet - Ride join request handling
✅ DriverDashboardView - Driver dashboard and statistics
✅ VehicleVerificationView - Vehicle verification process
✅ ReviewViewSet - Review system (REPLACES RideReviewViewSet)

DEPRECATED VIEWSETS (Commented out, don't use):
❌ RideViewSet - REPLACED by EnhancedRideViewSet (lines 113-1355)
❌ PassengerRideSearchView - REPLACED by EnhancedRideViewSet.search_rides_enhanced() (lines 1859-2043)
❌ RideReviewViewSet - REPLACED by ReviewViewSet (lines 2565-2630)

REDUNDANCY ELIMINATED:
- Old RideViewSet had basic functionality, EnhancedRideViewSet has PassengerFinder integration
- PassengerRideSearchView duplicated search functionality now in EnhancedRideViewSet
- RideReviewViewSet was basic, ReviewViewSet has rating statistics and better features
==========================================
"""

from django.shortcuts import render
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from django.db.models import F, ExpressionWrapper, FloatField, Q
from django.contrib.postgres.expressions import ArraySubquery
from django.core.exceptions import ValidationError
import logging
from datetime import datetime, timedelta
import math
import logging
from .models import (
    Ride,
    RidePassenger,
    Location,
    ScheduledRide,
    RideReview,
    RideDirection,
    FareCalculation,
    FareCalculator,
    RoutePoint,
    RideStop,
    RideRequest,
    DriverDashboard,
    PassengerFinder,
    Review,
)
from .serializers import (
    RideSerializer,
    RideCreateSerializer,
    RidePassengerSerializer,
    LocationSerializer,
    JoinRideSerializer,
    RideRatingSerializer,
    RideRequestSerializer,
    RideRequestCreateSerializer,
    DriverDashboardSerializer,
    PassengerRideSearchSerializer,
    PassengerRideResultSerializer,
    RidePassengerDetailSerializer,
    VehicleVerificationSerializer,
    RideReviewSerializer,
    ReviewSerializer,
    CreateReviewSerializer,
    UserReviewSummarySerializer,
)
from apps.users.models import User
from apps.users.models_vehicle import Vehicle
from datetime import timedelta
import json
import logging
from decimal import Decimal
from django.db.models import Avg
from apps.core.views_notifications import create_ride_notification

logger = logging.getLogger(__name__)


class IsDriverOrAdmin(permissions.BasePermission):
    """Permission to check if user is a driver or admin"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.has_car or request.user.is_admin()
        )


class IsRideDriver(permissions.BasePermission):
    """Permission to check if user is the ride driver"""

    def has_object_permission(self, request, view, obj):
        return obj.driver == request.user


class IsRidePassenger(permissions.BasePermission):
    """Permission to check if user is a passenger in the ride"""

    def has_object_permission(self, request, view, obj):
        return RidePassenger.objects.filter(ride=obj, passenger=request.user).exists()


class IsRideRequestDriver(permissions.BasePermission):
    """Permission to check if user is the driver of the ride for a ride request"""

    def has_object_permission(self, request, view, obj):
        # obj is a RideRequest, so we need to check obj.ride.driver
        return obj.ride.driver == request.user


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for location instances"""

    serializer_class = LocationSerializer
    queryset = Location.objects.all()

    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def workplaces(self, request):
        """Get all workplace locations"""
        workplaces = Location.objects.filter(is_workplace=True)
        serializer = self.get_serializer(workplaces, many=True)
        return Response(serializer.data)


class RideViewSet(viewsets.ModelViewSet):
    """
    ⚠️  DEPRECATED VIEWSET - DO NOT USE ⚠️ 
    
    This viewset has been REPLACED by EnhancedRideViewSet which provides:
    - Better search functionality with PassengerFinder integration  
    - Enhanced ride management features
    - Improved API responses and error handling
    - More comprehensive filtering and sorting
    
    🔄 Migration Guide:
    - Use EnhancedRideViewSet instead of this class
    - All endpoints moved to EnhancedRideViewSet
    - Enhanced search available at EnhancedRideViewSet.search_rides_enhanced()
    
    This class will be removed in a future version.
    """
#     """ViewSet for viewing and editing ride instances - DEPRECATED: Use EnhancedRideViewSet"""

    queryset = Ride.objects.all()

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == "create":
            return RideCreateSerializer
        if self.action == "join":
            return JoinRideSerializer
        return RideSerializer

    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action == "create":
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in [
            "update",
            "partial_update",
            "destroy",
            "cancel_ride",
            "manage_passengers",
        ]:
            permission_classes = [IsRideDriver]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """Request to join a ride as a passenger"""
        ride = self.get_object()

        if ride.status != "scheduled":
            return Response(
                {"error": "You can only join scheduled rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(
            data=request.data, context={"request": request, "ride": ride}
        )
        serializer.is_valid(raise_exception=True)
        passenger = serializer.save()

        # Return the passenger information
        response_serializer = RidePassengerSerializer(passenger)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel_ride(self, request, pk=None):
        """Driver cancels a ride"""
        ride = self.get_object()

        if ride.status not in ["scheduled", "in_progress"]:
            return Response(
                {"error": "You can only cancel scheduled or in-progress rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all passengers before cancelling the ride
        passengers = RidePassenger.objects.filter(ride=ride, status="confirmed")
        
        # Update ride status
        ride.status = "cancelled"
        ride.save()

        # Send cancellation notifications to all passengers
        ride_data = {
            'id': ride.id,
            'pickup_location': ride.pickup_location,
            'dropoff_location': ride.dropoff_location,
            'departure_time': ride.departure_time.isoformat() if ride.departure_time else '',
            'driver_name': f"{ride.driver.first_name} {ride.driver.last_name}",
        }
        
        notification_count = 0
        for passenger_obj in passengers:
            try:
                create_ride_notification(
                    recipient=passenger_obj.passenger,
                    ride_data=ride_data,
                    notification_type='ride_cancelled'
                )
                notification_count += 1
            except Exception as e:
                logger.error(f"Failed to send cancellation notification to passenger {passenger_obj.passenger.id}: {str(e)}")

        logger.info(f"Ride {ride.id} cancelled by driver {request.user.id}. Sent {notification_count} notifications to passengers.")

        serializer = self.get_serializer(ride)
        return Response({
            'ride': serializer.data,
            'notifications_sent': notification_count,
            'message': f'Ride cancelled successfully. {notification_count} passengers have been notified.'
        })

    @action(detail=True, methods=["post"])
    def leave_ride(self, request, pk=None):
        """Passenger leaves a ride"""
        ride = self.get_object()
        passenger = get_object_or_404(RidePassenger, ride=ride, passenger=request.user)

        if ride.status != "scheduled":
            return Response(
                {"error": "You can only leave a ride that hasn't started yet"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete the passenger entry
        passenger.delete()

        # Update available seats
        ride.update_available_seats()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["delete"])
    def delete_offered_ride(self, request, pk=None):
        """Driver deletes their offered ride if it hasn't started yet"""
        ride = self.get_object()
        current_time = timezone.now()

        # Check if user is the driver
        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can delete their offered ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if ride hasn't passed its departure time
        if ride.departure_time <= current_time:
            return Response(
                {"error": "Cannot delete a ride that has already started or passed its departure time"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if ride hasn't started yet
        if ride.status not in ["scheduled"]:
            return Response(
                {"error": "Can only delete scheduled rides that haven't started"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if there are passengers - driver should handle this appropriately
        passenger_count = RidePassenger.objects.filter(ride=ride, status="confirmed").count()
        if passenger_count > 0:
            return Response(
                {"error": f"Cannot delete ride with {passenger_count} confirmed passenger(s). Please cancel the ride instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete the ride
        ride.delete()

        return Response(
            {"message": "Ride deleted successfully"}, 
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def start_ride(self, request, pk=None):
        """Driver starts the ride - calculates fare automatically"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can start the ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            ride.start_ride()

            # Get dashboard info for immediate response
            dashboard_info = ride.get_dashboard_info()

            return Response(
                {
                    "message": "Ride started successfully",
                    "ride_id": ride.id,
                    "status": ride.status,
                    "started_at": ride.started_at,
                    "dashboard_info": dashboard_info,
                }
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def complete_ride(self, request, pk=None):
        """Driver completes the ride"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can complete the ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ride.status != "in_progress":
            return Response(
                {"error": "Only rides in progress can be completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark ride as completed
        ride.status = "completed"
        ride.save()

        # Update all confirmed passengers to completed status
        RidePassenger.objects.filter(ride=ride, status="confirmed").update(status="completed")

        # Get passengers that can be reviewed
        completed_passengers = ride.passengers.filter(status="completed")
        reviewable_passengers = []
        for passenger_obj in completed_passengers:
            # Check if already reviewed
            existing_review = Review.objects.filter(
                ride=ride,
                reviewer=request.user,
                reviewee=passenger_obj.user,
                reviewer_type='driver'
            ).first()
            
            if not existing_review:
                reviewable_passengers.append({
                    'id': passenger_obj.user.id,
                    'name': passenger_obj.user.get_full_name(),
                    'profile_picture': request.build_absolute_uri(passenger_obj.user.profile_picture.url) if passenger_obj.user.profile_picture else None,
                })

        return Response(
            {
                "message": "Ride completed successfully",
                "ride_id": ride.id,
                "status": ride.status,
                "reviewable_passengers": reviewable_passengers,
                "can_review_passengers": len(reviewable_passengers) > 0,
            }
        )

    @action(detail=True, methods=["get"])
    def driver_dashboard(self, request, pk=None):
        """Get comprehensive dashboard info for drivers"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can access dashboard"},
                status=status.HTTP_403_FORBIDDEN,
            )

        dashboard_info = ride.get_dashboard_info()
        return Response(dashboard_info)

    @action(detail=True, methods=["get"])
    def passenger_view(self, request, pk=None):
        """Get ride info from passenger perspective"""
        ride = self.get_object()

        # Check if user can view based on gender preferences
        if ride.female_only_ride and not request.user.can_join_female_only_ride():
            return Response(
                {"error": "This is a female-only ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        passenger_info = ride.get_passenger_view_info()
        return Response(passenger_info)

    @action(detail=True, methods=["get"])
    def passenger_details(self, request, pk=None):
        """Get detailed passenger information for ride preview"""
        ride = self.get_object()

        # Check if user can view based on gender preferences
        if ride.female_only_ride and not request.user.can_join_female_only_ride():
            return Response(
                {"error": "This is a female-only ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get detailed passenger information
        passenger_details = ride.get_passenger_details()
        
        # Add additional ride information
        ride_info = {
            'ride_id': ride.id,
            'driver_name': ride.driver.get_display_name(),
            'driver_rating': float(ride.driver.driver_rating) if ride.driver.driver_rating else 0.0,
            'vehicle_info': f"{ride.vehicle.make} {ride.vehicle.model}" if ride.vehicle else "No vehicle info",
            'departure_time': ride.departure_time,
            'pickup_location': ride.pickup_location,
            'dropoff_location': ride.dropoff_location,
            'estimated_distance_km': ride.estimated_distance_km,
            'estimated_duration_minutes': ride.estimated_duration_minutes,
            'price_per_seat': float(ride.price_per_seat) if ride.price_per_seat else 0.0,
            'gender_preference': ride.gender_preference,
            'is_female_only': ride.female_only_ride,
        }
        
        return Response({
            'ride_info': ride_info,
            'passenger_details': passenger_details
        })

    @action(detail=True, methods=["post"])
    def recalculate_route(self, request, pk=None):
        """Recalculate route using OpenRouteService"""
        ride = self.get_object()
        
        # Only driver can recalculate route
        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can recalculate the route"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        success = ride.calculate_route_with_openroute()
        
        if success:
            return Response({
                "message": "Route recalculated successfully",
                "distance_km": ride.estimated_distance_km,
                "duration_minutes": ride.estimated_duration_minutes,
                "polyline": ride.polyline
            })
        else:
            return Response({
                "message": "Route calculation failed, using fallback calculation",
                "distance_km": ride.estimated_distance_km,
                "duration_minutes": ride.estimated_duration_minutes
            })

    @action(detail=True, methods=["post"])
    def calculate_fare(self, request, pk=None):
        """Calculate fare for the ride based on current passengers"""
        ride = self.get_object()

        if ride.estimated_distance_km <= 0:
            return Response(
                {"error": "Distance must be set to calculate fare"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirmed_passengers = RidePassenger.objects.filter(
            ride=ride, status="confirmed"
        ).count()

        total_passengers = confirmed_passengers + 1  # +1 for driver consideration

        fare_details = FareCalculator.calculate_fare(
            distance_km=ride.estimated_distance_km,
            departure_time=ride.departure_time,
            passenger_count=total_passengers,
        )

        return Response(fare_details)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def get_route(self, request):
        """Calculate route between two points using route service - public endpoint"""
        try:
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
            from .route_service import calculate_route_distance
            
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
                    import json
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
            return Response({
                'success': False,
                'error': f'Invalid coordinates: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Route calculation error: {e}")
            return Response({
                'success': False,
                'error': 'Route calculation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"])
    def available_rides(self, request):
        """Get rides available for the current user"""
        user = request.user

        # Get user preferences
        gender_preference = request.query_params.get("gender_preference", "any")
        female_only = request.query_params.get("female_only", "false").lower() == "true"

        # Base queryset - only scheduled rides with available seats
        rides = (
            Ride.objects.filter(
                status="scheduled",
                available_seats__gt=0,
                departure_time__gt=timezone.now(),
            )
            .exclude(driver=user)  # Exclude user's own rides
            .select_related("driver", "vehicle")
            .order_by("-created_at")  # Order by newest first
        )

        # Exclude rides where user is already a passenger
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Filter by gender preferences
        if female_only:
            # Only show female-only rides when filter is enabled
            rides = rides.filter(female_only_ride=True)
        else:
            # When female-only filter is off, exclude female-only rides for non-female users
            if not getattr(user, 'can_join_female_only_ride', lambda: False)():
                rides = rides.exclude(female_only_ride=True)

        if gender_preference and gender_preference != "any":
            rides = rides.filter(gender_preference__in=["any", gender_preference])

        # Serialize and return
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def schedule_ride(self, request):
        """Create a scheduled ride for future booking"""
        from .serializers import ScheduledRideSerializer

        serializer = ScheduledRideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheduled_ride = serializer.save(user=request.user)

        return Response(
            ScheduledRideSerializer(scheduled_ride).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def rate_ride(self, request, pk=None):
        """Rate and review a completed ride"""
        ride = self.get_object()

        if ride.status != "completed":
            return Response(
                {"error": "You can only rate completed rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user was part of this ride
        is_driver = ride.driver == request.user
        is_passenger = RidePassenger.objects.filter(
            ride=ride, passenger=request.user
        ).exists()

        if not (is_driver or is_passenger):
            return Response(
                {"error": "You can only rate rides you participated in"},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .serializers import RideReviewSerializer

        serializer = RideReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set reviewer and determine review type
        review_data = serializer.validated_data
        review_data["reviewer"] = request.user
        review_data["ride"] = ride

        # Create review
        review = RideReview.objects.create(**review_data)

        # Update user ratings
        if review.review_type == "passenger_to_driver":
            review.reviewee.update_driver_rating(review.rating)
        elif review.review_type == "driver_to_passenger":
            review.reviewee.update_passenger_rating(review.rating)

        return Response(
            RideReviewSerializer(review).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"])
    def my_offered_rides(self, request):
        """Get rides offered by the current user"""
        rides = Ride.objects.filter(driver=request.user).order_by("-created_at")
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_joined_rides(self, request):
        """Get rides joined by the current user"""
        ride_passengers = RidePassenger.objects.filter(
            passenger=request.user, status="confirmed"
        ).values_list("ride", flat=True)

        rides = Ride.objects.filter(id__in=ride_passengers).order_by("-created_at")
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_rides(self, request):
        """Search for rides based on advanced criteria with smart matching"""
        # Get basic parameters
        pickup = request.query_params.get("pickup")
        dropoff = request.query_params.get("dropoff")
        date = request.query_params.get("date")  # Format: YYYY-MM-DD
        workplace = request.query_params.get("workplace")

        # Get coordinates if available
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        dest_lat = request.query_params.get("dest_lat")
        dest_lng = request.query_params.get("dest_lng")

        # Get preference filters
        time_flexibility = request.query_params.get("time_flexibility", 30)  # Minutes
        female_only = request.query_params.get("female_only", "false").lower() == "true"
        
        try:
            time_flexibility = int(time_flexibility)
        except (ValueError, TypeError):
            time_flexibility = 30

        # Smart time filtering - look for rides within the flexible time window
        departure_time = request.query_params.get("departure_time")  # Format: HH:MM

        # Base query
        rides = Ride.objects.filter(status="scheduled", available_seats__gt=0)

        # Apply date filter if provided
        if date:
            rides = rides.filter(departure_time__date=date)

            # Apply smart time filtering if provided
            if departure_time:
                try:
                    # Parse time in format HH:MM
                    hour, minute = map(int, departure_time.split(":"))
                    # Create base datetime with today's date
                    base_time = timezone.now().replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )

                    # Update with the requested date
                    year, month, day = map(int, date.split("-"))
                    base_time = base_time.replace(year=year, month=month, day=day)

                    # Calculate time window
                    time_window_start = base_time - timedelta(minutes=time_flexibility)
                    time_window_end = base_time + timedelta(minutes=time_flexibility)

                    # Filter rides within time window
                    rides = rides.filter(
                        departure_time__gte=time_window_start,
                        departure_time__lte=time_window_end,
                    )
                except (ValueError, TypeError, IndexError):
                    # If time parsing fails, use date only
                    pass

        # Basic location filtering
        if pickup:
            rides = rides.filter(pickup_location__icontains=pickup)

        if dropoff:
            rides = rides.filter(dropoff_location__icontains=dropoff)

        # Workplace filtering
        if workplace:
            rides = rides.filter(
                Q(pickup_location__icontains=workplace)
                | Q(dropoff_location__icontains=workplace)
                | Q(driver__workplace__icontains=workplace)
            )

        # Exclude rides by/with the current user
        user = request.user
        rides = rides.exclude(driver=user)

        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Apply female-only filter if requested
        if female_only:
            # Only show female-only rides when filter is enabled
            rides = rides.filter(female_only_ride=True)
        else:
            # When female-only filter is off, exclude female-only rides for non-female users
            if not getattr(user, 'can_join_female_only_ride', lambda: False)():
                rides = rides.exclude(female_only_ride=True)

        # Advanced matching with coordinates
        if lat and lng and dest_lat and dest_lng:
            try:
                lat = float(lat)
                lng = float(lng)
                dest_lat = float(dest_lat)
                dest_lng = float(dest_lng)

                # Score and sort rides
                scored_rides = []
                for ride in rides:
                    match_score = ride.match_score(user, lat, lng, dest_lat, dest_lng)
                    scored_rides.append((ride, match_score))

                # Sort by score (highest first)
                scored_rides.sort(key=lambda x: x[1], reverse=True)

                # Return serialized rides with scores
                result = []
                for ride, score in scored_rides:
                    ride_data = self.get_serializer(ride).data
                    ride_data["match_score"] = score
                    result.append(ride_data)

                return Response(result)

            except (ValueError, TypeError):
                # Fall back to basic sorting if coordinate parsing fails
                pass

        # Return rides in default order if no advanced matching
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="search-rides-enhanced")
    def search_rides_enhanced(self, request):
        """Enhanced ride search for mobile app with detailed response format"""
        # Get search parameters
        pickup_location = request.query_params.get("pickup_location", "")
        dropoff_location = request.query_params.get("dropoff_location", "")
        pickup_latitude = request.query_params.get("pickup_latitude")
        pickup_longitude = request.query_params.get("pickup_longitude")
        dropoff_latitude = request.query_params.get("dropoff_latitude")
        dropoff_longitude = request.query_params.get("dropoff_longitude")
        departure_time = request.query_params.get("departure_time")
        female_only = request.query_params.get("female_only", "false").lower() == "true"

        # Base query - only scheduled rides with available seats
        rides = Ride.objects.filter(
            status="scheduled",
            available_seats__gt=0,
            departure_time__gt=timezone.now(),
        ).select_related("driver", "vehicle").exclude(driver=request.user)

        # Exclude rides where user is already a passenger
        user_joined_rides = RidePassenger.objects.filter(passenger=request.user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Apply female-only filtering
        if female_only:
            rides = rides.filter(female_only_ride=True)
        else:
            # Exclude female-only rides for non-female users
            if not getattr(request.user, 'can_join_female_only_ride', lambda: False)():
                rides = rides.exclude(female_only_ride=True)

        # Location filtering if provided
        if pickup_location:
            rides = rides.filter(pickup_location__icontains=pickup_location)
        
        if dropoff_location:
            rides = rides.filter(dropoff_location__icontains=dropoff_location)

        # Time filtering if provided
        if departure_time:
            try:
                # Handle both ISO format and simple datetime strings
                if departure_time.endswith('Z'):
                    target_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                elif '+' in departure_time or departure_time.endswith('00:00'):
                    target_time = datetime.fromisoformat(departure_time)
                else:
                    # Assume it's a naive datetime, make it timezone-aware
                    naive_time = datetime.fromisoformat(departure_time)
                    target_time = timezone.make_aware(naive_time, timezone.get_current_timezone())
                
                # Filter by same day only (more flexible than restrictive time window)
                target_date = target_time.date()
                rides = rides.filter(departure_time__date=target_date)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse departure_time '{departure_time}': {e}")
                pass

        # Prepare response data
        ride_results = []
        for ride in rides:
            # Calculate estimated fare for this passenger
            estimated_fare = float(ride.price_per_seat) if ride.price_per_seat else 0.0
            
            # Determine if it's peak hour
            is_peak_hour = self._is_peak_hour(ride.departure_time)
            if is_peak_hour:
                estimated_fare *= 1.2  # 20% peak hour surcharge

            # Build ride result
            ride_result = {
                'ride': {
                    'id': ride.id,
                    'pickup_location': ride.pickup_location,
                    'dropoff_location': ride.dropoff_location,
                    'pickup_latitude': float(ride.pickup_latitude) if ride.pickup_latitude else None,
                    'pickup_longitude': float(ride.pickup_longitude) if ride.pickup_longitude else None,
                    'dropoff_latitude': float(ride.dropoff_latitude) if ride.dropoff_latitude else None,
                    'dropoff_longitude': float(ride.dropoff_longitude) if ride.dropoff_longitude else None,
                    'departure_time': ride.departure_time.isoformat(),
                    'available_seats': ride.available_seats,
                    'total_seats': ride.total_seats,
                    'price_per_seat': float(ride.price_per_seat) if ride.price_per_seat else 0.0,
                    'female_only_ride': ride.female_only_ride,
                    'status': ride.status,
                    'estimated_distance_km': float(ride.estimated_distance_km) if ride.estimated_distance_km else 0.0,
                    'estimated_duration_minutes': ride.estimated_duration_minutes,
                    'notes': ride.notes or '',
                    'passengers': []  # Will be populated if needed
                },
                'driver': {
                    'id': ride.driver.id,
                    'first_name': ride.driver.first_name,
                    'last_name': ride.driver.last_name,
                    'rating': float(getattr(ride.driver, 'driver_rating', 0) or 0),
                    'total_rides': getattr(ride.driver, 'total_rides_as_driver', 0) or 0,
                    'verified': getattr(ride.driver, 'driver_verification_status', 'pending') == 'verified',
                },
                'vehicle': {
                    'make': ride.vehicle.make if ride.vehicle else 'Unknown',
                    'model': ride.vehicle.model if ride.vehicle else 'Car',
                    'year': ride.vehicle.year if ride.vehicle else None,
                    'color': ride.vehicle.color if ride.vehicle else 'Unknown',
                } if ride.vehicle else None,
                'estimated_fare': estimated_fare,
                'is_peak_hour': is_peak_hour,
                'seats_left': ride.available_seats,
            }
            
            ride_results.append(ride_result)

        return Response({
            'rides': ride_results,
            'total_count': len(ride_results),
            'search_params': {
                'pickup_location': pickup_location,
                'dropoff_location': dropoff_location,
                'departure_time': departure_time,
                'female_only': female_only,
            }
        })

    @action(detail=False, methods=["get"], url_path="my-ride-requests")
    def my_ride_requests(self, request):
        """Get current user's ride requests"""
        ride_requests = RideRequest.objects.filter(
            passenger=request.user
        ).select_related('ride', 'ride__driver', 'ride__vehicle').order_by('-created_at')

        requests_data = []
        for req in ride_requests:
            request_data = {
                'id': req.id,
                'ride_id': req.ride.id,
                'pickup_location': req.pickup_location,
                'dropoff_location': req.dropoff_location,
                'pickup_latitude': float(req.pickup_latitude) if req.pickup_latitude else None,
                'pickup_longitude': float(req.pickup_longitude) if req.pickup_longitude else None,
                'dropoff_latitude': float(req.dropoff_latitude) if req.dropoff_latitude else None,
                'dropoff_longitude': float(req.dropoff_longitude) if req.dropoff_longitude else None,
                'message': req.message,
                'status': req.status,
                'created_at': req.created_at.isoformat(),
                'estimated_fare': float(req.estimated_fare) if req.estimated_fare else 0.0,
                'driver_message': req.driver_message or '',
                'ride_info': {
                    'id': req.ride.id,
                    'pickup_location': req.ride.pickup_location,
                    'dropoff_location': req.ride.dropoff_location,
                    'departure_time': req.ride.departure_time.isoformat(),
                    'price_per_seat': float(req.ride.price_per_seat) if req.ride.price_per_seat else 0.0,
                    'status': req.ride.status,
                    'driver_name': f"{req.ride.driver.first_name} {req.ride.driver.last_name}",
                    'vehicle_info': f"{req.ride.vehicle.make} {req.ride.vehicle.model}" if req.ride.vehicle else "Unknown Vehicle"
                },
                'driver_info': {
                    'id': req.ride.driver.id,
                    'first_name': req.ride.driver.first_name,
                    'last_name': req.ride.driver.last_name,
                    'full_name': f"{req.ride.driver.first_name} {req.ride.driver.last_name}",
                    'profile_picture': req.ride.driver.profile_picture.url if req.ride.driver.profile_picture else None,
                    'rating': float(getattr(req.ride.driver, 'driver_rating', 0) or 0),
                    'total_rides': getattr(req.ride.driver, 'total_rides_as_driver', 0) or 0
                }
            }
            requests_data.append(request_data)

        return Response(requests_data)

    @action(detail=False, methods=["post"], url_path="create-ride-request")
    def create_ride_request(self, request):
        """Create a ride request for a specific ride"""
        try:
            ride_id = request.data.get('ride_id')
            pickup_location = request.data.get('pickup_location', '')
            dropoff_location = request.data.get('dropoff_location', '')
            pickup_latitude = request.data.get('pickup_latitude')
            pickup_longitude = request.data.get('pickup_longitude')
            dropoff_latitude = request.data.get('dropoff_latitude')
            dropoff_longitude = request.data.get('dropoff_longitude')
            message = request.data.get('message', '')

            # Validate ride exists and is available
            try:
                ride = Ride.objects.get(id=ride_id, status='scheduled', available_seats__gt=0)
            except Ride.DoesNotExist:
                return Response(
                    {'error': 'Ride not found or not available'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if user already has a request for this ride
            existing_request = RideRequest.objects.filter(
                ride=ride, passenger=request.user
            ).first()
            
            if existing_request:
                return Response(
                    {'error': 'You have already requested to join this ride'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user is already a passenger
            existing_passenger = RidePassenger.objects.filter(
                ride=ride, passenger=request.user
            ).first()
            
            if existing_passenger:
                return Response(
                    {'error': 'You are already a passenger in this ride'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user is the driver
            if ride.driver == request.user:
                return Response(
                    {'error': 'You cannot request to join your own ride'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check female-only ride restrictions
            if ride.female_only_ride and not getattr(request.user, 'can_join_female_only_ride', lambda: False)():
                return Response(
                    {'error': 'This is a female-only ride'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create the ride request
            ride_request = RideRequest.objects.create(
                ride=ride,
                passenger=request.user,
                pickup_location=pickup_location,
                dropoff_location=dropoff_location,
                pickup_latitude=pickup_latitude,
                pickup_longitude=pickup_longitude,
                dropoff_latitude=dropoff_latitude,
                dropoff_longitude=dropoff_longitude,
                message=message,
                status='pending'
            )

            # Calculate estimated fare if coordinates are provided
            if pickup_latitude and pickup_longitude and dropoff_latitude and dropoff_longitude:
                try:
                    # Simple distance calculation (this could be improved with actual routing)
                    distance = math.sqrt(
                        (float(dropoff_latitude) - float(pickup_latitude))**2 + 
                        (float(dropoff_longitude) - float(pickup_longitude))**2
                    ) * 111  # Rough conversion to km
                    
                    estimated_fare = float(ride.price_per_seat) if ride.price_per_seat else 0.0
                    
                    # Apply peak hour surcharge if applicable
                    if self._is_peak_hour(ride.departure_time):
                        estimated_fare *= 1.2
                    
                    ride_request.estimated_fare = estimated_fare
                    ride_request.estimated_distance_km = distance
                    ride_request.save()
                except (ValueError, TypeError):
                    pass

            return Response({
                'success': True,
                'message': 'Ride request sent successfully',
                'request_id': ride_request.id,
                'status': ride_request.status
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to create ride request: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def colleagues_rides(self, request):
        """Get rides offered by colleagues (users with the same workplace)"""
        user = request.user

        if not user.workplace:
            return Response(
                {"error": "You need to set your workplace to see colleagues' rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find users with the same workplace
        colleagues = User.objects.filter(workplace=user.workplace).exclude(id=user.id)

        # Get rides offered by colleagues
        rides = Ride.objects.filter(
            driver__in=colleagues,
            status="scheduled",
            departure_time__gt=timezone.now(),
            available_seats__gt=0,
        )

        # Exclude rides where the user has already requested to join
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recommended_rides(self, request):
        """Get personalized ride recommendations based on user preferences and history"""
        user = request.user

        # Basic query: scheduled rides with available seats in the future
        rides = Ride.objects.filter(
            status="scheduled", departure_time__gt=timezone.now(), available_seats__gt=0
        )

        # Exclude rides where the user is already a passenger or the driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Extract request parameters
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        dest_lat = request.query_params.get("dest_lat")
        dest_lng = request.query_params.get("dest_lng")

        # If we have valid coordinates, prioritize by proximity
        if lat and lng and dest_lat and dest_lng:
            try:
                lat = float(lat)
                lng = float(lng)
                dest_lat = float(dest_lat)
                dest_lng = float(dest_lng)

                # Calculate scores for each ride (we'll do this in Python for flexibility)
                scored_rides = []
                for ride in rides:
                    match_score = ride.match_score(user, lat, lng, dest_lat, dest_lng)
                    scored_rides.append((ride, match_score))

                # Sort by score (highest first)
                scored_rides.sort(key=lambda x: x[1], reverse=True)

                # Return serialized rides with scores
                result = []
                for ride, score in scored_rides:
                    ride_data = self.get_serializer(ride).data
                    ride_data["match_score"] = score
                    result.append(ride_data)

                return Response(result)

            except (ValueError, TypeError):
                # If coordinate parsing fails, fall back to basic filtering
                pass

        # Workplace-based matching
        if user.workplace:
            # First prioritize colleagues' rides (from same workplace)
            colleague_rides = rides.filter(driver__workplace=user.workplace)

            # Then rides to/from user's workplace
            workplace_rides = rides.filter(
                Q(pickup_location__icontains=user.workplace)
                | Q(dropoff_location__icontains=user.workplace)
            ).exclude(id__in=colleague_rides.values_list("id", flat=True))

            # Combine and add remaining rides
            other_rides = rides.exclude(
                id__in=colleague_rides.values_list("id", flat=True)
            ).exclude(id__in=workplace_rides.values_list("id", flat=True))

            # Combine the querysets in priority order
            rides = list(colleague_rides) + list(workplace_rides) + list(other_rides)
            serializer = self.get_serializer(rides, many=True)
            return Response(serializer.data)

        # If no workplace preference, just return all available rides
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def invite_connections(self, request, pk=None):
        """Invite colleagues or friends to join this ride"""
        ride = self.get_object()

        # Verify the user is the driver of this ride
        if request.user != ride.driver:
            return Response(
                {"error": "Only the driver can invite people to this ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get the list of user IDs to invite
        user_ids = request.data.get("user_ids", [])
        friend_group = request.data.get("friend_group", "")
        department = request.data.get("department", "")
        message = request.data.get("message", "")

        invited = []
        errors = []

        # Process individual invitations
        if user_ids:
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)

                    # Check if user is already in the ride
                    if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
                        errors.append(f"{user.full_name} is already in this ride")
                        continue

                    # Determine relationship type
                    relationship = "other"
                    if (
                        user.workplace
                        and request.user.workplace
                        and user.workplace == request.user.workplace
                    ):
                        relationship = "colleague"
                    elif request.user.connections.filter(id=user.id).exists():
                        relationship = "friend"

                    # Create a pending ride passenger entry
                    passenger = RidePassenger.objects.create(
                        ride=ride,
                        passenger=user,
                        status="pending",
                        invited_by=request.user,
                        relationship=relationship,
                    )

                    invited.append(user.full_name)

                    # TODO: Send notification to user

                except User.DoesNotExist:
                    errors.append(f"User with ID {user_id} not found")

        # Process friend group invitation
        if (
            friend_group
            and hasattr(request.user, "friend_groups")
            and request.user.friend_groups
        ):
            try:
                group_members = request.user.friend_groups.get(friend_group, [])
                if group_members:
                    for user_id in group_members:
                        try:
                            user = User.objects.get(id=user_id)

                            # Skip if already invited
                            if RidePassenger.objects.filter(
                                ride=ride, passenger=user
                            ).exists():
                                continue

                            # Create invitation
                            RidePassenger.objects.create(
                                ride=ride,
                                passenger=user,
                                status="pending",
                                invited_by=request.user,
                                relationship="friend",
                            )

                            invited.append(user.full_name)
                            # TODO: Send notification

                        except User.DoesNotExist:
                            continue
            except (KeyError, AttributeError):
                errors.append(f"Friend group '{friend_group}' not found")

        # Process department invitation (for workplace rides)
        if department and ride.is_workplace_ride:
            department_colleagues = User.objects.filter(
                workplace=request.user.workplace, department=department
            ).exclude(id=request.user.id)

            for colleague in department_colleagues:
                # Skip if already invited
                if RidePassenger.objects.filter(
                    ride=ride, passenger=colleague
                ).exists():
                    continue

                # Create invitation
                RidePassenger.objects.create(
                    ride=ride,
                    passenger=colleague,
                    status="pending",
                    invited_by=request.user,
                    relationship="colleague",
                )

                invited.append(colleague.full_name)
                # TODO: Send notification

        return Response(
            {
                "invited": invited,
                "errors": errors,
                "message": f"Successfully invited {len(invited)} people to the ride",
            }
        )

    @action(detail=False, methods=["get"])
    def friend_group_rides(self, request):
        """Get rides shared with specific friend groups"""
        user = request.user
        friend_group = request.query_params.get("group")

        if not friend_group:
            return Response(
                {"error": "You must specify a friend group"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find all rides that are marked with this friend group
        rides = Ride.objects.filter(
            status="scheduled",
            departure_time__gt=timezone.now(),
            available_seats__gt=0,
            friend_group=friend_group,
        )

        # Add rides where the driver is part of requested friend group
        if hasattr(user, "friend_groups") and user.friend_groups:
            try:
                group_members = user.friend_groups.get(friend_group, [])
                if group_members:
                    # Find rides offered by members of this group
                    group_rides = Ride.objects.filter(
                        driver_id__in=group_members,
                        status="scheduled",
                        departure_time__gt=timezone.now(),
                        available_seats__gt=0,
                    )
                    # Combine with other rides
                    rides = rides | group_rides
            except (KeyError, AttributeError):
                pass

        # Exclude rides where user is already a passenger or driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def social_connections_rides(self, request):
        """Get rides from connected users (friends or colleagues)"""
        user = request.user

        # Get IDs of all connected users
        connection_ids = user.connections.values_list("id", flat=True)

        # Add colleagues if workplace is set
        if user.workplace:
            colleague_ids = (
                User.objects.filter(workplace=user.workplace)
                .exclude(id=user.id)
                .values_list("id", flat=True)
            )

            # Combine connection IDs
            all_connections = list(connection_ids) + list(colleague_ids)
            # Remove duplicates
            all_connections = list(set(all_connections))
        else:
            all_connections = list(connection_ids)

        # Find rides from connections
        rides = Ride.objects.filter(
            driver_id__in=all_connections,
            status="scheduled",
            departure_time__gt=timezone.now(),
            available_seats__gt=0,
        )

        # Also include rides explicitly shared with friend groups user belongs to
        if hasattr(user, "friend_groups") and user.friend_groups:
            user_groups = list(user.friend_groups.keys())
            if user_groups:
                group_rides = Ride.objects.filter(
                    friend_group__in=user_groups,
                    status="scheduled",
                    departure_time__gt=timezone.now(),
                    available_seats__gt=0,
                )
                # Combine with connection rides
                rides = rides | group_rides

        # Exclude rides where user is already a passenger or driver
        rides = rides.exclude(driver=user)
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Sort by departure time
        rides = rides.order_by("departure_time")

        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def rate_ride(self, request, pk=None):
        """Rate a completed ride"""
        ride = self.get_object()

        # Check if ride is completed
        if ride.status != "completed":
            return Response(
                {"error": "You can only rate completed rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user was in this ride (driver or passenger)
        user = request.user
        is_driver = ride.driver == user
        is_passenger = RidePassenger.objects.filter(
            ride=ride, passenger=user, status="confirmed"
        ).exists()

        if not (is_driver or is_passenger):
            return Response(
                {"error": "You can only rate rides you participated in"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RideRatingSerializer(data=request.data)
        if serializer.is_valid():
            rating = serializer.validated_data["rating"]
            comment = serializer.validated_data.get("comment", "")

            # Update ride rating
            ride.update_rating(rating)

            # If passenger is rating, also update driver's rating
            if is_passenger:
                ride.driver.update_rating(rating)

            # TODO: Store individual ratings for detailed feedback
            # For now, we'll just return success

            return Response(
                {
                    "message": "Rating submitted successfully",
                    "new_average": float(ride.average_rating),
                    "total_ratings": ride.total_ratings,
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RidePassengerViewSet(viewsets.ModelViewSet):
    """ViewSet for ride passengers"""

    serializer_class = RidePassengerSerializer
    queryset = RidePassenger.objects.all()

    def get_permissions(self):
        """Set custom permissions for different actions"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Limit passengers to those visible to the current user"""
        user = self.request.user

        # Admin can see all
        if user.is_admin():
            return RidePassenger.objects.all()

        # Users can see passengers for rides they drive or are passengers in
        return RidePassenger.objects.filter(
            models.Q(ride__driver=user) | models.Q(passenger=user)
        )

    @action(detail=False, methods=["get"])
    def my_ride_requests(self, request):
        """Get all ride requests made by the current user"""
        requests = RidePassenger.objects.filter(passenger=request.user)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending_requests_for_my_rides(self, request):
        """Get all pending ride requests for rides offered by the current user"""
        requests = RidePassenger.objects.filter(
            ride__driver=request.user, status="pending"
        )
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def calculate_fare(self, request):
        """Calculate fare for a potential ride based on distance and other factors"""
        try:
            pickup_lat = float(request.data.get("pickup_lat"))
            pickup_lng = float(request.data.get("pickup_lng"))
            dropoff_lat = float(request.data.get("dropoff_lat"))
            dropoff_lng = float(request.data.get("dropoff_lng"))
            seats = int(request.data.get("seats", 1))
            departure_time = request.data.get("departure_time")

            # Parse departure time to check for peak hours
            peak_hours = False
            if departure_time:
                try:
                    dt = timezone.datetime.fromisoformat(
                        departure_time.replace("Z", "+00:00")
                    )
                    hour = dt.hour
                    # Peak hours: 7-10 AM and 5-8 PM on weekdays
                    if dt.weekday() < 5 and ((7 <= hour <= 10) or (17 <= hour <= 20)):
                        peak_hours = True
                except:
                    pass

            # Calculate distance using Haversine formula
            def calculate_distance(lat1, lon1, lat2, lon2):
                import math

                R = 6371.0  # Earth radius in kilometers
                lat1_rad = math.radians(lat1)
                lon1_rad = math.radians(lon1)
                lat2_rad = math.radians(lat2)
                lon2_rad = math.radians(lon2)
                dlon = lon2_rad - lon1_rad
                dlat = lat2_rad - lat1_rad
                a = (
                    math.sin(dlat / 2) ** 2
                    + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
                )
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                return R * c

            distance_km = calculate_distance(
                pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
            )

            # Fare calculation (PKR rates for Karachi)
            base_fare = Decimal("50.00")  # Base fare in PKR
            per_km_rate = Decimal(
                "30.00"
            )  # Per km rate in PKR (Rs. 30/km as requested)
            peak_multiplier = Decimal("2.0") if peak_hours else Decimal("1.0")

            # Calculate total fare
            distance_fare = Decimal(str(distance_km)) * per_km_rate
            total_fare = (base_fare + distance_fare) * peak_multiplier
            per_seat_fare = total_fare / seats

            # Breakdown
            breakdown = {
                "base_fare": float(base_fare),
                "distance_km": round(distance_km, 2),
                "distance_fare": float(distance_fare),
                "peak_multiplier": float(peak_multiplier),
                "is_peak_hours": peak_hours,
                "total_fare": float(total_fare),
                "per_seat_fare": float(per_seat_fare),
                "seats": seats,
                "currency": "PKR",
            }

            return Response(breakdown)

        except (ValueError, TypeError, KeyError) as e:
            return Response(
                {"error": f"Invalid data provided: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def search_areas(self, request):
        """Search for areas/locations in Karachi"""
        query = request.query_params.get("q", "").strip()

        # Predefined Karachi areas for quick search
        karachi_areas = [
            "Gulshan-e-Iqbal",
            "Clifton",
            "Defence (DHA)",
            "Saddar",
            "Korangi",
            "Malir",
            "Landhi",
            "North Nazimabad",
            "Gulberg",
            "Pechs",
            "SITE",
            "Orangi Town",
            "Shah Faisal Colony",
            "Liaquatabad",
            "New Karachi",
            "Federal B Area",
            "Bahadurabad",
            "Tariq Road",
            "Nazimabad",
            "Buffer Zone",
            "PIB Colony",
            "Johar Town",
            "Scheme 33",
            "Surjani Town",
            "North Karachi",
            "Bin Qasim",
            "Port Qasim",
            "Hawke's Bay",
            "Kemari",
            "Lyari",
            "Garden",
            "Civil Lines",
            "Boat Basin",
            "Sea View",
            "Zamzama",
            "Bukhari Commercial",
            "Bahadur Yar Jang Road",
            "University Road",
            "Shahrah-e-Faisal",
            "Main Rashid Minhas Road",
            "Guru Mandir",
            "Ranchore Line",
            "Teen Talwar",
            "Do Talwar",
            "Dolmen Mall",
            "Lucky One Mall",
            "Jinnah Hospital",
            "Aga Khan Hospital",
            "Liaquat National Hospital",
            "Karachi University",
            "NED University",
            "IBA",
            "Hamdard University",
            "PAF Museum",
            "Frere Hall",
            "Mazar-e-Quaid",
            "Empress Market",
        ]

        if not query:
            # Return popular areas if no query
            popular_areas = karachi_areas[:20]
            results = [{"name": area, "type": "area"} for area in popular_areas]
        else:
            # Filter areas based on query
            matched_areas = [
                area for area in karachi_areas if query.lower() in area.lower()
            ]
            results = [{"name": area, "type": "area"} for area in matched_areas[:10]]

            # Also search in database locations
            db_locations = Location.objects.filter(name__icontains=query)[:5]

            for loc in db_locations:
                results.append(
                    {
                        "name": loc.name,
                        "address": loc.address,
                        "type": (
                            "landmark"
                            if loc.is_landmark
                            else "workplace" if loc.is_workplace else "location"
                        ),
                        "lat": loc.latitude,
                        "lng": loc.longitude,
                    }
                )

        return Response(results)

    @action(detail=False, methods=["get"])
    def user_ride_history(self, request):
        """Get user's ride history with statistics"""
        user = request.user

        # Get rides where user was driver
        driven_rides = Ride.objects.filter(driver=user, status="completed")

        # Get rides where user was passenger
        passenger_rides = RidePassenger.objects.filter(
            passenger=user, status="confirmed", ride__status="completed"
        ).select_related("ride")

        # Calculate statistics
        total_driven = driven_rides.count()
        total_as_passenger = passenger_rides.count()

        # Calculate total distance (approximate)
        total_distance = sum(
            ride.estimated_distance_km
            for ride in driven_rides
            if ride.estimated_distance_km
        )

        # Get recent rides
        recent_driven = driven_rides.order_by("-departure_time")[:5]
        recent_passenger = [
            rp.ride for rp in passenger_rides.order_by("-ride__departure_time")[:5]
        ]

        stats = {
            "total_rides_driven": total_driven,
            "total_rides_as_passenger": total_as_passenger,
            "total_distance_km": round(total_distance, 2),
            "average_rating": float(user.average_rating),
            "total_ratings": user.total_ratings,
        }

        recent_rides = {
            "driven": self.get_serializer(recent_driven, many=True).data,
            "as_passenger": self.get_serializer(recent_passenger, many=True).data,
        }

        return Response({"statistics": stats, "recent_rides": recent_rides})


class RideRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for ride requests"""

    serializer_class = RideRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_verified_driver():
            # Driver can see requests for their rides
            return RideRequest.objects.filter(ride__driver=user)
        else:
            # Passenger can see their own requests
            return RideRequest.objects.filter(passenger=user)

    def get_serializer_class(self):
        if self.action == "create":
            return RideRequestCreateSerializer
        return RideRequestSerializer

    def perform_create(self, serializer):
        """Create ride request and calculate fare"""
        request_obj = serializer.save(passenger=self.request.user)

        # Calculate passenger distance and fare
        request_obj.estimated_distance_km = (
            PassengerFinder._calculate_passenger_distance(
                request_obj.pickup_latitude,
                request_obj.pickup_longitude,
                request_obj.dropoff_latitude,
                request_obj.dropoff_longitude,
                request_obj.ride,
            )
        )

        fare_details = request_obj.calculate_fare()
        request_obj.save()

    @action(detail=True, methods=["post"], permission_classes=[IsRideRequestDriver])
    def accept(self, request, pk=None):
        """Accept a ride request"""
        ride_request = self.get_object()
        driver_message = request.data.get("message", "")

        try:
            ride_passenger = ride_request.accept_request(driver_message)
            return Response(
                {
                    "success": True,
                    "message": "Request accepted successfully",
                    "passenger": RidePassengerDetailSerializer(ride_passenger).data,
                }
            )
        except ValueError as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], permission_classes=[IsRideRequestDriver])
    def reject(self, request, pk=None):
        """Reject a ride request"""
        ride_request = self.get_object()
        driver_message = request.data.get("message", "")

        try:
            ride_request.reject_request(driver_message)
            return Response({"success": True, "message": "Request rejected"})
        except ValueError as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class DriverDashboardView(viewsets.GenericViewSet):
    """ViewSet for driver dashboard functionality"""

    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """Only verified drivers can access dashboard"""
        # Check if user has driver capabilities (has_car attribute or is_driver)
        if hasattr(self.request.user, 'has_car') and not self.request.user.has_car:
            self.permission_denied(
                self.request, "Only verified drivers can access dashboard"
            )
        elif hasattr(self.request.user, 'is_driver') and not self.request.user.is_driver:
            self.permission_denied(
                self.request, "Only verified drivers can access dashboard"
            )
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Get driver dashboard data"""
        driver = request.user
        
        # Debug logging
        logger.info(f"Getting dashboard data for driver: {driver.id} - {driver.username}")
        print(f"DEBUG: Getting dashboard data for driver: {driver.id} - {driver.username}")
        
        # Get upcoming and active rides (same logic as upcoming_rides endpoint)
        now = timezone.now()
        week_ago = now - timezone.timedelta(days=7)
        
        upcoming_rides = Ride.objects.filter(
            driver=driver,
        ).filter(
            models.Q(status='in_progress') |  # Active rides (any time)
            models.Q(status='scheduled', departure_time__gte=now) |  # Future scheduled
            models.Q(status='completed', departure_time__gte=week_ago)  # Recent completed (7 days)
        ).order_by('departure_time')
        
        logger.info(f"Dashboard upcoming rides count: {upcoming_rides.count()}")
        print(f"DEBUG: Dashboard upcoming rides count: {upcoming_rides.count()}")
        
        # Get pending requests count
        pending_requests_count = RideRequest.objects.filter(
            ride__driver=driver,
            status='pending'
        ).count()
        
        logger.info(f"Dashboard pending requests count: {pending_requests_count}")
        print(f"DEBUG: Dashboard pending requests count: {pending_requests_count}")
        
        # Calculate statistics
        total_rides = Ride.objects.filter(driver=driver, status='completed').count()
        total_passengers = RidePassenger.objects.filter(
            ride__driver=driver, 
            status='confirmed'
        ).count()
        
        logger.info(f"Dashboard stats - total_rides: {total_rides}, total_passengers: {total_passengers}")
        print(f"DEBUG: Dashboard stats - total_rides: {total_rides}, total_passengers: {total_passengers}")
        
        # Calculate total earnings
        completed_rides = Ride.objects.filter(driver=driver, status='completed')
        total_earnings = 0
        for ride in completed_rides:
            confirmed_passengers = RidePassenger.objects.filter(
                ride=ride, status='confirmed'
            ).count()
            total_earnings += float(ride.price_per_seat) * confirmed_passengers
        
        # Get driver rating
        driver_rating = getattr(driver, 'driver_rating', 4.5)
        
        dashboard_data = {
            'upcoming_rides': RideSerializer(upcoming_rides, many=True).data,
            'pending_requests_count': pending_requests_count,
            'ride_statistics': {
                'total_rides': total_rides,
                'total_passengers': total_passengers,
                'total_earnings': float(total_earnings),
                'average_rating': float(driver_rating) if driver_rating else 4.5,
            }
        }
        
        logger.info(f"Dashboard response size: upcoming_rides={len(dashboard_data['upcoming_rides'])}")
        print(f"DEBUG: Dashboard response size: upcoming_rides={len(dashboard_data['upcoming_rides'])}")
        return Response(dashboard_data)

    @action(detail=False, methods=["get"])
    def upcoming_rides(self, request):
        """Get upcoming and active rides for driver"""
        driver = request.user
        
        # Debug logging
        logger.info(f"Getting upcoming rides for driver: {driver.id} - {driver.username}")
        print(f"DEBUG: Getting upcoming rides for driver: {driver.id} - {driver.username}")
        
        # Get all rides for this driver first for debugging
        all_driver_rides = Ride.objects.filter(driver=driver)
        logger.info(f"Total rides for driver {driver.id}: {all_driver_rides.count()}")
        print(f"DEBUG: Total rides for driver {driver.id}: {all_driver_rides.count()}")
        
        for ride in all_driver_rides:
            logger.info(f"Ride {ride.id}: status={ride.status}, departure_time={ride.departure_time}, future={ride.departure_time >= timezone.now()}")
            print(f"DEBUG: Ride {ride.id}: status={ride.status}, departure_time={ride.departure_time}, future={ride.departure_time >= timezone.now()}")
        
        # Show rides that are either:
        # 1. In progress (regardless of departure time) - active rides
        # 2. Scheduled and future
        # 3. Recent completed rides (last 30 days) for context
        now = timezone.now()
        month_ago = now - timezone.timedelta(days=30)
        
        upcoming_rides = Ride.objects.filter(
            driver=driver,
        ).filter(
            models.Q(status='in_progress') |  # Active rides (any time)
            models.Q(status='scheduled', departure_time__gte=now) |  # Future scheduled
            models.Q(status='completed', departure_time__gte=month_ago)  # Recent completed (7 days)
        ).order_by('departure_time')
        
        logger.info(f"Upcoming rides count: {upcoming_rides.count()}")
        print(f"DEBUG: Upcoming rides count: {upcoming_rides.count()}")
        
        # If no upcoming rides, also check for recent rides for debugging
        if upcoming_rides.count() == 0:
            recent_rides = Ride.objects.filter(driver=driver).order_by('-departure_time')[:5]
            logger.info(f"Recent rides for debugging:")
            print(f"DEBUG: Recent rides for debugging:")
            for ride in recent_rides:
                logger.info(f"  Ride {ride.id}: {ride.status}, {ride.departure_time}, future={ride.departure_time >= timezone.now()}")
                print(f"DEBUG:   Ride {ride.id}: {ride.status}, {ride.departure_time}, future={ride.departure_time >= timezone.now()}")
        
        rides_data = []
        for ride in upcoming_rides:
            passengers = RidePassenger.objects.filter(
                ride=ride, status='confirmed'
            ).select_related('passenger')
            
            ride_data = RideSerializer(ride).data
            ride_data.update({
                'seats_left': ride.available_seats,
                'can_start': ride.status == 'scheduled' and passengers.exists(),
                'pending_requests_count': RideRequest.objects.filter(
                    ride=ride, status='pending'
                ).count(),
                'passengers': [
                    {
                        'user': {
                            'first_name': p.passenger.first_name,
                            'last_name': p.passenger.last_name,
                        }
                    } for p in passengers
                ]
            })
            rides_data.append(ride_data)
        
        logger.info(f"Returning {len(rides_data)} rides")
        print(f"DEBUG: Returning {len(rides_data)} rides")
        return Response(rides_data)

    @action(detail=False, methods=["get"])
    def pending_requests(self, request):
        """Get pending ride requests"""
        driver = request.user
        
        # Debug logging
        logger.info(f"Getting pending requests for driver: {driver.id} - {driver.username}")
        
        # Check total requests for this driver
        all_requests = RideRequest.objects.filter(ride__driver=driver)
        logger.info(f"Total requests for driver {driver.id}: {all_requests.count()}")
        
        for req in all_requests:
            logger.info(f"Request {req.id}: status={req.status}, ride={req.ride.id}")
        
        requests = RideRequest.objects.filter(
            ride__driver=driver,
            status='pending'
        ).select_related('passenger', 'ride').order_by('-created_at')
        
        logger.info(f"Pending requests count: {requests.count()}")
        
        # If no pending requests, also check for recent requests for debugging
        if requests.count() == 0:
            recent_requests = RideRequest.objects.filter(ride__driver=driver).order_by('-created_at')[:5]
            logger.info(f"Recent requests for debugging:")
            for request in recent_requests:
                logger.info(f"  Request {request.id}: {request.status}, {request.created_at}")
        
        serializer = RideRequestSerializer(requests, many=True)
        logger.info(f"Returning {len(serializer.data)} pending requests")
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def start_ride(self, request, pk=None):
        """Start a specific ride"""
        try:
            ride = Ride.objects.get(pk=pk, driver=request.user)
            ride.status = 'in_progress'
            ride.save()
            
            return Response({
                "success": True,
                "message": "Ride started successfully",
                "ride": RideSerializer(ride).data,
            })
        except Ride.DoesNotExist:
            return Response(
                {"success": False, "error": "Ride not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {"success": False, "error": "Ride not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class PassengerRideSearchView(viewsets.GenericViewSet):
    """
    ⚠️  DEPRECATED VIEWSET - DO NOT USE ⚠️ 
    
    This viewset has been REPLACED by EnhancedRideViewSet.search_rides_enhanced() which provides:
    - PassengerFinder integration for intelligent matching
    - Enhanced fallback mechanisms  
    - Better response formatting
    - Improved error handling
    
    🔄 Migration Guide:
    - Use EnhancedRideViewSet.search_rides_enhanced() instead
    - All search functionality moved to main ride viewset
    
    This class will be removed in a future version.
    """
    """ViewSet for passenger ride search functionality"""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def search_rides(self, request):
        """Search for available rides along passenger's route"""
        try:
            # Parse coordinates - handle both data and query_params for flexibility
            data = request.data if request.method == 'POST' else request.query_params
            
            pickup_location = data.get('pickup_location', data.get('pickupLocation', ''))
            dropoff_location = data.get('dropoff_location', data.get('dropoffLocation', ''))
            
            # Parse coordinates
            try:
                pickup_lat = float(data.get('pickup_latitude', data.get('pickupLatitude', 0)))
                pickup_lng = float(data.get('pickup_longitude', data.get('pickupLongitude', 0)))
                dropoff_lat = float(data.get('dropoff_latitude', data.get('dropoffLatitude', 0)))
                dropoff_lng = float(data.get('dropoff_longitude', data.get('dropoffLongitude', 0)))
            except (ValueError, TypeError):
                # If coordinates are missing or invalid, we can still search by location text
                pickup_lat = pickup_lng = dropoff_lat = dropoff_lng = None
            
            # Parse departure time
            departure_time_str = data.get('departure_time', data.get('departureTime', ''))
            departure_time = None
            if departure_time_str:
                try:
                    if departure_time_str.endswith('Z'):
                        departure_time = datetime.fromisoformat(departure_time_str.replace('Z', '+00:00'))
                    elif '+' in departure_time_str:
                        departure_time = datetime.fromisoformat(departure_time_str)
                    else:
                        # Assume naive datetime, make it timezone-aware
                        naive_time = datetime.fromisoformat(departure_time_str)
                        departure_time = timezone.make_aware(naive_time, timezone.get_current_timezone())
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse departure_time '{departure_time_str}': {e}")
            
            # Get optional parameters
            female_only = data.get('female_only', data.get('femaleOnly', False))
            if isinstance(female_only, str):
                female_only = female_only.lower() == 'true'
            
            # Base query - only scheduled rides with available seats
            rides = Ride.objects.filter(
                status="scheduled",
                available_seats__gt=0,
                departure_time__gt=timezone.now(),
            ).select_related("driver", "vehicle").exclude(driver=request.user)

            # Exclude rides where user is already a passenger
            user_joined_rides = RidePassenger.objects.filter(passenger=request.user).values_list(
                "ride", flat=True
            )
            rides = rides.exclude(id__in=user_joined_rides)

            # Apply female-only filtering
            if female_only:
                rides = rides.filter(female_only_ride=True)
            else:
                # Exclude female-only rides for non-female users
                if not getattr(request.user, 'can_join_female_only_ride', lambda: False)():
                    rides = rides.exclude(female_only_ride=True)

            # Location filtering if provided
            if pickup_location:
                rides = rides.filter(pickup_location__icontains=pickup_location)
            
            if dropoff_location:
                rides = rides.filter(dropoff_location__icontains=dropoff_location)

            # Time filtering if provided
            if departure_time:
                try:
                    # Allow 2 hour window around the target time
                    time_window = timedelta(hours=2)
                    start_time = departure_time - time_window
                    end_time = departure_time + time_window
                    rides = rides.filter(departure_time__range=[start_time, end_time])
                except Exception as e:
                    logger.warning(f"Failed to filter by time: {e}")

            # Prepare response data similar to search_rides_enhanced
            ride_results = []
            for ride in rides:
                try:
                    # Calculate estimated fare for this passenger
                    estimated_fare = float(ride.price_per_seat) if ride.price_per_seat else 0.0
                    
                    # Determine if it's peak hour
                    is_peak_hour = self._is_peak_hour(ride.departure_time)
                    if is_peak_hour:
                        estimated_fare *= 1.2  # 20% peak hour surcharge

                    # Build ride result
                    ride_result = {
                        'ride': {
                            'id': ride.id,
                            'pickup_location': ride.pickup_location,
                            'dropoff_location': ride.dropoff_location,
                            'pickup_latitude': float(ride.pickup_latitude) if ride.pickup_latitude else None,
                            'pickup_longitude': float(ride.pickup_longitude) if ride.pickup_longitude else None,
                            'dropoff_latitude': float(ride.dropoff_latitude) if ride.dropoff_latitude else None,
                            'dropoff_longitude': float(ride.dropoff_longitude) if ride.dropoff_longitude else None,
                            'departure_time': ride.departure_time.isoformat(),
                            'available_seats': ride.available_seats,
                            'total_seats': ride.total_seats,
                            'price_per_seat': float(ride.price_per_seat) if ride.price_per_seat else 0.0,
                            'female_only_ride': ride.female_only_ride,
                            'status': ride.status,
                            'estimated_distance_km': float(ride.estimated_distance_km) if ride.estimated_distance_km else 0.0,
                            'estimated_duration_minutes': ride.estimated_duration_minutes,
                            'notes': ride.notes or '',
                            'passengers': []
                        },
                        'driver': {
                            'id': ride.driver.id,
                            'first_name': ride.driver.first_name,
                            'last_name': ride.driver.last_name,
                            'rating': float(getattr(ride.driver, 'driver_rating', 0) or 0),
                            'total_rides': getattr(ride.driver, 'total_rides_as_driver', 0) or 0,
                            'verified': getattr(ride.driver, 'driver_verification_status', 'pending') == 'verified',
                        },
                        'vehicle': {
                            'make': ride.vehicle.make if ride.vehicle else 'Unknown',
                            'model': ride.vehicle.model if ride.vehicle else 'Car',
                            'year': ride.vehicle.year if ride.vehicle else None,
                            'color': ride.vehicle.color if ride.vehicle else 'Unknown',
                        } if ride.vehicle else None,
                        'estimated_fare': estimated_fare,
                        'is_peak_hour': is_peak_hour,
                        'seats_left': ride.available_seats,
                    }
                    
                    ride_results.append(ride_result)
                
                except Exception as e:
                    logger.error(f"Error processing ride {ride.id}: {e}")
                    continue

            return Response({
                'rides': ride_results,
                'total_count': len(ride_results),
                'search_params': {
                    'pickup_location': pickup_location,
                    'dropoff_location': dropoff_location,
                    'departure_time': departure_time_str,
                    'female_only': female_only,
                }
            })
            
        except Exception as e:
            logger.error(f"Search rides error: {e}")
            return Response({
                'error': f'Failed to search rides: {str(e)}',
                'rides': [],
                'total_count': 0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"])
    def my_requests(self, request):
        """Get user's ride requests"""
        passenger = request.user
        requests = RideRequest.objects.filter(passenger=passenger).order_by(
            "-created_at"
        )
        serializer = RideRequestSerializer(requests, many=True)
        return Response(serializer.data)


class EnhancedRideViewSet(viewsets.ModelViewSet):
    """Enhanced ride viewset with new verification requirements"""

    serializer_class = RideSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Ride.objects.select_related("driver", "vehicle").prefetch_related(
            "ridepassenger_set__passenger"
        )

    def get_serializer_class(self):
        if self.action == "create":
            return RideCreateSerializer
        return RideSerializer

    def perform_create(self, serializer):
        """Create ride with enhanced validation"""
        driver = self.request.user
        vehicle_id = serializer.validated_data.pop("vehicle_id")

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, owner=driver)
            ride = Ride.create_ride(
                driver=driver, vehicle=vehicle, **serializer.validated_data
            )
            serializer.instance = ride
        except Vehicle.DoesNotExist:
            raise serializers.ValidationError("Vehicle not found or not owned by user")
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

    def create(self, request, *args, **kwargs):
        """Override create to handle ride creation properly"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Perform the creation with validation
        self.perform_create(serializer)
        
        # Return the created ride data
        return Response(
            RideSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def toggle_female_only(self, request, pk=None):
        """Toggle female-only status (only for female drivers)"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only ride driver can modify this setting"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.gender != "female":
            return Response(
                {"error": "Only female drivers can enable female-only rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ride.is_female_only = not ride.is_female_only
        ride.save()

        return Response({"success": True, "is_female_only": ride.is_female_only})

    @action(detail=True, methods=["get"])
    def passenger_requests(self, request, pk=None):
        """Get ride requests for this ride (driver only)"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only ride driver can view requests"},
                status=status.HTTP_403_FORBIDDEN,
            )

        requests = RideRequest.objects.filter(ride=ride, status="pending")
        serializer = RideRequestSerializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def start_ride(self, request, pk=None):
        """Driver starts the ride"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can start the ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ride.status != "scheduled":
            return Response(
                {"error": "Only scheduled rides can be started"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark ride as in progress
        ride.status = "in_progress"
        ride.save()

        return Response({
            "success": True,
            "message": "Ride started successfully",
            "ride": RideSerializer(ride).data,
        })

    @action(detail=True, methods=["post"])
    def complete_ride(self, request, pk=None):
        """Driver completes the ride"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can complete the ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ride.status != "in_progress":
            return Response(
                {"error": "Only rides in progress can be completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark ride as completed
        ride.status = "completed"
        ride.save()

        # Update all confirmed passengers to completed status
        RidePassenger.objects.filter(ride=ride, status="confirmed").update(status="completed")

        # Get passengers that can be reviewed
        completed_passengers = RidePassenger.objects.filter(ride=ride, status="completed")
        reviewable_passengers = []
        for passenger_obj in completed_passengers:
            # Check if already reviewed
            existing_review = Review.objects.filter(
                ride=ride,
                reviewer=request.user,
                reviewee=passenger_obj.passenger,
                reviewer_type='driver'
            ).first()
            
            if not existing_review:
                reviewable_passengers.append({
                    'id': passenger_obj.passenger.id,
                    'name': passenger_obj.passenger.get_full_name(),
                    'profile_picture': request.build_absolute_uri(passenger_obj.passenger.profile_picture.url) if passenger_obj.passenger.profile_picture else None,
                })

        return Response({
            "message": "Ride completed successfully",
            "ride_id": ride.id,
            "status": ride.status,
            "reviewable_passengers": reviewable_passengers,
            "can_review_passengers": len(reviewable_passengers) > 0,
        })

    @action(detail=True, methods=["post"])
    def cancel_ride(self, request, pk=None):
        """Driver cancels a ride"""
        ride = self.get_object()

        if ride.driver != request.user:
            return Response(
                {"error": "Only the driver can cancel the ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ride.status not in ["scheduled", "in_progress"]:
            return Response(
                {"error": "You can only cancel scheduled or in-progress rides"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all passengers before cancelling the ride
        passengers = RidePassenger.objects.filter(ride=ride, status="confirmed")
        
        # Update ride status
        ride.status = "cancelled"
        ride.save()

        # Send cancellation notifications to all passengers
        ride_data = {
            'id': ride.id,
            'pickup_location': ride.pickup_location,
            'dropoff_location': ride.dropoff_location,
            'departure_time': ride.departure_time.isoformat() if ride.departure_time else '',
            'driver_name': f"{ride.driver.first_name} {ride.driver.last_name}",
        }
        
        notification_count = 0
        for passenger_obj in passengers:
            try:
                create_ride_notification(
                    recipient=passenger_obj.passenger,
                    ride_data=ride_data,
                    notification_type='ride_cancelled'
                )
                notification_count += 1
            except Exception as e:
                logger.error(f"Failed to send cancellation notification to passenger {passenger_obj.passenger.id}: {str(e)}")

        logger.info(f"Ride {ride.id} cancelled by driver {request.user.id}. Sent {notification_count} notifications to passengers.")

        return Response({
            'success': True,
            'ride': RideSerializer(ride).data,
            'notifications_sent': notification_count,
            'message': f'Ride cancelled successfully. {notification_count} passengers have been notified.'
        })

    @action(detail=False, methods=["get"])
    def my_rides(self, request):
        """Get user's rides (as driver or passenger) categorized properly with enhanced information"""
        user = request.user
        current_time = timezone.now()

        # Rides as driver (these go to "My Offers") - ordered by newest first
        driver_rides = self.get_queryset().filter(driver=user).order_by("-created_at")

        # Rides as passenger - confirmed rides only
        passenger_rides_qs = self.get_queryset().filter(
            ridepassenger__passenger=user, ridepassenger__status="confirmed"
        ).select_related('driver').prefetch_related('ridepassenger_set')

        # Categorize passenger rides by time and status
        current_rides = []  # Future rides or ongoing rides
        past_rides = []     # Completed or rides past their departure time

        for ride in passenger_rides_qs:
            # Check if ride is in the past based on departure time
            is_past = ride.departure_time < current_time
            
            # Current rides: future rides that are scheduled or in progress
            if not is_past and ride.status in ['scheduled', 'in_progress']:
                current_rides.append(ride)
            # Past rides: completed, cancelled, or rides past their departure time
            elif is_past or ride.status in ['completed', 'cancelled']:
                past_rides.append(ride)

        # Sort by departure time for passenger rides
        current_rides.sort(key=lambda x: x.departure_time)
        past_rides.sort(key=lambda x: x.departure_time, reverse=True)

        # Get statistics
        offered_rides_stats = {
            'total': driver_rides.count(),
            'active': driver_rides.filter(status='scheduled').count(),
            'completed': driver_rides.filter(status='completed').count(),
            'total_passengers_served': sum(ride.total_seats - ride.available_seats for ride in driver_rides),
        }
        
        passenger_rides_stats = {
            'current': len(current_rides),
            'past': len(past_rides),
            'total': len(current_rides) + len(past_rides),
        }

        return Response(
            {
                "current_rides": RideSerializer(current_rides, many=True).data,  # Future rides I'm taking
                "past_rides": RideSerializer(past_rides, many=True).data,        # Past/completed rides I took  
                "offered_rides": RideSerializer(driver_rides, many=True).data,    # Rides I'm offering (newest first)
                "statistics": {
                    "offered_rides": offered_rides_stats,
                    "passenger_rides": passenger_rides_stats,
                }
            }
        )

    @action(detail=False, methods=["get"])
    def available_rides(self, request):
        """Get rides available for the current user with enhanced information"""
        user = request.user

        # Get user preferences
        gender_preference = request.query_params.get("gender_preference", "any")
        female_only = request.query_params.get("female_only", "false").lower() == "true"

        # Base queryset - only scheduled rides with available seats
        rides = (
            Ride.objects.filter(
                status="scheduled",
                available_seats__gt=0,
                departure_time__gt=timezone.now(),
            )
            .exclude(driver=user)  # Exclude user's own rides
            .select_related("driver", "vehicle")
            .prefetch_related("ridepassenger_set__passenger")
            .order_by("-created_at")  # Order by newest first
        )

        # Exclude rides where user is already a passenger
        user_joined_rides = RidePassenger.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Exclude rides where user has pending or confirmed requests
        user_requested_rides = RideRequest.objects.filter(passenger=user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_requested_rides)

        # Filter by gender preferences - automatically exclude female-only rides for non-female users
        if female_only or getattr(user, 'female_only_preference', False):
            rides = rides.filter(female_only_ride=True)
        elif not getattr(user, 'can_join_female_only_ride', lambda: False)():
            # Non-female users should not see female-only rides
            rides = rides.exclude(female_only_ride=True)

        if gender_preference and gender_preference != "any":
            rides = rides.filter(gender_preference__in=["any", gender_preference])

        # Add additional annotations for enhanced information
        rides = rides.annotate(
            seats_taken=models.F('total_seats') - models.F('available_seats'),
            occupancy_percentage=ExpressionWrapper(
                (models.F('total_seats') - models.F('available_seats')) * 100.0 / models.F('total_seats'),
                output_field=FloatField()
            )
        )

        # Serialize with enhanced data
        serializer = self.get_serializer(rides, many=True)
        
        # Add summary statistics
        total_rides = rides.count()
        female_only_count = rides.filter(female_only_ride=True).count()
        peak_hour_count = sum(1 for ride in rides if self._is_peak_hour(ride.departure_time))
        
        return Response({
            'rides': serializer.data,
            'summary': {
                'total_rides': total_rides,
                'female_only_rides': female_only_count,
                'peak_hour_rides': peak_hour_count,
                'filters_applied': {
                    'female_only': female_only,
                    'gender_preference': gender_preference
                }
            }
        })
    
    @action(detail=False, methods=["get"], url_path="search-rides-enhanced")
    def search_rides_enhanced(self, request):
        """Enhanced ride search for mobile app with detailed response format"""
        # Get search parameters
        pickup_location = request.query_params.get("pickup_location", "")
        dropoff_location = request.query_params.get("dropoff_location", "")
        pickup_latitude = request.query_params.get("pickup_latitude")
        pickup_longitude = request.query_params.get("pickup_longitude")
        dropoff_latitude = request.query_params.get("dropoff_latitude")
        dropoff_longitude = request.query_params.get("dropoff_longitude")
        departure_time = request.query_params.get("departure_time")
        female_only = request.query_params.get("female_only", "false").lower() == "true"

        # Use PassengerFinder for enhanced search with fallback
        if pickup_latitude and pickup_longitude and dropoff_latitude and dropoff_longitude and departure_time:
            try:
                # Parse departure time
                if departure_time.endswith('Z'):
                    target_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                elif '+' in departure_time or departure_time.endswith('00:00'):
                    target_time = datetime.fromisoformat(departure_time)
                else:
                    # Assume it's a naive datetime, make it timezone-aware
                    naive_time = datetime.fromisoformat(departure_time)
                    target_time = timezone.make_aware(naive_time, timezone.get_current_timezone())
                
                # Temporarily disable PassengerFinder to avoid description error
                # TODO: Fix PassengerFinder and re-enable
                # ride_results = PassengerFinder.find_rides(...)
                # For now, fall through to basic search
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse coordinates or departure_time: {e}")
                # Fall back to basic search
        
        # Fallback to basic search if coordinates/time not provided or parsing failed
        rides = Ride.objects.filter(
            status="scheduled",
            available_seats__gt=0,
            departure_time__gt=timezone.now(),
        ).select_related("driver", "vehicle").exclude(driver=request.user)

        # Exclude rides where user is already a passenger
        user_joined_rides = RidePassenger.objects.filter(passenger=request.user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_joined_rides)

        # Exclude rides where user has pending or confirmed requests
        user_requested_rides = RideRequest.objects.filter(passenger=request.user).values_list(
            "ride", flat=True
        )
        rides = rides.exclude(id__in=user_requested_rides)

        # Apply female-only filtering
        if female_only:
            rides = rides.filter(female_only_ride=True)
        else:
            # Exclude female-only rides for non-female users
            if not getattr(request.user, 'can_join_female_only_ride', lambda: False)():
                rides = rides.exclude(female_only_ride=True)

        # Location filtering if provided - use more flexible matching
        if pickup_location:
            # Split location into words for flexible matching
            pickup_words = pickup_location.strip().split()
            pickup_q = Q()
            for word in pickup_words:
                if len(word) >= 3:  # Only consider words with 3+ characters
                    pickup_q |= Q(pickup_location__icontains=word)
            if pickup_q:
                rides = rides.filter(pickup_q)
        
        if dropoff_location:
            # Split location into words for flexible matching
            dropoff_words = dropoff_location.strip().split()
            dropoff_q = Q()
            for word in dropoff_words:
                if len(word) >= 3:  # Only consider words with 3+ characters
                    dropoff_q |= Q(dropoff_location__icontains=word)
            if dropoff_q:
                rides = rides.filter(dropoff_q)

        # Coordinate-based route matching if coordinates provided
        if pickup_latitude and pickup_longitude and dropoff_latitude and dropoff_longitude:
            try:
                passenger_pickup_lat = float(pickup_latitude)
                passenger_pickup_lng = float(pickup_longitude)
                passenger_dropoff_lat = float(dropoff_latitude)
                passenger_dropoff_lng = float(dropoff_longitude)
                
                # Find rides where passenger route is along the driver's route
                route_matching_rides = []
                
                for ride in rides:
                    if ride.pickup_latitude and ride.pickup_longitude and ride.dropoff_latitude and ride.dropoff_longitude:
                        driver_pickup_lat = float(ride.pickup_latitude)
                        driver_pickup_lng = float(ride.pickup_longitude)
                        driver_dropoff_lat = float(ride.dropoff_latitude)
                        driver_dropoff_lng = float(ride.dropoff_longitude)
                        
                        # Check if passenger's journey fits within driver's route using enhanced route service
                        # Note: Using lat, lng format as expected by our route service
                        if self._is_passenger_on_route_enhanced(
                            driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                            passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng
                        ):
                            route_matching_rides.append(ride.id)
                
                # Filter rides to only those that match the route
                if route_matching_rides:
                    rides = rides.filter(id__in=route_matching_rides)
                else:
                    # If no route matches and we have coordinates, use proximity as fallback
                    proximity_km = 3.0  # Increased radius for broader search
                    lat_range = proximity_km / 111.0
                    lng_range = proximity_km / (111.0 * math.cos(math.radians(passenger_pickup_lat)))
                    
                    proximity_q = Q(
                        pickup_latitude__range=(passenger_pickup_lat - lat_range, passenger_pickup_lat + lat_range),
                        pickup_longitude__range=(passenger_pickup_lng - lng_range, passenger_pickup_lng + lng_range)
                    ) | Q(
                        dropoff_latitude__range=(passenger_dropoff_lat - lat_range, passenger_dropoff_lat + lat_range),
                        dropoff_longitude__range=(passenger_dropoff_lng - lng_range, passenger_dropoff_lng + lng_range)
                    )
                    
                    rides = rides.filter(proximity_q)
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse coordinates: {e}")
                pass

        # Time filtering if provided - more flexible time window
        if departure_time:
            try:
                # Handle both ISO format and simple datetime strings
                if departure_time.endswith('Z'):
                    target_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                elif '+' in departure_time or departure_time.endswith('00:00'):
                    target_time = datetime.fromisoformat(departure_time)
                else:
                    # Assume it's a naive datetime, make it timezone-aware
                    naive_time = datetime.fromisoformat(departure_time)
                    target_time = timezone.make_aware(naive_time, timezone.get_current_timezone())
                
                # More flexible time matching: within 2 hours of target time or same day
                target_date = target_time.date()
                time_window_start = target_time - timedelta(hours=2)
                time_window_end = target_time + timedelta(hours=2)
                
                # Filter by time window OR same day
                rides = rides.filter(
                    Q(departure_time__range=(time_window_start, time_window_end)) |
                    Q(departure_time__date=target_date)
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse departure_time '{departure_time}': {e}")
                pass

        # Check if we have specific search criteria results
        filtered_ride_count = rides.count()
        search_applied = bool(pickup_location or dropoff_location or departure_time)
        fallback_applied = False
        
        # If no rides found with specific criteria, show all available rides as fallback
        if filtered_ride_count == 0 and search_applied:
            logger.info(f"No rides found with specific criteria, showing all available rides as fallback")
            fallback_applied = True
            
            # Reset to base queryset with only basic filtering
            rides = Ride.objects.filter(
                status="scheduled",
                available_seats__gt=0,
                departure_time__gt=timezone.now(),
            ).select_related("driver", "vehicle").exclude(driver=request.user)

            # Exclude rides where user is already a passenger
            user_joined_rides = RidePassenger.objects.filter(passenger=request.user).values_list(
                "ride", flat=True
            )
            rides = rides.exclude(id__in=user_joined_rides)

            # Exclude rides where user has pending or confirmed requests
            user_requested_rides = RideRequest.objects.filter(passenger=request.user).values_list(
                "ride", flat=True
            )
            rides = rides.exclude(id__in=user_requested_rides)

            # Apply female-only filtering
            if female_only:
                rides = rides.filter(female_only_ride=True)
            else:
                # Exclude female-only rides for non-female users
                if not getattr(request.user, 'can_join_female_only_ride', lambda: False)():
                    rides = rides.exclude(female_only_ride=True)
            
            # Order by most recent first as requested
            rides = rides.order_by("-created_at")

        # Prepare response data
        ride_results = []
        for ride in rides:
            # Calculate estimated fare for this passenger
            estimated_fare = float(ride.price_per_seat) if ride.price_per_seat else 0.0
            
            # Determine if it's peak hour
            is_peak_hour = self._is_peak_hour(ride.departure_time)
            if is_peak_hour:
                estimated_fare *= 1.2  # 20% peak hour surcharge

            # Build ride result
            ride_result = {
                'ride': {
                    'id': ride.id,
                    'pickup_location': ride.pickup_location,
                    'dropoff_location': ride.dropoff_location,
                    'pickup_latitude': float(ride.pickup_latitude) if ride.pickup_latitude else None,
                    'pickup_longitude': float(ride.pickup_longitude) if ride.pickup_longitude else None,
                    'dropoff_latitude': float(ride.dropoff_latitude) if ride.dropoff_latitude else None,
                    'dropoff_longitude': float(ride.dropoff_longitude) if ride.dropoff_longitude else None,
                    'departure_time': ride.departure_time.isoformat(),
                    'available_seats': ride.available_seats,
                    'total_seats': ride.total_seats,
                    'price_per_seat': float(ride.price_per_seat) if ride.price_per_seat else 0.0,
                    'female_only_ride': ride.female_only_ride,
                    'status': ride.status,
                    'estimated_distance_km': float(ride.estimated_distance_km) if ride.estimated_distance_km else 0.0,
                    'estimated_duration_minutes': ride.estimated_duration_minutes,
                    'notes': ride.notes or '',
                    'passengers': []
                },
                'driver': {
                    'id': ride.driver.id,
                    'first_name': ride.driver.first_name,
                    'last_name': ride.driver.last_name,
                    'rating': float(getattr(ride.driver, 'driver_rating', 0) or 0),
                    'total_rides': getattr(ride.driver, 'total_rides_as_driver', 0) or 0,
                    'verified': getattr(ride.driver, 'driver_verification_status', 'pending') == 'verified',
                },
                'vehicle': {
                    'make': ride.vehicle.make if ride.vehicle else 'Unknown',
                    'model': ride.vehicle.model if ride.vehicle else 'Car',
                    'year': ride.vehicle.year if ride.vehicle else None,
                    'color': ride.vehicle.color if ride.vehicle else 'Unknown',
                } if ride.vehicle else None,
                'estimated_fare': estimated_fare,
                'is_peak_hour': is_peak_hour,
                'seats_left': ride.available_seats,
                'user_relationship': {
                    'can_request': True,  # Already filtered out rides user can't request
                    'is_female_only': ride.female_only_ride,
                    'user_gender_compatible': not ride.female_only_ride or getattr(request.user, 'can_join_female_only_ride', lambda: False)()
                }
            }
            
            ride_results.append(ride_result)

        return Response({
            'rides': ride_results,
            'total_count': len(ride_results),
            'search_params': {
                'pickup_location': pickup_location,
                'dropoff_location': dropoff_location,
                'departure_time': departure_time,
                'female_only': female_only,
            },
            'enhanced_search': False,
            'fallback_applied': fallback_applied
        })
    
    def _is_peak_hour(self, departure_time):
        """Check if departure time is during peak hours"""
        if not departure_time:
            return False
        hour = departure_time.hour
        # Peak hours: 7-10 AM and 5-8 PM
        return (7 <= hour <= 10) or (17 <= hour <= 20)

    def _is_passenger_on_route(self, driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                              passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng):
        """
        Check if passenger's pickup and dropoff locations are along the driver's route.
        Uses practical ride-sharing logic to determine route compatibility.
        """
        try:
            # Calculate distances using Haversine formula
            def haversine_distance(lat1, lng1, lat2, lng2):
                """Calculate distance between two points in kilometers"""
                R = 6371  # Earth's radius in kilometers
                lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
                c = 2 * math.asin(math.sqrt(a))
                return R * c

            # Calculate key distances
            driver_route_distance = haversine_distance(driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng)
            
            # Distance from driver pickup to passenger pickup
            driver_to_passenger_pickup = haversine_distance(driver_pickup_lat, driver_pickup_lng, passenger_pickup_lat, passenger_pickup_lng)
            
            # Distance from passenger pickup to passenger dropoff
            passenger_route_distance = haversine_distance(passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng)
            
            # Distance from passenger dropoff to driver dropoff
            passenger_dropoff_to_driver_dropoff = haversine_distance(passenger_dropoff_lat, passenger_dropoff_lng, driver_dropoff_lat, driver_dropoff_lng)
            
            # Distance if driver goes: driver_pickup -> passenger_pickup -> passenger_dropoff -> driver_dropoff
            total_route_with_passenger = driver_to_passenger_pickup + passenger_route_distance + passenger_dropoff_to_driver_dropoff
            
            # More lenient checks for practical ride sharing
            max_detour_ratio = 2.0  # Allow up to 100% extra distance (double the original route)
            max_pickup_detour = 8.0  # Max 8km detour to pick up passenger (increased for city coverage)
            max_dropoff_detour = 8.0  # Max 8km detour to drop off passenger
            
            # Basic distance checks
            if driver_to_passenger_pickup > max_pickup_detour:
                return False
            
            if passenger_dropoff_to_driver_dropoff > max_dropoff_detour:
                return False
            
            # Skip detour ratio check if driver route is very short (less than 2km)
            if driver_route_distance > 2.0:
                detour_ratio = total_route_with_passenger / driver_route_distance
                if detour_ratio > max_detour_ratio:
                    return False
            
            # More lenient directional check using simple coordinate logic
            def is_generally_same_direction(start_lat, start_lng, end_lat, end_lng, point_lat, point_lng):
                """Check if a point is generally in the direction from start to end"""
                # Calculate vectors
                route_vector_lat = end_lat - start_lat
                route_vector_lng = end_lng - start_lng
                point_vector_lat = point_lat - start_lat
                point_vector_lng = point_lng - start_lng
                
                # Calculate dot product to check direction similarity
                dot_product = route_vector_lat * point_vector_lat + route_vector_lng * point_vector_lng
                
                # If dot product is positive, generally same direction
                return dot_product >= 0
            
            # Check if passenger pickup is generally in the direction of driver's destination
            pickup_same_direction = is_generally_same_direction(
                driver_pickup_lat, driver_pickup_lng, 
                driver_dropoff_lat, driver_dropoff_lng,
                passenger_pickup_lat, passenger_pickup_lng
            )
            
            # Check if passenger dropoff is generally in the direction of driver's destination from passenger pickup
            dropoff_same_direction = is_generally_same_direction(
                passenger_pickup_lat, passenger_pickup_lng,
                driver_dropoff_lat, driver_dropoff_lng,
                passenger_dropoff_lat, passenger_dropoff_lng
            )
            
            # Accept if both directional checks pass OR if distances are very close (within 3km)
            if pickup_same_direction and dropoff_same_direction:
                return True
            
            # Alternative: Accept if passenger locations are very close to driver route endpoints
            pickup_close_to_start = driver_to_passenger_pickup <= 3.0
            dropoff_close_to_end = passenger_dropoff_to_driver_dropoff <= 3.0
            
            if pickup_close_to_start and dropoff_close_to_end:
                return True
            
            # Check if it's a reasonable route even with some backtracking (common in cities)
            # Accept if total detour is less than 50% of original route distance
            if driver_route_distance > 0:
                total_detour = (driver_to_passenger_pickup + passenger_dropoff_to_driver_dropoff)
                detour_percentage = total_detour / driver_route_distance
                
                # Allow reasonable detours for practical ride sharing
                if detour_percentage <= 0.8:  # 80% detour is acceptable
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error in route calculation: {e}")
            # If calculation fails, fall back to proximity check
            try:
                def simple_distance(lat1, lng1, lat2, lng2):
                    return math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2) * 111  # Rough km conversion
                
                # Simple proximity check as fallback
                pickup_distance = simple_distance(driver_pickup_lat, driver_pickup_lng, passenger_pickup_lat, passenger_pickup_lng)
                dropoff_distance = simple_distance(driver_dropoff_lat, driver_dropoff_lng, passenger_dropoff_lat, passenger_dropoff_lng)
                
                return pickup_distance <= 5.0 and dropoff_distance <= 5.0
            except:
                return False

    def _is_passenger_on_route_enhanced(self, driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                                     passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng):
        try:
            from .route_service import calculate_route_distance
            import json
            from shapely.geometry import LineString, Point

            driver_route = calculate_route_distance(
                start_lat=driver_pickup_lat, start_lng=driver_pickup_lng,
                end_lat=driver_dropoff_lat, end_lng=driver_dropoff_lng,
                preference='fastest'
            )

            if driver_route.get('provider') == 'haversine':
                logger.info("Fallback to basic route check due to route service limitations")
                return self._is_passenger_on_route(
                    driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                    passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng
                )

            driver_polyline = driver_route.get('polyline', '')
            if not driver_polyline or not driver_polyline.startswith('['):
                logger.warning("No valid polyline data available")
                return self._is_passenger_on_route(
                    driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                    passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng
                )

            driver_coords = json.loads(driver_polyline)
            if not driver_coords:
                logger.warning("Failed to parse driver polyline coordinates")
                return self._is_passenger_on_route(
                    driver_pickup_lat, driver_pickup_lng, driver_dropoff_lat, driver_dropoff_lng,
                    passenger_pickup_lat, passenger_pickup_lng, passenger_dropoff_lat, passenger_dropoff_lng
                )

            driver_linestring = LineString([(lng, lat) for lat, lng in driver_coords])
            passenger_pickup_point = Point(passenger_pickup_lng, passenger_pickup_lat)
            passenger_dropoff_point = Point(passenger_dropoff_lng, passenger_dropoff_lat)

            buffer_radius = 0.005  # ~500m
            driver_buffer = driver_linestring.buffer(buffer_radius)

            pickup_inside = driver_buffer.contains(passenger_pickup_point)
            dropoff_inside = driver_buffer.contains(passenger_dropoff_point)

            pickup_position = driver_linestring.project(passenger_pickup_point)
            dropoff_position = driver_linestring.project(passenger_dropoff_point)

            pickup_distance = driver_linestring.distance(passenger_pickup_point)
            dropoff_distance = driver_linestring.distance(passenger_dropoff_point)

            logger.info(f"""
            pickup_inside: {pickup_inside}, dropoff_inside: {dropoff_inside}
            pickup_position: {pickup_position:.4f}, dropoff_position: {dropoff_position:.4f}
            pickup_distance: {pickup_distance:.5f}, dropoff_distance: {dropoff_distance:.5f}
            """)

            if (pickup_distance <= buffer_radius and dropoff_distance <= buffer_radius and pickup_position < dropoff_position):
                return True

            return False

        except Exception as e:
            logger.error(f"Enhanced route matching failed: {str(e)}")
            return False

    
    def _haversine_distance(self, lat1, lng1, lat2, lng2):
        """Calculate distance between two points using Haversine formula"""
        import math
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat_rad = math.radians(lat2 - lat1)
        delta_lng_rad = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat_rad / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng_rad / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    @action(detail=True, methods=["get"])
    def passenger_details(self, request, pk=None):
        """Get detailed passenger information for ride preview"""
        ride = self.get_object()
        user = request.user

        # Check if user can view based on gender preferences
        if ride.female_only_ride and not user.can_join_female_only_ride():
            return Response(
                {"error": "This is a female-only ride"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get detailed passenger information
        passenger_details = ride.get_passenger_details()
        
        # Check user's relationship to this ride
        is_driver = ride.driver == user
        is_passenger = RidePassenger.objects.filter(ride=ride, passenger=user, status="confirmed").exists()
        has_pending_request = RideRequest.objects.filter(ride=ride, passenger=user, status="pending").exists()
        
        # Check if user has reviewed this ride (if it's completed and user was a passenger)
        has_reviewed = False
        user_review = None
        if is_passenger and ride.status == 'completed':
            existing_review = Review.objects.filter(
                ride=ride,
                reviewer=user,
                reviewee=ride.driver
            ).first()
            has_reviewed = existing_review is not None
            if existing_review:
                user_review = {
                    'overall_rating': existing_review.overall_rating,
                    'comment': existing_review.comment,
                    'created_at': existing_review.created_at.isoformat()
                }
        
        # Add additional ride information
        ride_info = {
            'ride_id': ride.id,
            'driver_name': ride.driver.get_display_name(),
            'driver_rating': float(ride.driver.driver_rating) if ride.driver.driver_rating else 0.0,
            'vehicle_info': f"{ride.vehicle.make} {ride.vehicle.model}" if ride.vehicle else "No vehicle info",
            'departure_time': ride.departure_time,
            'pickup_location': ride.pickup_location,
            'dropoff_location': ride.dropoff_location,
            'estimated_distance_km': round(float(ride.estimated_distance_km), 2) if ride.estimated_distance_km else 0.0,
            'estimated_duration_minutes': ride.estimated_duration_minutes,
            'price_per_seat': float(ride.price_per_seat) if ride.price_per_seat else 0.0,
            'gender_preference': ride.gender_preference,
            'is_female_only': ride.female_only_ride,
            'user_relationship': {
                'is_driver': is_driver,
                'is_passenger': is_passenger,
                'has_pending_request': has_pending_request,
                'can_join': not is_driver and not is_passenger and not has_pending_request and ride.available_seats > 0,
                'has_reviewed': has_reviewed,
                'user_review': user_review,
                'can_review': is_passenger and ride.status == 'completed' and not has_reviewed
            }
        }
        
        return Response({
            'ride_info': ride_info,
            'passenger_details': passenger_details
        })

    @action(detail=False, methods=["get"])
    def my_offered_rides(self, request):
        """Get rides offered by the current user"""
        rides = Ride.objects.filter(driver=request.user).order_by("-created_at")
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_joined_rides(self, request):
        """Get rides joined by the current user"""
        ride_passengers = RidePassenger.objects.filter(
            passenger=request.user, status="confirmed"
        ).values_list("ride", flat=True)

        rides = Ride.objects.filter(id__in=ride_passengers).order_by("-created_at")
        serializer = self.get_serializer(rides, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def past_rides_with_reviews(self, request):
        """Get past completed rides with review status for the passenger"""
        user = request.user
        current_time = timezone.now()

        # Get completed rides where user was a passenger
        ride_passengers = RidePassenger.objects.filter(
            passenger=user, 
            status="confirmed"
        ).select_related('ride', 'ride__driver').filter(
            Q(ride__status='completed') | Q(ride__departure_time__lt=current_time)
        )

        past_rides_data = []
        for rp in ride_passengers:
            ride = rp.ride
            
            # Check if user has reviewed this ride
            existing_review = Review.objects.filter(
                ride=ride,
                reviewer=user,
                reviewee=ride.driver
            ).first()
            
            # Serialize ride data
            ride_data = RideSerializer(ride).data
            ride_data.update({
                'has_been_reviewed': existing_review is not None,
                'review_id': existing_review.id if existing_review else None,
                'user_review': {
                    'overall_rating': existing_review.overall_rating,
                    'comment': existing_review.comment,
                    'created_at': existing_review.created_at.isoformat()
                } if existing_review else None,
                'can_review': ride.status == 'completed' and existing_review is None,
                'driver_info': {
                    'id': ride.driver.id,
                    'first_name': ride.driver.first_name,
                    'last_name': ride.driver.last_name,
                    'rating': float(getattr(ride.driver, 'driver_rating', 0) or 0)
                }
            })
            past_rides_data.append(ride_data)

        # Sort by departure time (newest first)
        past_rides_data.sort(key=lambda x: x['departure_time'], reverse=True)
        
        return Response({
            'past_rides': past_rides_data,
            'total_count': len(past_rides_data),
            'reviewable_count': sum(1 for ride in past_rides_data if ride['can_review'])
        })


class VehicleVerificationView(viewsets.GenericViewSet):
    """ViewSet for vehicle verification process"""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def my_vehicles(self, request):
        """Get user's vehicles with verification status"""
        user = request.user
        vehicles = Vehicle.objects.filter(owner=user)
        serializer = VehicleVerificationSerializer(vehicles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def submit_verification(self, request, pk=None):
        """Submit vehicle for verification"""
        try:
            vehicle = Vehicle.objects.get(pk=pk, owner=request.user)

            registration_book = request.FILES.get("registration_book")
            car_image = request.FILES.get("car_image")

            if registration_book:
                vehicle.car_registration_book_image = registration_book

            if car_image:
                vehicle.car_image = car_image

            vehicle.verification_status = "pending"
            vehicle.verification_submitted_at = timezone.now()
            vehicle.save()

            return Response(
                {"success": True, "message": "Vehicle submitted for verification"}
            )

        except Vehicle.DoesNotExist:
            return Response(
                {"error": "Vehicle not found"}, status=status.HTTP_404_NOT_FOUND
            )


class RideReviewViewSet(viewsets.ModelViewSet):
    """
    ⚠️  DEPRECATED VIEWSET - DO NOT USE ⚠️ 
    
    This viewset has been REPLACED by ReviewViewSet which provides:
    - Better review management with duplicate prevention
    - Rating distribution and statistics  
    - Enhanced user review summaries
    - More comprehensive review functionality
    
    🔄 Migration Guide:
    - Use ReviewViewSet instead of this class
    - All review endpoints moved to ReviewViewSet
    
    This class will be removed in a future version.
    """
    
    serializer_class = RideReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get reviews based on the user's role"""
        return RideReview.objects.filter(
            models.Q(reviewer=self.request.user) | models.Q(reviewee=self.request.user)
        ).order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def my_received(self, request):
        """Get reviews received by the current user"""
        reviews = RideReview.objects.filter(reviewee=request.user).order_by('-created_at')
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_given(self, request):
        """Get reviews given by the current user"""
        reviews = RideReview.objects.filter(reviewer=request.user).order_by('-created_at')
        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)/received')
    def user_received(self, request, user_id=None):
        """Get reviews received by a specific user (for viewing other users' profiles)"""
        try:
            user = User.objects.get(id=user_id)
            reviews = RideReview.objects.filter(reviewee=user).order_by('-created_at')
            serializer = self.get_serializer(reviews, many=True)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)/given')
    def user_given(self, request, user_id=None):
        """Get reviews given by a specific user (for viewing other users' profiles)"""
        try:
            user = User.objects.get(id=user_id)
            reviews = RideReview.objects.filter(reviewer=user).order_by('-created_at')
            serializer = self.get_serializer(reviews, many=True)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )


class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reviews between drivers and passengers"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateReviewSerializer
        return ReviewSerializer
    
    def get_queryset(self):
        return Review.objects.filter(
            models.Q(reviewer=self.request.user) | models.Q(reviewee=self.request.user)
        ).order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create a new review"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if review already exists
        existing_review = Review.objects.filter(
            ride=serializer.validated_data['ride'],
            reviewer=request.user,
            reviewee=serializer.validated_data['reviewee']
        ).first()
        
        if existing_review:
            return Response(
                {"error": "You have already reviewed this person for this ride"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review = serializer.save()
        response_serializer = ReviewSerializer(review, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def my_received(self, request):
        """Get reviews received by the current user"""
        reviews = Review.objects.filter(reviewee=request.user).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_given(self, request):
        """Get reviews given by the current user"""
        reviews = Review.objects.filter(reviewer=request.user).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_summary(self, request):
        """Get review summary for the current user"""
        user = request.user
        reviews = Review.objects.filter(reviewee=user).order_by('-created_at')
        
        # Calculate rating distribution
        total_reviews = reviews.count()
        if total_reviews == 0:
            return Response({
                'average_rating': 0.0,
                'total_reviews': 0,
                'rating_distribution': {
                    '5': 0,
                    '4': 0,
                    '3': 0,
                    '2': 0,
                    '1': 0,
                },
                'recent_reviews': []
            })
        
        rating_counts = {
            5: reviews.filter(overall_rating=5).count(),
            4: reviews.filter(overall_rating=4).count(),
            3: reviews.filter(overall_rating=3).count(),
            2: reviews.filter(overall_rating=2).count(),
            1: reviews.filter(overall_rating=1).count(),
        }
        
        average_rating = user.get_average_rating()
        recent_reviews = reviews[:5]  # Get 5 most recent reviews
        
        return Response({
            'average_rating': average_rating,
            'total_reviews': total_reviews,
            'rating_distribution': {
                '5': rating_counts[5],
                '4': rating_counts[4],
                '3': rating_counts[3],
                '2': rating_counts[2],
                '1': rating_counts[1],
            },
            'recent_reviews': ReviewSerializer(recent_reviews, many=True, context={'request': request}).data
        })
    
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)/summary')
    def user_review_summary(self, request, user_id=None):
        """Get review summary for a specific user"""
        try:
            user = User.objects.get(id=user_id)
            reviews = Review.objects.filter(reviewee=user).order_by('-created_at')
            
            # Calculate rating distribution
            total_reviews = reviews.count()
            if total_reviews == 0:
                return Response({
                    'average_rating': 0.0,
                    'total_reviews': 0,
                    'five_star_count': 0,
                    'four_star_count': 0,
                    'three_star_count': 0,
                    'two_star_count': 0,
                    'one_star_count': 0,
                    'recent_reviews': []
                })
            
            rating_counts = {
                5: reviews.filter(overall_rating=5).count(),
                4: reviews.filter(overall_rating=4).count(),
                3: reviews.filter(overall_rating=3).count(),
                2: reviews.filter(overall_rating=2).count(),
                1: reviews.filter(overall_rating=1).count(),
            }
            
            average_rating = user.get_average_rating()
            recent_reviews = reviews[:5]  # Get 5 most recent reviews
            
            return Response({
                'average_rating': average_rating,
                'total_reviews': total_reviews,
                'five_star_count': rating_counts[5],
                'four_star_count': rating_counts[4],
                'three_star_count': rating_counts[3],
                'two_star_count': rating_counts[2],
                'one_star_count': rating_counts[1],
                'recent_reviews': ReviewSerializer(recent_reviews, many=True, context={'request': request}).data
            })
            
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='ride/(?P<ride_id>[^/.]+)/passengers')
    def ride_passengers_for_review(self, request, ride_id=None):
        """Get passengers from a completed ride that the driver can review"""
        try:
            ride = Ride.objects.get(id=ride_id, driver=request.user, status='completed')
            passengers = ride.passengers.filter(status='completed')
            
            # Filter out passengers already reviewed
            unreviewed_passengers = []
            for passenger_obj in passengers:
                existing_review = Review.objects.filter(
                    ride=ride,
                    reviewer=request.user,
                    reviewee=passenger_obj.user,
                    reviewer_type='driver'
                ).first()
                
                if not existing_review:
                    unreviewed_passengers.append({
                        'id': passenger_obj.user.id,
                        'name': passenger_obj.user.get_full_name(),
                        'profile_picture': request.build_absolute_uri(passenger_obj.user.profile_picture.url) if passenger_obj.user.profile_picture else None,
                        'gender': passenger_obj.user.gender
                    })
            
            return Response(unreviewed_passengers)
            
        except Ride.DoesNotExist:
            return Response(
                {"error": "Ride not found or you don't have permission to review passengers"},
                status=status.HTTP_404_NOT_FOUND
            )
