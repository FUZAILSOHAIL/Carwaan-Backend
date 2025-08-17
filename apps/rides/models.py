from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel
from apps.users.models import User
from django.conf import settings
import math
import logging
from django.utils import timezone
from decimal import Decimal
import pytz
from datetime import datetime, time, timedelta
from .route_service import OpenRouteServiceProvider

logger = logging.getLogger(__name__)


class Location(models.Model):
    """Model for common locations like universities, workplaces, and landmarks"""

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    is_workplace = models.BooleanField(default=False)
    is_landmark = models.BooleanField(default=False)
    is_university = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class RoutePoint(models.Model):
    """Model to store route waypoints for detailed route display on map"""
    
    latitude = models.FloatField()
    longitude = models.FloatField()
    sequence = models.IntegerField(help_text="Order of the point in the route")
    ride = models.ForeignKey('Ride', on_delete=models.CASCADE, related_name='route_points')
    
    class Meta:
        ordering = ['sequence']
    
    def __str__(self):
        return f"Point {self.sequence} for ride {self.ride_id}"


class Ride(TimeStampedModel):
    """Model for carpooling rides among colleagues and friends"""

    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    RIDE_TYPE_CHOICES = (
        ("commute", "Work Commute"),
        ("event", "Event/Meeting"),
        ("social", "Social Gathering"),
        ("errand", "Errand Run"),
        ("other", "Other"),
    )
    
    GENDER_PREFERENCE_CHOICES = (
        ("any", "Any gender welcome"),
        ("male_only", "Male passengers only"),
        ("female_only", "Female passengers only"),
        ("family_only", "Families only"),
    )

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offered_rides"
    )
    
    # Vehicle used for this ride (required for new flow)
    vehicle = models.ForeignKey(
        'users.Vehicle', 
        on_delete=models.CASCADE, 
        related_name='rides',
        null=True,
        blank=True,
        help_text="Vehicle being used for this ride"
    )
    
    departure_time = models.DateTimeField(default=timezone.now)
    return_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Return time for round trips"
    )
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    total_seats = models.PositiveIntegerField(default=2)
    available_seats = models.PositiveIntegerField(default=1)
    
    # Enhanced gender preferences
    gender_preference = models.CharField(
        max_length=20, 
        choices=GENDER_PREFERENCE_CHOICES, 
        default="any",
        help_text="Gender preference for passengers"
    )
    is_female_only = models.BooleanField(
        default=False,
        help_text="Female-only ride (only available for female drivers)"
    )
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    notes = models.TextField(blank=True)
    
    # Recurring ride options
    is_recurring = models.BooleanField(
        default=False,
        help_text="Whether this is a recurring ride"
    )
    recurring_days = models.JSONField(
        null=True,
        blank=True,
        help_text="Days of week for recurring rides (0=Monday, 6=Sunday)"
    )
    recurring_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date for recurring rides"
    )
    
    # Route information
    polyline = models.TextField(
        blank=True, 
        help_text="Encoded polyline representation of the route"
    )
    estimated_distance_km = models.FloatField(default=0.0)
    estimated_duration_minutes = models.IntegerField(default=0)
    
    # Route calculation method and preferences
    route_calculation_method = models.CharField(
        max_length=50,
        default='haversine',
        help_text="Method used to calculate route: 'haversine', 'openrouteservice', 'google_maps', etc."
    )
    route_preference = models.CharField(
        max_length=20,
        choices=[
            ('fastest', 'Fastest Route'),
            ('shortest', 'Shortest Route'),
            ('balanced', 'Balanced Route'),
        ],
        default='fastest',
        help_text="Route preference selected by driver"
    )
    route_alternatives = models.JSONField(
        null=True,
        blank=True,
        help_text="Alternative route options with distances and durations"
    )

    # Enhanced fields for colleague/friend carpooling
    ride_type = models.CharField(
        max_length=20, choices=RIDE_TYPE_CHOICES, default="commute"
    )
    route_description = models.TextField(
        blank=True, help_text="Description of route, landmarks, etc."
    )
    price_per_seat = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    cost_splitting = models.BooleanField(
        default=True, help_text="Whether to split costs among passengers"
    )
    
    # New fare and direction features
    calculated_fare = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Auto-calculated fare based on distance and time"
    )
    
    ride_direction = models.ForeignKey(
        'RideDirection', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Common route/direction for this ride"
    )
    
    # Enhanced gender preferences for safety
    female_only_ride = models.BooleanField(
        default=False,
        help_text="True if this is a female-only ride (driver and passengers)"
    )
    
    # Driver destination visibility
    driver_destination = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Where the driver is ultimately going (for passenger info)"
    )
    
    # Ride started timestamp
    started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the ride actually started"
    )
    
    # Auto-calculated at ride start
    auto_fare_calculated = models.BooleanField(
        default=False,
        help_text="Whether fare was auto-calculated when ride started"
    )

    # Social aspects for colleague/friend carpooling
    is_private = models.BooleanField(
        default=False, help_text="If true, only visible to connections/colleagues"
    )
    friend_group = models.CharField(
        max_length=100, blank=True, help_text="Specific friend group for this ride"
    )
    workplace_department = models.CharField(
        max_length=100, blank=True, help_text="Specific department for workplace rides"
    )

    # Coordinates for calculating distance
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    dropoff_latitude = models.FloatField(null=True, blank=True)
    dropoff_longitude = models.FloatField(null=True, blank=True)
    
    # Intermediate stops
    has_stops = models.BooleanField(default=False)

    # Ride preferences
    recurring = models.BooleanField(
        default=False, help_text="Is this a recurring ride?"
    )
    recurring_days = models.JSONField(
        null=True,
        blank=True,
        help_text="Days on which this ride recurs [0-6] where 0 is Monday",
    )

    time_flexibility_minutes = models.PositiveIntegerField(
        default=10, help_text="Flexibility in departure time (minutes)"
    )

    is_workplace_ride = models.BooleanField(
        default=False, help_text="Is this ride to/from a workplace?"
    )

    # Comfort features
    comfort_features = models.JSONField(
        null=True, blank=True, help_text="Features like AC, music, smoking policy, etc."
    )

    # Rating
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.PositiveIntegerField(default=0)
    
    # Passenger statistics by gender for display
    current_male_passengers = models.PositiveIntegerField(default=0)
    current_female_passengers = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Ride from {self.pickup_location} to {self.dropoff_location} at {self.departure_time}"

    def clean(self):
        """Validate ride data"""
        # Validate that driver is verified
        if not self.driver.is_verified_driver():
            raise ValidationError("Only verified drivers can create rides")
        
        # Validate that driver owns the vehicle
        if self.vehicle and self.vehicle.owner != self.driver:
            raise ValidationError("Driver can only use their own verified vehicles")
        
        # Validate that vehicle is verified and active
        if self.vehicle and not self.vehicle.is_verified:
            raise ValidationError("Vehicle must be verified to be used for rides")
        
        if self.vehicle and not self.vehicle.is_active:
            raise ValidationError("Vehicle must be active to be used for rides")
        
        # Validate female-only rides
        if self.female_only_ride and self.driver.gender != 'female':
            raise ValidationError("Only female drivers can create female-only rides")
        
        # Validate available seats don't exceed vehicle capacity
        if self.vehicle and self.available_seats > self.vehicle.available_seats_for_ride:
            raise ValidationError(f"Available seats cannot exceed vehicle capacity ({self.vehicle.available_seats_for_ride})")
        
        # Validate departure time is in the future for new rides
        if not self.pk and self.departure_time <= timezone.now():
            raise ValidationError("Departure time must be in the future")
        
        # Validate that pickup and dropoff locations are different
        if (self.pickup_latitude and self.dropoff_latitude and 
            self.pickup_longitude and self.dropoff_longitude):
            if (abs(self.pickup_latitude - self.dropoff_latitude) < 0.0001 and 
                abs(self.pickup_longitude - self.dropoff_longitude) < 0.0001):
                raise ValidationError("Pickup and drop-off locations cannot be the same")
        
        # Also check if pickup and dropoff location names are identical
        if (self.pickup_location and self.dropoff_location and 
            self.pickup_location.strip().lower() == self.dropoff_location.strip().lower()):
            raise ValidationError("Pickup and drop-off locations cannot be the same")
        
        super().clean()
    
    def save(self, *args, **kwargs):
        """Override save to set defaults from vehicle"""
        if self.vehicle and not self.pk:  # Only on creation
            # Set total seats from vehicle if not specified
            if not self.total_seats:
                self.total_seats = self.vehicle.available_seats_for_ride
            
            # Set available seats
            if not self.available_seats:
                self.available_seats = self.total_seats
        
        self.full_clean()  # Run validation
        super().save(*args, **kwargs)
    
    @classmethod
    def create_ride(cls, driver, vehicle, **kwargs):
        """Create a new ride with validation and route calculation"""
        from .route_service import calculate_route_distance
        
        # Create the ride instance
        ride = cls(
            driver=driver,
            vehicle=vehicle,
            **kwargs
        )
        
        # Set total_seats from vehicle if not provided
        if not kwargs.get('total_seats'):
            ride.total_seats = vehicle.available_seats_for_ride
        
        # Set available_seats if not provided
        if not kwargs.get('available_seats'):
            ride.available_seats = ride.total_seats
        
        # Calculate route information if coordinates are provided
        if (ride.pickup_latitude and ride.pickup_longitude and 
            ride.dropoff_latitude and ride.dropoff_longitude):
            
            try:
                route_preference = kwargs.get('route_preference', 'fastest')
                route_info = calculate_route_distance(
                    ride.pickup_latitude, 
                    ride.pickup_longitude,
                    ride.dropoff_latitude, 
                    ride.dropoff_longitude,
                    preference=route_preference
                )
                
                # Update ride with route information
                ride.estimated_distance_km = route_info['distance_km']
                ride.estimated_duration_minutes = int(route_info['duration_minutes'])
                ride.polyline = route_info.get('polyline', '')
                ride.route_calculation_method = route_info['provider']
                ride.route_preference = route_preference
                
                # Calculate and set fare based on route distance
                if ride.estimated_distance_km > 0:
                    fare_details = FareCalculator.calculate_individual_fare(
                        ride.estimated_distance_km,
                        ride.departure_time
                    )
                    ride.calculated_fare = fare_details['fare_amount']
                
                # Store route alternatives if available
                try:
                    from .route_service import get_route_alternatives
                    alternatives = get_route_alternatives(
                        ride.pickup_latitude, 
                        ride.pickup_longitude,
                        ride.dropoff_latitude, 
                        ride.dropoff_longitude
                    )
                    ride.route_alternatives = alternatives
                except Exception as e:
                    print(f"Failed to get route alternatives: {e}")
                    
            except Exception as e:
                print(f"Route calculation failed, using fallback: {e}")
                # Fallback to Haversine calculation
                distance_km = ride.calculate_distance(
                    ride.pickup_latitude, ride.pickup_longitude,
                    ride.dropoff_latitude, ride.dropoff_longitude
                )
                ride.estimated_distance_km = distance_km
                ride.estimated_duration_minutes = int(distance_km * 2)  # Rough estimate
                ride.route_calculation_method = 'haversine_fallback'
        
        # Validate and save
        ride.full_clean()
        ride.save()
        
        # Create route points if provided
        route_points = kwargs.get('route_points', [])
        if route_points:
            for i, point in enumerate(route_points):
                RoutePoint.objects.create(
                    ride=ride,
                    latitude=point.get('lat', point.get('latitude', 0)),
                    longitude=point.get('lng', point.get('longitude', 0)),
                    sequence=i
                )
        
        # Create stops if provided
        stops = kwargs.get('stops', [])
        if stops and kwargs.get('has_stops', False):
            for i, stop in enumerate(stops):
                RideStop.objects.create(
                    ride=ride,
                    location=stop.get('location', ''),
                    latitude=stop.get('lat', stop.get('latitude', 0)),
                    longitude=stop.get('lng', stop.get('longitude', 0)),
                    sequence=i
                )
        
        return ride

    def can_passenger_join(self, passenger):
        """Check if passenger can join this ride"""
        # Check gender restrictions
        if self.female_only_ride and passenger.gender != 'female':
            return False, "This is a female-only ride"
        
        # Check seat availability
        if self.available_seats <= 0:
            return False, "No seats available"
        
        # Check if passenger already joined
        if self.passengers.filter(passenger=passenger, status__in=['pending', 'confirmed']).exists():
            return False, "You have already requested to join this ride"
        
        return True, "Can join ride"
    
    def get_driver_display_info(self):
        """Get driver info for passenger view"""
        return {
            'name': self.driver.get_display_name(),
            'gender': self.driver.get_gender_display(),
            'rating': float(self.driver.driver_rating),
            'total_reviews': self.driver.total_driver_reviews,
            'is_verified': self.driver.is_verified_driver(),
            'profile_picture': self.driver.profile_picture.url if self.driver.profile_picture else None,
        }
    
    def get_vehicle_display_info(self):
        """Get vehicle info for passenger view"""
        if not self.vehicle:
            return None
        
        return {
            'make_model': f"{self.vehicle.make} {self.vehicle.model}",
            'year': self.vehicle.year,
            'color': self.vehicle.color,
            'license_plate': self.vehicle.license_plate,
            'has_ac': self.vehicle.has_ac,
            'ac_type': self.vehicle.get_ac_type_display(),
            'total_seats': self.vehicle.total_seats,
            'image': self.vehicle.car_image.url if self.vehicle.car_image else None,
        }

    def is_full(self):
        """Check if the ride is full"""
        return self.available_seats <= 0

    def update_available_seats(self):
        """Update the available seats based on confirmed passengers"""
        confirmed_passengers = RidePassenger.objects.filter(
            ride=self, status="confirmed"
        )
        
        confirmed_passengers_count = confirmed_passengers.count()
        self.available_seats = max(0, self.total_seats - confirmed_passengers_count)
        
        # Update gender statistics - safely handle missing gender field
        try:
            male_count = confirmed_passengers.filter(passenger__gender="male").count()
            female_count = confirmed_passengers.filter(passenger__gender="female").count()
            
            self.current_male_passengers = male_count
            self.current_female_passengers = female_count
        except Exception:
            # If gender field doesn't exist or another error occurs, set default values
            self.current_male_passengers = 0
            self.current_female_passengers = 0
        
        self.save()

    def update_rating(self, new_rating):
        """Update average rating with a new rating (1-5)"""
        if new_rating < 1 or new_rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        if self.total_ratings == 0:
            self.average_rating = new_rating
        else:
            total = self.average_rating * self.total_ratings
            self.average_rating = (total + new_rating) / (self.total_ratings + 1)

        self.total_ratings += 1
        self.save()

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        # Earth radius in kilometers
        R = 6371.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance
    
    def calculate_route_with_openroute(self):
        """Calculate route distance and duration using OpenRouteService"""
        if not all([self.pickup_latitude, self.pickup_longitude, 
                   self.dropoff_latitude, self.dropoff_longitude]):
            return False
            
        try:
            route_data = OpenRouteServiceProvider.get_distance_and_duration(
                self.pickup_latitude,
                self.pickup_longitude,
                self.dropoff_latitude,
                self.dropoff_longitude
            )
            
            if route_data['success']:
                self.estimated_distance_km = route_data['distance_km']
                self.estimated_duration_minutes = route_data['duration_minutes']
                if route_data['polyline']:
                    self.polyline = route_data['polyline']
                self.save()
                return True
            else:
                # Fallback to Haversine calculation
                distance = self.calculate_distance(
                    self.pickup_latitude, self.pickup_longitude,
                    self.dropoff_latitude, self.dropoff_longitude
                )
                self.estimated_distance_km = round(distance, 2)
                self.estimated_duration_minutes = round((distance / 40) * 60)  # Assume 40 km/h
                self.save()
                return False
                
        except Exception as e:
            # Fallback to Haversine calculation
            distance = self.calculate_distance(
                self.pickup_latitude, self.pickup_longitude,
                self.dropoff_latitude, self.dropoff_longitude
            )
            self.estimated_distance_km = round(distance, 2)
            self.estimated_duration_minutes = round((distance / 40) * 60)
            self.save()
            return False
    
    def get_passenger_details(self):
        """Get detailed information about current passengers"""
        passengers = self.ridepassenger_set.filter(status='confirmed').select_related('passenger')
        
        passenger_info = []
        for rp in passengers:
            passenger_info.append({
                'id': rp.passenger.id,
                'name': rp.passenger.get_display_name(),
                'gender': rp.passenger.gender,
                'rating': float(rp.passenger.passenger_rating) if rp.passenger.passenger_rating else 0.0,
                'profile_picture': rp.passenger.profile_picture.url if rp.passenger.profile_picture else None,
                'joined_at': rp.joined_at,
                'pickup_note': rp.pickup_note or ''
            })
        
        return {
            'total_passengers': len(passenger_info),
            'available_seats': self.available_seats,
            'passengers': passenger_info,
            'gender_breakdown': {
                'male': len([p for p in passenger_info if p['gender'] == 'male']),
                'female': len([p for p in passenger_info if p['gender'] == 'female']),
                'other': len([p for p in passenger_info if p['gender'] not in ['male', 'female']])
            }
        }
        
    def check_passenger_eligibility(self, passenger):
        """Check if a passenger is eligible to join based on gender preferences"""
        # Check female-only ride restriction first
        if self.female_only_ride and passenger.gender != "female":
            return False
            
        if self.gender_preference == "any":
            return True
        
        try:
            if self.gender_preference == "male_only" and passenger.gender == "male":
                return True
            elif self.gender_preference == "female_only" and passenger.gender == "female":
                return True
            # For family_only, we'll consider this in the request process with additional fields
            return False
        except AttributeError:
            # If there's an issue accessing the gender attribute, default to allowing the passenger
            return True

    def match_score(self, user, user_lat, user_lng, user_dest_lat, user_dest_lng):
        """Calculate a match score for a user and this ride based on multiple factors"""
        score = 0.0

        # Base score starts at 50
        score = 50.0

        # 1. Distance matching (contributes up to 40 points)
        if (
            self.pickup_latitude
            and self.pickup_longitude
            and self.dropoff_latitude
            and self.dropoff_longitude
        ):
            # Calculate pickup distance (10km or less is ideal)
            pickup_distance = self.calculate_distance(
                user_lat, user_lng, self.pickup_latitude, self.pickup_longitude
            )
            # Calculate dropoff distance (10km or less is ideal)
            dropoff_distance = self.calculate_distance(
                user_dest_lat,
                user_dest_lng,
                self.dropoff_latitude,
                self.dropoff_longitude,
            )

            # Score based on pickup distance (closer is better)
            if pickup_distance <= 1:  # Within 1km
                score += 20
            elif pickup_distance <= 3:  # Within 3km
                score += 15
            elif pickup_distance <= 5:  # Within 5km
                score += 10
            elif pickup_distance <= 10:  # Within 10km
                score += 5

            # Score based on dropoff distance (closer is better)
            if dropoff_distance <= 1:  # Within 1km
                score += 20
            elif dropoff_distance <= 3:  # Within 3km
                score += 15
            elif dropoff_distance <= 5:  # Within 5km
                score += 10
            elif dropoff_distance <= 10:  # Within 10km
                score += 5

        # 2. Time matching (contributes up to 20 points)
        if (
            hasattr(user, "preferred_departure_times")
            and user.preferred_departure_times
        ):
            # Convert ride departure time to HH:MM format
            ride_hour = self.departure_time.hour
            ride_minute = self.departure_time.minute

            # Check if ride time is within user's preferred times
            for time_range in user.preferred_departure_times:
                try:
                    # Parse time range as "HH:MM-HH:MM"
                    start_time, end_time = time_range.split("-")
                    start_hour, start_minute = map(int, start_time.split(":"))
                    end_hour, end_minute = map(int, end_time.split(":"))

                    # Convert to minutes for easier comparison
                    ride_time_minutes = ride_hour * 60 + ride_minute
                    start_time_minutes = start_hour * 60 + start_minute
                    end_time_minutes = end_hour * 60 + end_minute

                    # Check if ride time is within this preferred range
                    if start_time_minutes <= ride_time_minutes <= end_time_minutes:
                        score += 20
                        break
                except (ValueError, IndexError):
                    continue

        # 3. User rating matching (contributes up to 10 points)
        # Higher ratings are better matches
        if self.driver.driver_rating > 0:
            driver_rating = float(self.driver.driver_rating)
            score += min(10, driver_rating * 2)  # Up to 10 points for a 5-star driver

        # 4. Preferences matching (contributes up to 20 points)
        preference_score = 0

        # Check comfort features
        if (
            self.comfort_features
            and hasattr(user, "smoking_preference")
            and hasattr(user, "ac_preference")
            and hasattr(user, "chat_preference")
        ):
            # Smoking preference
            if user.smoking_preference != "no_preference":
                if (
                    user.smoking_preference == "no_smoking"
                    and self.comfort_features.get("smoking_allowed", False) == False
                ):
                    preference_score += 5
                elif (
                    user.smoking_preference == "smoking_allowed"
                    and self.comfort_features.get("smoking_allowed", False) == True
                ):
                    preference_score += 5
            else:
                preference_score += 3

            # AC preference
            if user.ac_preference != "no_preference":
                if (
                    user.ac_preference == "ac_required"
                    and self.comfort_features.get("has_ac", False) == True
                ):
                    preference_score += 5
                elif (
                    user.ac_preference == "no_ac"
                    and self.comfort_features.get("has_ac", False) == False
                ):
                    preference_score += 5
            else:
                preference_score += 3

            # Chat preference
            if user.chat_preference != "no_preference":
                if user.chat_preference == "chatty" and self.comfort_features.get(
                    "chat_level", "moderate"
                ) in ["chatty", "moderate"]:
                    preference_score += 5
                elif user.chat_preference == "quiet" and self.comfort_features.get(
                    "chat_level", "moderate"
                ) in ["quiet", "moderate"]:
                    preference_score += 5
            else:
                preference_score += 3

            # Music preference
            if (
                hasattr(user, "preferred_music")
                and user.preferred_music
                and "music_genres" in self.comfort_features
            ):
                ride_genres = self.comfort_features.get("music_genres", [])
                user_genres = user.preferred_music

                # Check for overlap in music preferences
                if set(user_genres) & set(ride_genres):
                    preference_score += 5

        # Add preference score to total (max 20)
        score += min(20, preference_score)

        # 5. Additional bonuses for special cases (up to 10 bonus points)

        # Bonus for workplace rides if user has workplace set
        if self.is_workplace_ride and hasattr(user, "workplace") and user.workplace:
            if (
                user.workplace.lower() in self.pickup_location.lower()
                or user.workplace.lower() in self.dropoff_location.lower()
            ):
                score += 5

        # Bonus for colleague rides (driver from same workplace)
        if (
            hasattr(user, "workplace")
            and user.workplace
            and hasattr(self.driver, "workplace")
            and self.driver.workplace
        ):
            if user.workplace.lower() == self.driver.workplace.lower():
                score += 5

        # Bonus for recurring rides that match user's preferred days
        if (
            self.recurring
            and self.recurring_days
            and hasattr(user, "preferred_days")
            and user.preferred_days
        ):
            # Convert to sets for intersection
            ride_days = set(self.recurring_days)
            user_days = set(user.preferred_days)

            # Check overlap
            if ride_days & user_days:
                score += len(ride_days & user_days)  # 1 point per matching day

        # Cap the score at 100
        return min(100, score)

    def start_ride(self):
        """Mark ride as started and calculate individual fare for each passenger"""
        if self.status != 'scheduled':
            raise ValueError("Can only start scheduled rides")
        
        self.status = 'in_progress'
        self.started_at = timezone.now()
        
        # Calculate individual fare for each confirmed passenger
        if not self.auto_fare_calculated:
            confirmed_passengers = RidePassenger.objects.filter(
                ride=self, status="confirmed"
            )
            
            for passenger_obj in confirmed_passengers:
                # Calculate individual fare based on passenger's specific distance
                if passenger_obj.passenger_distance_km > 0:
                    fare_details = FareCalculator.calculate_individual_fare(
                        passenger_distance_km=passenger_obj.passenger_distance_km,
                        departure_time=self.departure_time
                    )
                    
                    passenger_obj.individual_fare = fare_details['fare_amount']
                    passenger_obj.fare_calculated_at = timezone.now()
                    passenger_obj.save()
            
            self.auto_fare_calculated = True
        
        self.save()
        return self
    
    def get_dashboard_info(self):
        """Get comprehensive dashboard information for drivers"""
        confirmed_passengers = RidePassenger.objects.filter(
            ride=self, status="confirmed"
        ).select_related('passenger')
        
        passenger_info = []
        for rp in confirmed_passengers:
            passenger_info.append({
                'name': rp.passenger.get_full_name(),
                'gender': getattr(rp.passenger, 'gender', 'not_specified'),
                'phone': getattr(rp.passenger, 'phone', None),
                'pickup_location': getattr(rp, 'pickup_location', self.pickup_location)
            })
        
        return {
            'total_passengers': len(passenger_info),
            'available_seats': self.available_seats,
            'driver_destination': self.driver_destination or self.dropoff_location,
            'passengers': passenger_info,
            'male_passengers': self.current_male_passengers,
            'female_passengers': self.current_female_passengers,
            'calculated_fare': float(self.calculated_fare) if self.calculated_fare else 0,
            'is_started': self.status == 'in_progress',
            'direction': self.ride_direction.name if self.ride_direction else None
        }
    
    def get_passenger_view_info(self):
        """Get information visible to passengers when requesting rides"""
        return {
            'driver_name': self.driver.get_full_name(),
            'driver_destination': self.driver_destination or self.dropoff_location,
            'current_passengers': self.total_seats - self.available_seats,
            'available_seats': self.available_seats,
            'total_seats': self.total_seats,
            'male_passengers': self.current_male_passengers,
            'female_passengers': self.current_female_passengers,
            'calculated_fare': float(self.calculated_fare) if self.calculated_fare else 0,
            'gender_preference': self.get_gender_preference_display(),
            'is_female_only': self.female_only_ride,
            'estimated_distance': self.estimated_distance_km,
            'estimated_duration': self.estimated_duration_minutes,
            'direction': self.ride_direction.name if self.ride_direction else None
        }
    
    def check_direction_compatibility(self, passenger_pickup_lat, passenger_pickup_lng, 
                                    passenger_dest_lat, passenger_dest_lng):
        """Check if passenger's route is compatible with driver's direction"""
        if not all([self.pickup_latitude, self.pickup_longitude, 
                   self.dropoff_latitude, self.dropoff_longitude]):
            return True  # Can't check, so allow
        
        # Calculate if passenger's pickup is roughly on the way
        driver_total_distance = self.calculate_distance(
            self.pickup_latitude, self.pickup_longitude,
            self.dropoff_latitude, self.dropoff_longitude
        )
        
        # Distance from driver pickup to passenger pickup
        pickup_detour = self.calculate_distance(
            self.pickup_latitude, self.pickup_longitude,
            passenger_pickup_lat, passenger_pickup_lng
        )
        
        # Distance from passenger pickup to driver destination
        passenger_to_dest = self.calculate_distance(
            passenger_pickup_lat, passenger_pickup_lng,
            self.dropoff_latitude, self.dropoff_longitude
        )
        
        # If detour is less than 20% of total trip and passenger destination
        # is roughly in the same direction, consider it compatible
        detour_ratio = pickup_detour / driver_total_distance if driver_total_distance > 0 else 0
        
        return detour_ratio <= 0.2  # Max 20% detour acceptable


