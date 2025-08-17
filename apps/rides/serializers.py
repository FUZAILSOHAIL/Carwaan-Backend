from rest_framework import serializers
from .models import (
    Ride, RidePassenger, Location, RoutePoint, RideStop,
    ScheduledRide, RideReview, RideDirection, FareCalculation,
    RideRequest, DriverDashboard, PassengerFinder, Review
)
from apps.users.models import User
from apps.users.models_vehicle import Vehicle
from apps.users.serializers import UserSerializer
from apps.users.serializers_vehicle import VehicleListSerializer
from django.utils import timezone


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'address', 'latitude', 'longitude', 
                  'is_workplace', 'is_landmark', 'is_university']


class RoutePointSerializer(serializers.ModelSerializer):
    """Serializer for route points to display on map"""
    
    class Meta:
        model = RoutePoint
        fields = ['id', 'latitude', 'longitude', 'sequence']


class RideStopSerializer(serializers.ModelSerializer):
    """Serializer for intermediate stops"""
    
    class Meta:
        model = RideStop
        fields = ['id', 'location_name', 'address', 'latitude', 'longitude', 'sequence', 'scheduled_time']


class RidePassengerSerializer(serializers.ModelSerializer):
    passenger_name = serializers.ReadOnlyField(source='passenger.full_name')
    passenger_rating = serializers.SerializerMethodField()
    passenger_picture = serializers.SerializerMethodField()
    passenger_gender = serializers.ReadOnlyField(source='passenger.gender')
    
    class Meta:
        model = RidePassenger
        fields = [
            'id', 'ride', 'passenger', 'joined_at', 'status', 'pickup_note',
            'passenger_name', 'passenger_rating', 'passenger_picture', 'passenger_gender'
        ]
        read_only_fields = ['joined_at']
    
    def get_passenger_rating(self, obj):
        """Get passenger rating as float"""
        try:
            return float(obj.passenger.passenger_rating) if obj.passenger.passenger_rating else 0.0
        except (AttributeError, TypeError, ValueError):
            return 0.0
    
    def get_passenger_picture(self, obj):
        if obj.passenger.profile_picture:
            return obj.passenger.profile_picture.url
        return None