class RideStop(models.Model):
    """Model for intermediate stops along a ride route"""
    
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='stops')
    location_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    sequence = models.PositiveIntegerField(default=0, help_text="Order of stop in the route")
    scheduled_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['sequence']
    
    def __str__(self):
        return f"Stop at {self.location_name} on ride {self.ride_id}"


class RidePassenger(TimeStampedModel):
    """Model for passengers joining rides among colleagues and friends"""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    )

    RELATIONSHIP_TYPE = (
        ("colleague", "Colleague"),
        ("friend", "Friend"),
        ("family", "Family Member"),
        ("acquaintance", "Acquaintance"),
        ("other", "Other"),
    )

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="joined_rides"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    pickup_note = models.CharField(
        max_length=255, blank=True, help_text="Special instructions for pickup"
    )
    
    # Passenger's individual pickup and dropoff locations
    passenger_pickup_location = models.CharField(max_length=255, blank=True)
    passenger_dropoff_location = models.CharField(max_length=255, blank=True)
    passenger_pickup_latitude = models.FloatField(null=True, blank=True)
    passenger_pickup_longitude = models.FloatField(null=True, blank=True)
    passenger_dropoff_latitude = models.FloatField(null=True, blank=True)
    passenger_dropoff_longitude = models.FloatField(null=True, blank=True)
    
    # Individual fare calculation
    passenger_distance_km = models.FloatField(
        default=0.0,
        help_text="Passenger's individual travel distance in kilometers"
    )
    individual_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Fare calculated for this passenger's specific distance"
    )
    fare_calculated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When fare was calculated"
    )

    # Enhanced fields for colleague/friend carpooling
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_TYPE,
        default="colleague",
        help_text="Relationship with the driver",
    )
    contribution_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Amount contributed to trip costs",
    )
    has_contributed = models.BooleanField(
        default=False, help_text="Whether the passenger has paid their contribution"
    )

    # Social aspects
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_passengers",
    )
    regular_passenger = models.BooleanField(
        default=False,
        help_text="Whether this is a regular passenger for recurring rides",
    )
    
    def calculate_individual_fare(self):
        """Calculate fare for this passenger based on their individual distance"""
        if self.passenger_distance_km > 0:
            fare_details = FareCalculator.calculate_individual_fare(
                self.passenger_distance_km,
                self.ride.departure_time
            )
            self.individual_fare = fare_details['fare_amount']
            self.fare_calculated_at = timezone.now()
            self.save()
            return fare_details
        return None
    
    def get_fare_breakdown(self):
        """Get detailed fare breakdown for this passenger"""
        if self.individual_fare > 0:
            is_peak = FareCalculator.is_peak_hour(self.ride.departure_time)
            rate = FareCalculator.get_current_rate(self.ride.departure_time)
            
            return {
                'distance_km': self.passenger_distance_km,
                'rate_per_km': float(rate),
                'is_peak_hour': is_peak,
                'total_fare': float(self.individual_fare),
                'calculated_at': self.fare_calculated_at,
            }
        return None

    # Enhanced fields for colleague/friend carpooling
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_TYPE,
        default="colleague",
        help_text="Relationship with the driver",
    )
    contribution_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text="Amount contributed to trip costs",
    )
    has_contributed = models.BooleanField(
        default=False, help_text="Whether the passenger has paid their contribution"
    )

    # Social aspects
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_passengers",
    )
    regular_passenger = models.BooleanField(
        default=False,
        help_text="Whether this is a regular passenger for recurring rides",
    )

    class Meta:
        unique_together = ("ride", "passenger")

    def __str__(self):
        return f"{self.passenger.username} - {self.ride}"