class RideSerializer(serializers.ModelSerializer):
    driver = UserSerializer(read_only=True)
    driver_rating = serializers.SerializerMethodField()
    vehicle = VehicleListSerializer(read_only=True)
    passengers = RidePassengerSerializer(source='ridepassenger_set', many=True, read_only=True)
    route_points = RoutePointSerializer(many=True, read_only=True)
    stops = RideStopSerializer(many=True, read_only=True)
    is_full = serializers.SerializerMethodField()
    match_score = serializers.SerializerMethodField()
    available_seats_display = serializers.SerializerMethodField()
    passenger_genders = serializers.SerializerMethodField()
    passenger_details = serializers.SerializerMethodField()
    estimated_distance_km = serializers.SerializerMethodField()
    ride_stats = serializers.SerializerMethodField()
    time_until_departure = serializers.SerializerMethodField()
    is_leaving_soon = serializers.SerializerMethodField()
    driver_total_rides = serializers.SerializerMethodField()
    driver_verified = serializers.SerializerMethodField()
    comfort_level = serializers.SerializerMethodField()
    
    class Meta:
        model = Ride
        fields = [
            'id', 'driver', 'driver_rating', 'vehicle', 'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'available_seats', 'available_seats_display',
            'status', 'recurring', 'notes', 'route_description', 'price_per_seat', 'passengers', 'is_full',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'time_flexibility_minutes', 'is_workplace_ride', 'recurring_days',
            'comfort_features', 'average_rating', 'match_score', 'gender_preference',
            'current_male_passengers', 'current_female_passengers', 'passenger_genders', 'polyline', 
            'estimated_distance_km', 'estimated_duration_minutes', 'route_points',
            'has_stops', 'stops', 'passenger_details', 'female_only_ride',
            'ride_stats', 'time_until_departure', 'is_leaving_soon', 'driver_total_rides',
            'driver_verified', 'comfort_level', 'created_at'
        ]
        read_only_fields = ['driver', 'vehicle', 'available_seats', 'status', 'average_rating', 
                           'current_male_passengers', 'current_female_passengers', 'created_at']
        
    def get_available_seats_display(self, obj):
        return f"{obj.available_seats}/{obj.total_seats}"
        
    def get_is_full(self, obj):
        return obj.is_full()
    
    def get_driver_rating(self, obj):
        """Return driver's rating"""
        try:
            # Try to access the driver and its rating
            if hasattr(obj, 'driver') and obj.driver:
                rating = obj.driver.driver_rating
                # Check if rating is a method or field
                if callable(rating):
                    # If it's callable, it might be a method, return default
                    print(f"WARNING: driver_rating is callable: {rating}")
                    return 4.5
                # Convert to float
                return float(rating) if rating is not None else 4.5
            else:
                print(f"WARNING: obj has no driver: {obj}")
                return 4.5
        except Exception as e:
            print(f"ERROR in get_driver_rating: {e}")
            return 4.5
    
    def get_match_score(self, obj):
        """Get match score if available, otherwise return None"""
        # match_score is a method that requires parameters, so we can't call it here
        # This should only be populated when specifically calculated in views
        return getattr(obj, '_match_score', None)
    
    def get_passenger_details(self, obj):
        """Get detailed passenger information for ride preview"""
        return obj.get_passenger_details()
    
    def get_passenger_genders(self, obj):
        """Return list of passenger genders for color coding"""
        return [p.passenger.gender for p in obj.ridepassenger_set.filter(status='confirmed')]
    
    def get_estimated_distance_km(self, obj):
        """Format estimated distance to 2 decimal places"""
        try:
            return round(float(obj.estimated_distance_km), 2) if obj.estimated_distance_km else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def get_ride_stats(self, obj):
        """Get comprehensive ride statistics"""
        return {
            'seats_occupied': obj.total_seats - obj.available_seats,
            'occupancy_rate': ((obj.total_seats - obj.available_seats) / obj.total_seats) * 100 if obj.total_seats > 0 else 0,
            'is_peak_hour': self._is_peak_hour(obj.departure_time),
            'age_hours': (timezone.now() - obj.created_at).total_seconds() / 3600 if obj.created_at else 0,
        }
    
    def get_time_until_departure(self, obj):
        """Get time until departure in minutes"""
        if obj.departure_time:
            delta = obj.departure_time - timezone.now()
            return int(delta.total_seconds() / 60) if delta.total_seconds() > 0 else 0
        return None
    
    def get_is_leaving_soon(self, obj):
        """Check if ride is leaving within 2 hours"""
        time_until = self.get_time_until_departure(obj)
        return time_until is not None and 0 < time_until <= 120
    
    def get_driver_total_rides(self, obj):
        """Get total rides offered by driver"""
        return Ride.objects.filter(driver=obj.driver).count()
    
    def get_driver_verified(self, obj):
        """Check if driver is verified"""
        return getattr(obj.driver, 'driver_verification_status', 'pending') == 'verified'
    
    def get_comfort_level(self, obj):
        """Get comfort level from features"""
        features = obj.comfort_features or {}
        return features.get('chat_level', 'moderate')
    
    def _is_peak_hour(self, departure_time):
        """Check if departure time is during peak hours"""
        if not departure_time:
            return False
        hour = departure_time.hour
        # Peak hours: 7-10 AM and 5-8 PM
        return (7 <= hour <= 10) or (17 <= hour <= 20)


class RideCreateSerializer(serializers.ModelSerializer):
    # Define explicitly to handle nested validation
    vehicle_id = serializers.IntegerField(write_only=True, help_text="ID of the vehicle to use for this ride")
    pickup_latitude = serializers.FloatField(required=False, allow_null=True)
    pickup_longitude = serializers.FloatField(required=False, allow_null=True)
    dropoff_latitude = serializers.FloatField(required=False, allow_null=True)
    dropoff_longitude = serializers.FloatField(required=False, allow_null=True)
    recurring_days = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    comfort_features = serializers.JSONField(required=False, allow_null=True)
    polyline = serializers.CharField(required=False, allow_blank=True)
    route_points = serializers.ListField(child=serializers.DictField(), required=False, allow_null=True)
    stops = serializers.ListField(child=serializers.DictField(), required=False, allow_null=True)
    
    class Meta:
        model = Ride
        fields = [
            'vehicle_id', 'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'recurring', 'notes', 'route_description', 'price_per_seat',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 
            'dropoff_longitude', 'time_flexibility_minutes', 'is_workplace_ride', 
            'recurring_days', 'comfort_features', 'gender_preference',
            'polyline', 'estimated_distance_km', 'estimated_duration_minutes',
            'route_points', 'has_stops', 'stops', 'female_only_ride'
        ]
    
    def validate_vehicle_id(self, value):
        """Validate that vehicle belongs to the current user and is active"""
        user = self.context['request'].user
        try:
            vehicle = Vehicle.objects.get(id=value, owner=user)
            
            # Check if vehicle is active
            if not vehicle.is_active:
                raise serializers.ValidationError("Vehicle is not active. Please activate your vehicle first.")
            
            # Check if vehicle is verified
            if not vehicle.is_verified:
                raise serializers.ValidationError(
                    "Vehicle must be verified before it can be used for rides. "
                    "Please submit verification documents and wait for admin approval."
                )
            
            return value
        except Vehicle.DoesNotExist:
            raise serializers.ValidationError("Vehicle not found or you don't have permission to use this vehicle")
    
    def validate_total_seats(self, value):
        """Validate that total seats doesn't exceed vehicle capacity"""
        vehicle_id = self.initial_data.get('vehicle_id')
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id)
                if value > vehicle.available_seats_for_ride:
                    raise serializers.ValidationError(
                        f"Total seats cannot exceed vehicle capacity of {vehicle.available_seats_for_ride}"
                    )
            except Vehicle.DoesNotExist:
                pass  # Will be caught by vehicle_id validation
        
        if value < 1:
            raise serializers.ValidationError("Total seats must be at least 1")
        return value

    def validate_price_per_seat(self, value):
        """Validate that price is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
        
    def validate(self, data):
        """Validate coordinate data"""
        # If any coordinates are provided, all should be provided
        pickup_lat = data.get('pickup_latitude')
        pickup_lng = data.get('pickup_longitude')
        dropoff_lat = data.get('dropoff_latitude')
        dropoff_lng = data.get('dropoff_longitude')
        
        if any([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]) and not all([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]):
            raise serializers.ValidationError("If providing coordinates, all coordinates are required")
            
        # Validate recurring ride data
        recurring = data.get('recurring')
        recurring_days = data.get('recurring_days')
        
        if recurring and not recurring_days:
            raise serializers.ValidationError("Recurring rides must specify recurring days")
            
        # Make sure pickup and dropoff locations are not the same
        if data['pickup_location'] == data['dropoff_location']:
            raise serializers.ValidationError("Pickup and dropoff locations cannot be the same")
        
        # Validate comfort_features format if provided
        comfort_features = data.get('comfort_features')
        if comfort_features:
            # Check if it's a proper JSON object
            if not isinstance(comfort_features, dict):
                raise serializers.ValidationError("Comfort features must be a valid JSON object")
                
            # Check for valid keys
            valid_keys = {'smoking_allowed', 'has_ac', 'chat_level', 'music_genres'}
            invalid_keys = set(comfort_features.keys()) - valid_keys
            
            if invalid_keys:
                raise serializers.ValidationError(f"Invalid comfort feature keys: {', '.join(invalid_keys)}")
            
            # Validate chat_level if provided
            if 'chat_level' in comfort_features:
                valid_levels = {'quiet', 'moderate', 'chatty'}
                if comfort_features['chat_level'] not in valid_levels:
                    raise serializers.ValidationError(
                        f"Invalid chat level. Must be one of: {', '.join(valid_levels)}"
                    )
                    
            # Validate music_genres if provided
            if 'music_genres' in comfort_features:
                if not isinstance(comfort_features['music_genres'], list):
                    raise serializers.ValidationError("Music genres must be a list")
                    
        # Validate stops if has_stops is True
        has_stops = data.get('has_stops', False)
        stops = data.get('stops')
        
        if has_stops and not stops:
            raise serializers.ValidationError("Stops must be provided if ride has stops")
            
        if stops:
            for i, stop in enumerate(stops):
                if not all(key in stop for key in ['location_name', 'latitude', 'longitude']):
                    raise serializers.ValidationError(f"Stop {i+1} is missing required fields")
        
        # Validate route points if provided
        route_points = data.get('route_points')
        if route_points:
            for i, point in enumerate(route_points):
                if not all(key in point for key in ['latitude', 'longitude', 'sequence']):
                    raise serializers.ValidationError(f"Route point {i+1} is missing required fields")
        
        # Validate female-only rides - only female drivers can create female-only rides
        if data.get('female_only_ride', False):
            user = self.context['request'].user
            if user.gender != 'female':
                raise serializers.ValidationError("Only female drivers can create female-only rides")
        
        return data
    
    def create(self, validated_data):
        """Create a new ride with the current user as driver"""
        user = self.context['request'].user
        
        # Extract nested data
        route_points_data = validated_data.pop('route_points', None)
        stops_data = validated_data.pop('stops', None)
        
        # Check if user has a car
        if not user.has_car:
            raise serializers.ValidationError("You must have a car to offer rides")
        
        # Create the ride with the current user as driver
        ride = Ride.objects.create(
            driver=user,
            available_seats=validated_data['total_seats'],
            **validated_data
        )
        
        # Calculate route using OpenRouteService if coordinates are provided
        if all([ride.pickup_latitude, ride.pickup_longitude, 
               ride.dropoff_latitude, ride.dropoff_longitude]):
            # Use OpenRouteService to calculate accurate distance and duration
            ride.calculate_route_with_openroute()
        
        # Create route points if provided
        if route_points_data:
            for point_data in route_points_data:
                RoutePoint.objects.create(ride=ride, **point_data)
                
        # Create stops if provided
        if stops_data:
            for stop_data in stops_data:
                scheduled_time = stop_data.pop('scheduled_time', None)
                if isinstance(scheduled_time, str):
                    try:
                        scheduled_time = timezone.datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                    except ValueError:
                        scheduled_time = None
                        
                stop_data['scheduled_time'] = scheduled_time
                RideStop.objects.create(ride=ride, **stop_data)
        
        return ride


class RideUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            'departure_time', 'pickup_location', 'dropoff_location',
            'total_seats', 'status', 'notes', 'route_description',
            'price_per_seat', 'pickup_latitude', 'pickup_longitude',
            'dropoff_latitude', 'dropoff_longitude', 'recurring',
            'recurring_days', 'time_flexibility_minutes', 'is_workplace_ride',
            'comfort_features'
        ]


class JoinRideSerializer(serializers.ModelSerializer):
    pickup_note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    class Meta:
        model = RidePassenger
        fields = ['pickup_note']
    
    def validate(self, data):
        """Validate that the user can join the ride"""
        user = self.context['request'].user
        ride = self.context['ride']
        
        # Check if ride is full
        if ride.is_full():
            raise serializers.ValidationError("This ride is full")
        
        # Check if user is already a passenger
        if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
            raise serializers.ValidationError("You already requested to join this ride")
            
        # Check if user is the driver
        if ride.driver == user:
            raise serializers.ValidationError("You are the driver of this ride")
            
        # Check gender preference restrictions and female-only rides
        if not ride.check_passenger_eligibility(user):
            # Check if it's specifically a female-only ride
            if ride.female_only_ride and user.gender != "female":
                raise serializers.ValidationError("This is a female-only ride. Only female passengers can join.")
            
            # Check other gender preferences
            gender_message = {
                "male_only": "This ride is for male passengers only",
                "female_only": "This ride is for female passengers only", 
                "family_only": "This ride is for families only"
            }.get(ride.gender_preference, "You don't meet the gender requirements for this ride")
            raise serializers.ValidationError(gender_message)
            
        return data
    
    def create(self, validated_data):
        """Create a new ride passenger for the user and the given ride"""
        user = self.context['request'].user
        ride = self.context['ride']
        
        # Create the ride passenger
        passenger = RidePassenger.objects.create(
            ride=ride,
            passenger=user,
            status='pending',
            **validated_data
        )
        
        return passenger


class RidePassengerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RidePassenger
        fields = ['ride', 'pickup_note']
        
    def validate_ride(self, ride):
        # Check if the ride is already full
        if ride.is_full():
            raise serializers.ValidationError("This ride is already full")
            
        # Check if user is already a passenger in this ride
        user = self.context['request'].user
        if RidePassenger.objects.filter(ride=ride, passenger=user).exists():
            raise serializers.ValidationError("You are already a passenger in this ride")
            
        # Check if user is the driver
        if ride.driver == user:
            raise serializers.ValidationError("You cannot join your own ride as a passenger")
            
        return ride


class RidePassengerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RidePassenger
        fields = ['status', 'pickup_note']


class RideRatingSerializer(serializers.Serializer):
    """Serializer for rating rides"""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RideDirectionSerializer(serializers.ModelSerializer):
    """Serializer for ride directions/routes"""
    
    class Meta:
        model = RideDirection
        fields = ['id', 'name', 'start_area', 'end_area', 'waypoints', 
                  'average_distance_km', 'average_duration_minutes']


class FareCalculationSerializer(serializers.ModelSerializer):
    """Serializer for fare calculation details"""
    
    class Meta:
        model = FareCalculation
        fields = ['base_fare', 'peak_hour_multiplier', 'total_fare', 
                  'fare_per_passenger', 'is_peak_hour', 'passenger_count',
                  'distance_km', 'calculated_at']


class ScheduledRideSerializer(serializers.ModelSerializer):
    """Serializer for scheduled rides"""
    
    user_name = serializers.ReadOnlyField(source='user.get_display_name')
    matched_ride_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduledRide
        fields = [
            'id', 'pickup_location', 'dropoff_location', 'pickup_latitude',
            'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'scheduled_date', 'scheduled_time', 'gender_preference',
            'is_driver', 'seats_needed', 'seats_offered', 'notes',
            'is_active', 'user_name', 'matched_ride_info', 'created_at'
        ]
        read_only_fields = ['created_at', 'user_name', 'matched_ride_info']
    
    def get_matched_ride_info(self, obj):
        if obj.matched_ride:
            return {
                'ride_id': obj.matched_ride.id,
                'driver_name': obj.matched_ride.driver.get_display_name(),
                'departure_time': obj.matched_ride.departure_time,
                'status': obj.matched_ride.status
            }
        return None
    
    def validate_scheduled_date(self, value):
        from datetime import date
        if value < date.today():
            raise serializers.ValidationError("Scheduled date cannot be in the past")
        return value


class RideReviewSerializer(serializers.ModelSerializer):
    """Serializer for ride reviews and ratings"""
    
    reviewer_name = serializers.ReadOnlyField(source='reviewer.get_display_name')
    reviewee_name = serializers.ReadOnlyField(source='reviewee.get_display_name')
    
    class Meta:
        model = RideReview
        fields = [
            'id', 'ride', 'reviewer', 'reviewee', 'review_type',
            'rating', 'comment', 'punctuality_rating', 'cleanliness_rating',
            'communication_rating', 'safety_rating', 'created_at',
            'reviewer_name', 'reviewee_name'
        ]
        read_only_fields = ['created_at', 'reviewer_name', 'reviewee_name']
    
    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def validate_punctuality_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Punctuality rating must be between 1 and 5")
        return value
    
    def validate_cleanliness_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Cleanliness rating must be between 1 and 5")
        return value
    
    def validate_communication_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Communication rating must be between 1 and 5")
        return value
    
    def validate_safety_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Safety rating must be between 1 and 5")
        return value


class EnhancedRideSerializer(RideSerializer):
    """Enhanced ride serializer with all new features"""
    
    driver_info = serializers.SerializerMethodField()
    fare_details = FareCalculationSerializer(source='fare_details', read_only=True)
    direction_info = RideDirectionSerializer(source='ride_direction', read_only=True)
    passenger_view_info = serializers.SerializerMethodField()
    dashboard_info = serializers.SerializerMethodField()
    
    class Meta(RideSerializer.Meta):
        fields = RideSerializer.Meta.fields + [
            'calculated_fare', 'ride_direction', 'female_only_ride',
            'driver_destination', 'started_at', 'auto_fare_calculated',
            'driver_info', 'fare_details', 'direction_info',
            'passenger_view_info', 'dashboard_info'
        ]
    
    def get_driver_info(self, obj):
        return {
            'name': obj.driver.get_display_name(),
            'rating': float(obj.driver.driver_rating),
            'total_rides': obj.driver.total_rides_offered,
            'car_info': {
                'model': obj.driver.car_model,
                'color': obj.driver.car_color,
                'license_plate': obj.driver.car_license_plate
            } if obj.driver.car_model else None
        }
    
    def get_passenger_view_info(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Only provide passenger view for non-drivers
            if request.user != obj.driver:
                return obj.get_passenger_view_info()
        return None
    
    def get_dashboard_info(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Only provide dashboard info for the driver
            if request.user == obj.driver:
                return obj.get_dashboard_info()
        return None


class RideRequestSerializer(serializers.ModelSerializer):
    """Serializer for ride requests from passengers"""
    passenger = UserSerializer(read_only=True)
    ride_info = serializers.SerializerMethodField()
    estimated_fare_display = serializers.SerializerMethodField()
    estimated_distance_km = serializers.SerializerMethodField()
    
    class Meta:
        model = RideRequest
        fields = [
            'id', 'ride', 'passenger', 'pickup_location', 'dropoff_location',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'status', 'message', 'seats_requested', 'estimated_distance_km',
            'estimated_fare', 'estimated_fare_display', 'driver_response', 
            'responded_at', 'created_at', 'ride_info'
        ]
        read_only_fields = ['passenger', 'estimated_fare', 'responded_at', 'status']
    
    def get_ride_info(self, obj):
        """Return basic ride information"""
        return {
            'departure_time': obj.ride.departure_time,
            'pickup_location': obj.ride.pickup_location,
            'dropoff_location': obj.ride.dropoff_location,
            'driver_name': obj.ride.driver.get_display_name(),
            'vehicle_info': f"{obj.ride.vehicle.make} {obj.ride.vehicle.model}"
        }
    
    def get_estimated_fare_display(self, obj):
        """Return formatted fare display"""
        return f"Rs. {obj.estimated_fare}"
    
    def get_estimated_distance_km(self, obj):
        """Format estimated distance to 2 decimal places"""
        try:
            return round(float(obj.estimated_distance_km), 2) if obj.estimated_distance_km else 0.0
        except (ValueError, TypeError):
            return 0.0


class RideRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ride requests"""
    
    class Meta:
        model = RideRequest
        fields = [
            'ride', 'pickup_location', 'dropoff_location',
            'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude',
            'message', 'seats_requested'
        ]
    
    def validate_ride(self, value):
        """Validate ride availability"""
        if value.status != 'scheduled':
            raise serializers.ValidationError("Can only request to join scheduled rides")
        
        if value.available_seats < 1:
            raise serializers.ValidationError("No seats available in this ride")
        
        return value
    
    def validate(self, data):
        """Additional validation"""
        user = self.context['request'].user
        ride = data['ride']
        
        # Check if user is the driver
        if ride.driver == user:
            raise serializers.ValidationError("Driver cannot request to join their own ride")
        
        # Check if user already has a request for this ride
        if RideRequest.objects.filter(ride=ride, passenger=user).exists():
            raise serializers.ValidationError("You already have a request for this ride")
        
        # Check gender restrictions
        if ride.female_only_ride and not user.can_join_female_only_ride():
            raise serializers.ValidationError("This is a female-only ride")
        
        return data