class FareCalculator:
    """Comprehensive fare calculation system for Carwaan"""
    
    # Default fare rate per kilometer in PKR
    BASE_FARE_PER_KM = Decimal('30.00')
    
    # Peak hour multiplier
    PEAK_HOUR_MULTIPLIER = Decimal('2.0')
    
    # Peak hours definition (24-hour format)
    PEAK_HOURS = [
        (time(8, 0), time(10, 0)),    # 8 AM - 10 AM
        (time(17, 0), time(19, 0)),   # 5 PM - 7 PM
    ]
    
    @classmethod
    def is_peak_hour(cls, datetime_obj):
        """Check if given datetime falls in peak hours"""
        import pytz
        # Convert to Karachi timezone
        karachi_tz = pytz.timezone('Asia/Karachi')
        if timezone.is_aware(datetime_obj):
            local_time = datetime_obj.astimezone(karachi_tz)
        else:
            local_time = karachi_tz.localize(datetime_obj)
        
        current_time = local_time.time()
        
        for start_time, end_time in cls.PEAK_HOURS:
            if start_time <= current_time <= end_time:
                return True
        return False
    
    @classmethod
    def calculate_individual_fare(cls, passenger_distance_km, departure_time):
        """
        Calculate fare for individual passenger based on their specific travel distance
        
        Args:
            passenger_distance_km: Passenger's individual travel distance in kilometers
            departure_time: Departure datetime
        
        Returns:
            dict with fare details
        """
        # Handle zero or negative distance
        if passenger_distance_km <= 0:
            return {
                'fare_amount': Decimal('0.00'),
                'distance_km': 0.0,
                'rate_per_km': cls.get_current_rate(departure_time),
                'is_peak_hour': cls.is_peak_hour(departure_time),
                'peak_multiplier': cls.PEAK_HOUR_MULTIPLIER if cls.is_peak_hour(departure_time) else Decimal('1.0'),
            }
        
        # Get current rate (base or peak)
        current_rate = cls.get_current_rate(departure_time)
        
        # Calculate fare for this passenger's distance
        fare_amount = current_rate * Decimal(str(passenger_distance_km))
        
        return {
            'fare_amount': round(fare_amount, 2),
            'distance_km': passenger_distance_km,
            'rate_per_km': current_rate,
            'is_peak_hour': cls.is_peak_hour(departure_time),
            'peak_multiplier': cls.PEAK_HOUR_MULTIPLIER if cls.is_peak_hour(departure_time) else Decimal('1.0'),
        }
    
    @classmethod
    def get_current_rate(cls, departure_time):
        """Get current rate per km based on time"""
        if cls.is_peak_hour(departure_time):
            return cls.BASE_FARE_PER_KM * cls.PEAK_HOUR_MULTIPLIER
        return cls.BASE_FARE_PER_KM
    
    @classmethod
    def calculate_fare(cls, distance_km, departure_time, passenger_count=1):
        """
        Calculate fare based on distance, time, and passenger count (legacy method)
        
        Args:
            distance_km: Distance in kilometers
            departure_time: Departure datetime
            passenger_count: Number of passengers (for fare splitting)
        
        Returns:
            dict with fare details
        """
        base_fare = cls.BASE_FARE_PER_KM * Decimal(str(distance_km))
        
        # Apply peak hour multiplier
        if cls.is_peak_hour(departure_time):
            total_fare = base_fare * cls.PEAK_HOUR_MULTIPLIER
            is_peak = True
        else:
            total_fare = base_fare
            is_peak = False
        
        # Calculate per passenger fare (split equally)
        fare_per_passenger = total_fare / passenger_count if passenger_count > 0 else total_fare
        
        return {
            'base_fare': float(base_fare),
            'total_fare': float(total_fare),
            'fare_per_passenger': float(fare_per_passenger),
            'is_peak_hour': is_peak,
            'peak_multiplier': float(cls.PEAK_HOUR_MULTIPLIER) if is_peak else 1.0,
            'passenger_count': passenger_count,
            'distance_km': distance_km
        }