class DriverDashboardSerializer(serializers.Serializer):
    """Serializer for driver dashboard data"""
    upcoming_rides = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField()
    ride_statistics = serializers.SerializerMethodField()
    
    def get_upcoming_rides(self, driver):
        """Get upcoming rides with passenger details"""
        dashboard_data = DriverDashboard.get_upcoming_rides(driver)
        result = []
        
        for ride_info in dashboard_data:
            ride = ride_info['ride']
            passengers = ride_info['passengers']
            
            ride_data = {
                'id': ride.id,
                'departure_time': ride.departure_time,
                'pickup_location': ride.pickup_location,
                'dropoff_location': ride.dropoff_location,
                'vehicle': f"{ride.vehicle.make} {ride.vehicle.model}",
                'seats_left': ride_info['seats_left'],
                'can_start': ride_info['can_start'],
                'pending_requests_count': ride_info['pending_requests'],
                'passengers': [
                    {
                        'name': p.passenger.get_display_name(),
                        'pickup': p.passenger_pickup_location,
                        'dropoff': p.passenger_dropoff_location,
                        'fare': f"Rs. {p.individual_fare}",
                        'gender': p.passenger.gender
                    } for p in passengers
                ]
            }
            result.append(ride_data)
        
        return result
    
    def get_pending_requests(self, driver):
        """Get pending ride requests"""
        requests = DriverDashboard.get_ride_requests(driver)
        return RideRequestSerializer(requests, many=True).data
    
    def get_ride_statistics(self, driver):
        """Get driver statistics"""
        return {
            'total_rides_offered': driver.total_rides_offered,
            'driver_rating': float(driver.driver_rating),
            'total_reviews': driver.total_driver_reviews,
            'active_vehicles': driver.vehicles.filter(is_active=True).count()
        }