class ScheduledRide(TimeStampedModel):
    """Model for pre-booked/scheduled rides"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="scheduled_rides"
    )
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    dropoff_latitude = models.FloatField(null=True, blank=True)
    dropoff_longitude = models.FloatField(null=True, blank=True)
    
    scheduled_date = models.DateField(help_text="Date for the scheduled ride")
    scheduled_time = models.TimeField(help_text="Time for the scheduled ride")
    
    gender_preference = models.CharField(
        max_length=20, 
        choices=Ride.GENDER_PREFERENCE_CHOICES, 
        default="any"
    )
    
    is_driver = models.BooleanField(
        default=False, 
        help_text="True if user wants to drive, False if looking for a ride"
    )
    
    seats_needed = models.PositiveIntegerField(
        default=1, 
        help_text="Number of seats needed (for passengers)"
    )
    
    seats_offered = models.PositiveIntegerField(
        default=1, 
        help_text="Number of seats offered (for drivers)"
    )
    
    notes = models.TextField(blank=True)
    
    # Matching
    matched_ride = models.ForeignKey(
        'Ride', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="The actual ride this was matched to"
    )
    
    is_active = models.BooleanField(
        default=True, 
        help_text="Whether this scheduled ride is still looking for matches"
    )
    
    def __str__(self):
        role = "Driver" if self.is_driver else "Passenger"
        return f"{role} scheduled: {self.pickup_location} to {self.dropoff_location} on {self.scheduled_date}"


class RideReview(TimeStampedModel):
    """Model for ride reviews and ratings"""
    
    REVIEW_TYPE_CHOICES = (
        ('driver_to_passenger', 'Driver rating Passenger'),
        ('passenger_to_driver', 'Passenger rating Driver'),
        ('passenger_to_passenger', 'Passenger rating Passenger'),
    )
    
    ride = models.ForeignKey(
        'Ride', 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='reviews_given'
    )
    
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='reviews_received'
    )
    
    review_type = models.CharField(max_length=30, choices=REVIEW_TYPE_CHOICES)
    
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    
    comment = models.TextField(blank=True, help_text="Optional review comment")
    
    # Review categories for detailed feedback
    punctuality_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    
    cleanliness_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    
    communication_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    
    safety_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    
    class Meta:
        unique_together = ('ride', 'reviewer', 'reviewee')
    
    def __str__(self):
        return f"{self.reviewer.first_name} rated {self.reviewee.first_name}: {self.rating} stars"


class RideDirection(models.Model):
    """Model to store common routes/directions for better matching"""
    
    name = models.CharField(max_length=100, help_text="Route name (e.g., 'Gulshan to Saddar')")
    start_area = models.CharField(max_length=100)
    end_area = models.CharField(max_length=100)
    
    # Key waypoints along this route
    waypoints = models.JSONField(
        default=list, 
        help_text="List of major areas/landmarks along this route"
    )
    
    average_distance_km = models.FloatField(default=0.0)
    average_duration_minutes = models.IntegerField(default=0)
    
    # Usage statistics
    usage_count = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = ('start_area', 'end_area')


class FareCalculation(models.Model):
    """Model to store fare calculations for rides"""
    
    ride = models.OneToOneField(
        'Ride', 
        on_delete=models.CASCADE, 
        related_name='fare_details'
    )
    
    base_fare = models.DecimalField(max_digits=10, decimal_places=2)
    peak_hour_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.0)
    total_fare = models.DecimalField(max_digits=10, decimal_places=2)
    fare_per_passenger = models.DecimalField(max_digits=10, decimal_places=2)
    
    is_peak_hour = models.BooleanField(default=False)
    passenger_count = models.PositiveIntegerField(default=1)
    distance_km = models.FloatField()
    
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Fare for ride {self.ride.id}: PKR {self.total_fare}"

# Karachi areas for localization
KARACHI_AREAS = [
    'Saddar', 'Gulshan-e-Iqbal', 'Defence (DHA)', 'Clifton', 'Nazimabad',
    'North Nazimabad', 'Gulberg', 'Johar Town', 'Malir', 'Korangi',
    'Landhi', 'Shah Faisal Colony', 'Soldier Bazaar', 'Garden',
    'Lyari', 'Keamari', 'Orangi Town', 'New Karachi', 'Surjani Town',
    'Scheme 33', 'Gulistan-e-Johar', 'Pechs', 'Tariq Road',
    'Bahadurabad', 'Shahrah-e-Faisal', 'University Road', 'Main University Road',
    'Shahra-e-Quaideen', 'II Chundrigar Road', 'MA Jinnah Road',
    'Kemari Port', 'Port Qasim', 'Karachi Airport', 'Jinnah International Airport'
]

# Desi/Local names for users (replacing generic names)
DESI_NAMES = {
    'male': [
        'Ahmed Ali', 'Muhammad Hassan', 'Ali Khan', 'Usman Ahmad', 'Shahid Iqbal',
        'Tariq Mahmood', 'Kamran Sheikh', 'Imran Khan', 'Fahad Malik', 'Bilal Ahmed',
        'Saqib Raza', 'Adnan Siddiqui', 'Faisal Sheikh', 'Rizwan Ali', 'Zubair Ahmed'
    ],
    'female': [
        'Fatima Khan', 'Ayesha Ahmed', 'Sana Ali', 'Mariam Sheikh', 'Zara Malik',
        'Nida Hassan', 'Farah Iqbal', 'Samina Khatoon', 'Rabia Siddiqui', 'Hina Tariq',
        'Shazia Begum', 'Noor Fatima', 'Saira Khan', 'Rubina Ahmed', 'Mehreen Ali'
    ]
}

class DriverDashboard:
    """Helper class for driver dashboard functionality"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def get_upcoming_rides(self):
        """Get upcoming rides for the driver"""
        from django.utils import timezone
        
        return Ride.objects.filter(
            driver=self.driver,
            departure_time__gte=timezone.now(),
            status='scheduled'
        ).order_by('departure_time')
    
    def get_ride_summary(self, ride):
        """Get comprehensive ride summary for dashboard"""
        passengers = RidePassenger.objects.filter(
            ride=ride,
            status='confirmed'
        ).select_related('passenger')
        
        return {
            'ride_id': ride.id,
            'pickup_location': ride.pickup_location,
            'dropoff_location': ride.dropoff_location,
            'departure_time': ride.departure_time,
            'vehicle': ride.get_vehicle_display_info(),
            'total_seats': ride.total_seats,
            'available_seats': ride.available_seats,
            'passengers': [
                {
                    'name': p.passenger.get_display_name(),
                    'gender': p.passenger.get_gender_display(),
                    'pickup_location': p.passenger_pickup_location or ride.pickup_location,
                    'dropoff_location': p.passenger_dropoff_location or ride.dropoff_location,
                    'fare': float(p.individual_fare),
                    'phone': p.passenger.phone,
                    'rating': float(p.passenger.passenger_rating),
                }
                for p in passengers
            ],
            'total_earnings': sum(p.individual_fare for p in passengers),
            'status': ride.status,
            'can_start': ride.status == 'scheduled' and passengers.exists(),
        }
    
    def get_pending_requests(self):
        """Get pending passenger requests for driver's rides"""
        return RidePassenger.objects.filter(
            ride__driver=self.driver,
            status='pending'
        ).select_related('passenger', 'ride').order_by('-joined_at')