class PassengerRideSearchSerializer(serializers.Serializer):
    """Serializer for passenger ride search"""
    pickup_location = serializers.CharField(max_length=255)
    dropoff_location = serializers.CharField(max_length=255)
    pickup_latitude = serializers.FloatField()
    pickup_longitude = serializers.FloatField()
    dropoff_latitude = serializers.FloatField()
    dropoff_longitude = serializers.FloatField()
    departure_time = serializers.DateTimeField()
    female_only = serializers.BooleanField(default=False)


class PassengerRideResultSerializer(serializers.Serializer):
    """Serializer for passenger ride search results"""
    ride = RideSerializer()
    driver = UserSerializer()
    vehicle = VehicleListSerializer()
    distance_km = serializers.FloatField()
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_fare_display = serializers.SerializerMethodField()
    is_peak_hour = serializers.BooleanField()
    driver_rating = serializers.SerializerMethodField()
    vehicle_display = serializers.SerializerMethodField()
    
    def get_estimated_fare_display(self, obj):
        return f"Rs. {obj['estimated_fare']}"

    def get_driver_rating(self, obj):
        """Get driver rating as float"""
        try:
            return float(obj.driver.driver_rating) if obj.driver.driver_rating else 0.0
        except (AttributeError, TypeError, ValueError):
            return 0.0
    
    def get_vehicle_display(self, obj):
        vehicle = obj['vehicle']
        return f"{vehicle.make} {vehicle.model} ({vehicle.color})"


class RidePassengerDetailSerializer(serializers.ModelSerializer):
    """Enhanced serializer for ride passenger with fare details"""
    passenger = UserSerializer(read_only=True)
    fare_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = RidePassenger
        fields = [
            'id', 'ride', 'passenger', 'joined_at', 'status', 'pickup_note',
            'passenger_pickup_location', 'passenger_dropoff_location',
            'passenger_distance_km', 'individual_fare', 'fare_calculated_at',
            'relationship', 'contribution_amount', 'has_contributed',
            'fare_breakdown'
        ]
    
    def get_fare_breakdown(self, obj):
        """Get detailed fare breakdown"""
        if obj.individual_fare > 0:
            return {
                'base_amount': float(obj.individual_fare),
                'distance_km': obj.passenger_distance_km,
                'rate_per_km': 30.00,  # Could be dynamic based on time
                'formatted_amount': f"Rs. {obj.individual_fare}"
            }
        return None


class VehicleVerificationSerializer(serializers.ModelSerializer):
    """Serializer for vehicle verification process"""
    verification_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'make', 'model', 'year', 'color', 'license_plate',
            'verification_status', 'verification_submitted_at', 
            'verification_approved_at', 'verification_documents'
        ]
        read_only_fields = ['verification_status', 'verification_submitted_at', 'verification_approved_at']
    
    def get_verification_documents(self, obj):
        """Return verification document status"""
        return {
            'registration_book_uploaded': bool(obj.car_registration_book_image),
            'car_image_uploaded': bool(obj.car_image)
        }