class PassengerView:
    """Helper class for passenger view functionality"""
    
    def __init__(self, passenger):
        self.passenger = passenger
    
    def find_matching_rides(self, pickup_lat, pickup_lng, dest_lat, dest_lng, departure_time, female_only=False):
        """Find rides matching passenger requirements"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Time window: ±15 minutes
        time_window_start = departure_time - timedelta(minutes=15)
        time_window_end = departure_time + timedelta(minutes=15)
        
        # Base queryset
        rides = Ride.objects.filter(
            departure_time__range=(time_window_start, time_window_end),
            status='scheduled',
            available_seats__gt=0
        ).select_related('driver', 'vehicle')
        
        # Apply female-only filter
        if female_only or self.passenger.female_only_preference:
            rides = rides.filter(
                female_only_ride=True,
                driver__gender='female'
            )
        
        # Filter rides passenger can join
        eligible_rides = []
        for ride in rides:
            can_join, reason = ride.can_passenger_join(self.passenger)
            if can_join:
                # Calculate route compatibility and fare
                distance_km = self.calculate_passenger_distance(
                    pickup_lat, pickup_lng, dest_lat, dest_lng, ride
                )
                
                if distance_km > 0:
                    fare_details = FareCalculator.calculate_individual_fare(
                        distance_km, ride.departure_time
                    )
                    
                    ride_info = {
                        'ride': ride,
                        'driver_info': ride.get_driver_display_info(),
                        'vehicle_info': ride.get_vehicle_display_info(),
                        'distance_km': distance_km,
                        'fare_details': fare_details,
                        'seats_available': ride.available_seats,
                        'current_passengers': ride.current_male_passengers + ride.current_female_passengers,
                    }
                    eligible_rides.append(ride_info)
        
        # Sort by relevance (distance, time, rating)
        eligible_rides.sort(key=lambda x: (x['distance_km'], -x['ride'].driver.driver_rating))
        
        return eligible_rides
    
    def calculate_passenger_distance(self, pickup_lat, pickup_lng, dest_lat, dest_lng, ride):
        """Calculate passenger's individual travel distance for a ride"""
        import math
        
        # Simple distance calculation (could be enhanced with route calculation)
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371  # Earth's radius in kilometers
            
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            
            a = (math.sin(dlat/2) * math.sin(dlat/2) + 
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
                 math.sin(dlon/2) * math.sin(dlon/2))
            
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        return haversine_distance(pickup_lat, pickup_lng, dest_lat, dest_lng)