class AvailableVehicleSerializer(serializers.ModelSerializer):
    """Serializer for vehicles available for ride creation"""
    verification_status_display = serializers.SerializerMethodField()
    can_use_for_rides = serializers.SerializerMethodField()
    vehicle_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'make', 'model', 'year', 'color', 'license_plate',
            'vehicle_type', 'total_seats', 'available_seats_for_ride',
            'is_verified', 'is_active', 'verification_status_display',
            'can_use_for_rides', 'vehicle_display'
        ]
    
    def get_verification_status_display(self, obj):
        """Get human-readable verification status"""
        if obj.is_verified:
            return "Verified ✓"
        elif obj.verification_status == 'pending':
            return "Verification Pending"
        elif obj.verification_status == 'under_review':
            return "Under Review"
        elif obj.verification_status == 'rejected':
            return "Verification Rejected"
        else:
            return "Not Verified"
    
    def get_can_use_for_rides(self, obj):
        """Check if vehicle can be used for rides"""
        return obj.is_active and obj.is_verified
    
    def get_vehicle_display(self, obj):
        """Get formatted vehicle display string"""
        return f"{obj.year} {obj.make} {obj.model} ({obj.color})"


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.ReadOnlyField(source='reviewer.get_full_name')
    reviewee_name = serializers.ReadOnlyField(source='reviewee.get_full_name')
    reviewer_picture = serializers.SerializerMethodField()
    reviewee_picture = serializers.SerializerMethodField()
    ride_route = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'ride', 'reviewer', 'reviewee', 'reviewer_type',
            'overall_rating', 'punctuality_rating', 'communication_rating', 'behavior_rating',
            'comment', 'would_ride_again', 'created_at', 'created_at_formatted',
            'reviewer_name', 'reviewee_name', 'reviewer_picture', 'reviewee_picture',
            'ride_route'
        ]
        read_only_fields = ['created_at', 'reviewer']
    
    def get_reviewer_picture(self, obj):
        if obj.reviewer.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.reviewer.profile_picture.url)
        return None
    
    def get_reviewee_picture(self, obj):
        if obj.reviewee.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.reviewee.profile_picture.url)
        return None
    
    def get_ride_route(self, obj):
        return f"{obj.ride.pickup_location} → {obj.ride.dropoff_location}"
    
    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime("%B %d, %Y")
    
    def validate(self, data):
        # Additional validation
        if data.get('overall_rating') and (data['overall_rating'] < 1 or data['overall_rating'] > 5):
            raise serializers.ValidationError("Overall rating must be between 1 and 5")
        return data


class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            'ride', 'reviewee', 'reviewer_type', 'overall_rating',
            'punctuality_rating', 'communication_rating', 'behavior_rating',
            'comment', 'would_ride_again'
        ]
    
    def create(self, validated_data):
        # Set the reviewer to the current user
        validated_data['reviewer'] = self.context['request'].user
        return super().create(validated_data)


class UserReviewSummarySerializer(serializers.Serializer):
    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()
    five_star_count = serializers.IntegerField()
    four_star_count = serializers.IntegerField()
    three_star_count = serializers.IntegerField()
    two_star_count = serializers.IntegerField()
    one_star_count = serializers.IntegerField()
    recent_reviews = ReviewSerializer(many=True)