class RideRequest(TimeStampedModel):
    """Model for passenger requests to join rides"""
    
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    )
    
    ride = models.ForeignKey(
        'Ride', 
        on_delete=models.CASCADE, 
        related_name='ride_requests'
    )
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='ride_requests'
    )
    
    # Passenger's specific pickup and dropoff
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    pickup_latitude = models.FloatField()
    pickup_longitude = models.FloatField()
    dropoff_latitude = models.FloatField()
    dropoff_longitude = models.FloatField()
    
    # Request details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, help_text="Driver's response message")
    seats_requested = models.PositiveIntegerField(default=1)
    
    # Calculated fare
    estimated_distance_km = models.FloatField(default=0.0)
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Response from driver
    driver_response = models.TextField(blank=True, help_text="Driver's response message")
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('ride', 'passenger')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.passenger.get_display_name()} -> {self.ride}"
    
    def calculate_fare(self):
        """Calculate estimated fare for this request"""
        if self.estimated_distance_km > 0:
            fare_details = FareCalculator.calculate_individual_fare(
                passenger_distance_km=self.estimated_distance_km,
                departure_time=self.ride.departure_time
            )
            self.estimated_fare = fare_details['fare_amount']
            self.save()
            return fare_details
        return None
    
    def accept_request(self, driver_message=""):
        """Accept the ride request and create RidePassenger"""
        if self.status != 'pending':
            raise ValueError("Can only accept pending requests")
        
        if self.ride.available_seats < self.seats_requested:
            raise ValueError("Not enough seats available")
        
        # Check gender restrictions
        if self.ride.female_only_ride and not self.passenger.can_join_female_only_ride():
            raise ValueError("This is a female-only ride")
        
        # Create RidePassenger entry
        ride_passenger = RidePassenger.objects.create(
            ride=self.ride,
            passenger=self.passenger,
            status='confirmed',
            passenger_pickup_location=self.pickup_location,
            passenger_dropoff_location=self.dropoff_location,
            passenger_pickup_latitude=self.pickup_latitude,
            passenger_pickup_longitude=self.pickup_longitude,
            passenger_dropoff_latitude=self.dropoff_latitude,
            passenger_dropoff_longitude=self.dropoff_longitude,
            passenger_distance_km=self.estimated_distance_km,
            individual_fare=self.estimated_fare
        )
        
        # Update ride seats
        self.ride.available_seats -= self.seats_requested
        self.ride.save()
        
        # Update request status
        self.status = 'accepted'
        self.driver_response = driver_message
        self.responded_at = timezone.now()
        self.save()
        
        return ride_passenger
    
    def reject_request(self, driver_message=""):
        """Reject the ride request"""
        if self.status != 'pending':
            raise ValueError("Can only reject pending requests")
        
        self.status = 'rejected'
        self.driver_response = driver_message
        self.responded_at = timezone.now()
        self.save()


class DriverDashboard:
    """Utility class for driver dashboard functionality"""
    
    @staticmethod
    def get_upcoming_rides(driver):
        """Get driver's upcoming rides with passenger info"""
        upcoming_rides = Ride.objects.filter(
            driver=driver,
            departure_time__gte=timezone.now(),
            status__in=['scheduled', 'in_progress']
        ).order_by('departure_time')
        
        dashboard_data = []
        for ride in upcoming_rides:
            passengers = RidePassenger.objects.filter(
                ride=ride, 
                status='confirmed'
            ).select_related('passenger')
            
            ride_info = {
                'ride': ride,
                'passengers': passengers,
                'seats_left': ride.available_seats,
                'can_start': ride.status == 'scheduled',
                'pending_requests': RideRequest.objects.filter(
                    ride=ride, 
                    status='pending'
                ).count()
            }
            dashboard_data.append(ride_info)
        
        return dashboard_data
    
    @staticmethod
    def get_ride_requests(driver):
        """Get pending ride requests for driver's rides"""
        return RideRequest.objects.filter(
            ride__driver=driver,
            status='pending'
        ).select_related('passenger', 'ride').order_by('-created_at')


class PassengerFinder:
    """Utility class for passenger ride finding functionality"""
    
    @staticmethod
    def find_rides(passenger, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, 
                  departure_time, female_only=False):
        """Find available rides for passenger based on route compatibility"""
        from .route_service import route_service
        
        # Calculate time window (±30 minutes for better matching)
        time_window_start = departure_time - timedelta(minutes=30)
        time_window_end = departure_time + timedelta(minutes=30)
        
        def _get_base_query_with_gender_filter(apply_female_filter=False):
            """Helper function to get base query with optional gender filtering"""
            query = Ride.objects.filter(
                departure_time__range=(time_window_start, time_window_end),
                available_seats__gt=0,
                status='scheduled'
            ).exclude(driver=passenger)
            
            # Apply gender filter if requested
            if apply_female_filter:
                if female_only or getattr(passenger, 'female_only_preference', False):
                    query = query.filter(female_only_ride=True)
                
                # Check if passenger can join female-only rides
                if not passenger.can_join_female_only_ride():
                    query = query.exclude(female_only_ride=True)
            else:
                # When showing all rides, still respect passenger's ability to join female-only rides
                if not passenger.can_join_female_only_ride():
                    query = query.exclude(female_only_ride=True)
            
            return query
        
        # Calculate passenger's desired route
        try:
            passenger_route = route_service.calculate_route(
                pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, 'fastest'
            )
            passenger_distance = passenger_route['distance_km']
        except Exception as e:
            # Fallback to straight-line distance
            passenger_distance = PassengerFinder._haversine_distance(
                pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
            )
        
        def _process_rides(rides_query, min_compatibility=0.3):
            """Helper function to process rides and return ride data"""
            available_rides = []
            for ride in rides_query:
                try:
                    # Check route compatibility
                    compatibility_score = PassengerFinder._calculate_route_compatibility(
                        pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride
                    )
                    
                    if compatibility_score >= min_compatibility:
                        # Calculate actual passenger distance based on ride route
                        passenger_ride_distance = PassengerFinder._calculate_passenger_distance(
                            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride
                        )
                        
                        # Calculate fare
                        fare_details = FareCalculator.calculate_individual_fare(
                            passenger_distance_km=passenger_ride_distance,
                            departure_time=ride.departure_time
                        )
                        
                        ride_data = {
                            'ride': ride,
                            'driver': ride.driver,
                            'vehicle': ride.vehicle,
                            'distance_km': passenger_ride_distance,
                            'estimated_fare': fare_details['fare_amount'],
                            'is_peak_hour': fare_details['is_peak_hour'],
                            'compatibility_score': compatibility_score,
                            'time_difference_minutes': abs((ride.departure_time - departure_time).total_seconds() / 60)
                        }
                        available_rides.append(ride_data)
                        
                except Exception as e:
                    # Log error but continue with other rides
                    logger.warning(f"Error processing ride {ride.id}: {e}")
                    continue
            return available_rides
        
        # First attempt: Find rides with gender filter and high compatibility
        rides_query = _get_base_query_with_gender_filter(apply_female_filter=True)
        available_rides = _process_rides(rides_query, min_compatibility=0.3)
        
        # If no rides found with specific criteria, try with relaxed compatibility
        if not available_rides:
            available_rides = _process_rides(rides_query, min_compatibility=0.1)
        
        # If still no rides found, expand to all available rides (respecting gender restrictions)
        if not available_rides:
            # Expand time window for fallback
            extended_time_start = departure_time - timedelta(hours=2)
            extended_time_end = departure_time + timedelta(hours=2)
            
            fallback_query = Ride.objects.filter(
                departure_time__range=(extended_time_start, extended_time_end),
                available_seats__gt=0,
                status='scheduled'
            ).exclude(driver=passenger)
            
            # Still respect passenger's ability to join female-only rides
            if not passenger.can_join_female_only_ride():
                fallback_query = fallback_query.exclude(female_only_ride=True)
            
            available_rides = _process_rides(fallback_query, min_compatibility=0.0)
        
        # Sort by compatibility score, then fare, then driver rating
        available_rides.sort(key=lambda x: (
            -x['compatibility_score'],  # Higher compatibility first
            x['estimated_fare'],        # Lower fare first
            -x['driver'].driver_rating, # Higher rating first
            x['time_difference_minutes'] # Closer time first
        ))
        
        return available_rides[:20]  # Return top 20 matches
    
    @staticmethod
    def _calculate_route_compatibility(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride):
        """Calculate how compatible passenger route is with ride route"""
        
        # Check proximity to pickup and dropoff locations
        pickup_to_ride_start = PassengerFinder._haversine_distance(
            pickup_lat, pickup_lng, ride.pickup_latitude, ride.pickup_longitude
        )
        dropoff_to_ride_end = PassengerFinder._haversine_distance(
            dropoff_lat, dropoff_lng, ride.dropoff_latitude, ride.dropoff_longitude
        )
        
        # Maximum reasonable detour distances (in km)
        MAX_PICKUP_DETOUR = 5.0
        MAX_DROPOFF_DETOUR = 5.0
        
        # Calculate compatibility scores (0-1 scale)
        pickup_score = max(0, 1 - (pickup_to_ride_start / MAX_PICKUP_DETOUR))
        dropoff_score = max(0, 1 - (dropoff_to_ride_end / MAX_DROPOFF_DETOUR))
        
        # Check if passenger's route is generally in the same direction
        direction_score = PassengerFinder._calculate_direction_compatibility(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride
        )
        
        # Overall compatibility is weighted average
        compatibility = (pickup_score * 0.4 + dropoff_score * 0.4 + direction_score * 0.2)
        
        return min(1.0, compatibility)
    
    @staticmethod
    def _calculate_direction_compatibility(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride):
        """Check if passenger's direction is compatible with ride direction"""
        import math
        
        # Calculate passenger's bearing
        passenger_bearing = math.atan2(
            dropoff_lng - pickup_lng,
            dropoff_lat - pickup_lat
        )
        
        # Calculate ride's bearing
        ride_bearing = math.atan2(
            ride.dropoff_longitude - ride.pickup_longitude,
            ride.dropoff_latitude - ride.pickup_latitude
        )
        
        # Calculate angular difference
        bearing_diff = abs(passenger_bearing - ride_bearing)
        if bearing_diff > math.pi:
            bearing_diff = 2 * math.pi - bearing_diff
        
        # Convert to compatibility score (0-1)
        # Same direction = 1.0, opposite direction = 0.0
        direction_compatibility = max(0, 1 - (bearing_diff / math.pi))
        
        return direction_compatibility
    
    @staticmethod
    def _calculate_passenger_distance(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, ride):
        """Calculate passenger's travel distance considering the ride route"""
        from .route_service import route_service
        
        try:
            # Try to calculate actual route distance
            route_info = route_service.calculate_route(
                pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, 'fastest'
            )
            return route_info['distance_km']
        except Exception:
            # Fallback to straight-line distance
            return PassengerFinder._haversine_distance(
                pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
            )
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate haversine distance between two points"""
        import math
        
        R = 6371  # Earth's radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c


class Review(TimeStampedModel):
    """Model for ride reviews between drivers and passengers"""
    
    REVIEWER_TYPES = [
        ('driver', 'Driver'),
        ('passenger', 'Passenger'),
    ]
    
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='user_reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_reviews_given')
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_reviews_received')
    reviewer_type = models.CharField(max_length=10, choices=REVIEWER_TYPES)
    
    # Rating fields
    overall_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Overall rating from 1 to 5"
    )
    punctuality_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Punctuality rating from 1 to 5",
        null=True, blank=True
    )
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Communication rating from 1 to 5",
        null=True, blank=True
    )
    behavior_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Behavior rating from 1 to 5",
        null=True, blank=True
    )
    
    # Review content
    comment = models.TextField(max_length=500, blank=True, null=True)
    
    # Additional flags for driver reviews about passengers
    would_ride_again = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['ride', 'reviewer', 'reviewee']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reviewer.get_full_name()} -> {self.reviewee.get_full_name()} ({self.overall_rating}★)"
    
    def clean(self):
        # Ensure reviewer and reviewee are different
        if self.reviewer == self.reviewee:
            raise ValidationError("Reviewer and reviewee cannot be the same person")
        
        # Ensure reviewer was part of the ride
        if self.reviewer_type == 'driver':
            if self.ride.driver != self.reviewer:
                raise ValidationError("Only the ride driver can submit driver reviews")
        elif self.reviewer_type == 'passenger':
            if not self.ride.passengers.filter(user=self.reviewer).exists():
                raise ValidationError("Only ride passengers can submit passenger reviews")
        
        # Ensure reviewee was part of the ride
        if self.reviewer_type == 'driver':
            # Driver reviewing a passenger
            if not self.ride.passengers.filter(user=self.reviewee).exists():
                raise ValidationError("Can only review passengers who were on this ride")
        elif self.reviewer_type == 'passenger':
            # Passenger reviewing the driver
            if self.ride.driver != self.reviewee:
                raise ValidationError("Passengers can only review the ride driver")
