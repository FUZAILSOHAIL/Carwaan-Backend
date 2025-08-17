#!/usr/bin/env python3
"""
Data Validation Script for Carwaan Test Data
Validates that the generated test data is correct and complete

Run with: python manage.py validate_test_data
"""

from django.core.management.base import BaseCommand
from apps.users.models import User, Vehicle
from apps.rides.models import Ride, Location, RidePassenger, RideRequest

class Command(BaseCommand):
    help = 'Validate generated test data for Carwaan'

    def handle(self, *args, **options):
        self.stdout.write('Validating Carwaan test data...')
        
        # Count all data
        user_count = User.objects.count()
        vehicle_count = Vehicle.objects.count()
        location_count = Location.objects.count()
        ride_count = Ride.objects.count()
        passenger_count = RidePassenger.objects.count()
        request_count = RideRequest.objects.count()
        
        self.stdout.write(f'📊 Data Summary:')
        self.stdout.write(f'  - Users: {user_count}')
        self.stdout.write(f'  - Vehicles: {vehicle_count}')
        self.stdout.write(f'  - Locations: {location_count}')
        self.stdout.write(f'  - Rides: {ride_count}')
        self.stdout.write(f'  - Ride Passengers: {passenger_count}')
        self.stdout.write(f'  - Ride Requests: {request_count}')
        
        # Validate data quality
        self.validate_users()
        self.validate_vehicles()
        self.validate_rides()
        self.validate_locations()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Test data validation completed!')
        )

    def validate_users(self):
        """Validate user data"""
        total_users = User.objects.count()
        drivers = User.objects.filter(is_driver=True).count()
        verified_users = User.objects.filter(is_verified=True).count()
        admin_users = User.objects.filter(role='admin').count()
        pakistani_phones = User.objects.filter(phone__startswith='+923').count()
        karachi_cnics = User.objects.filter(cnic__startswith='42101').count()
        
        self.stdout.write(f'\n👥 User Validation:')
        self.stdout.write(f'  - Total users: {total_users}')
        self.stdout.write(f'  - Drivers: {drivers}')
        self.stdout.write(f'  - Verified users: {verified_users}')
        self.stdout.write(f'  - Admin users: {admin_users}')
        self.stdout.write(f'  - Pakistani phone numbers: {pakistani_phones}')
        self.stdout.write(f'  - Karachi CNICs: {karachi_cnics}')
        
        # Check for test accounts
        test_accounts = User.objects.filter(email__contains='test.carwaan').count()
        if test_accounts > 0:
            self.stdout.write(f'  - Test accounts: {test_accounts}')
            
        # Sample user data
        sample_user = User.objects.first()
        if sample_user:
            self.stdout.write(f'  - Sample user: {sample_user.first_name} {sample_user.last_name} ({sample_user.email})')

    def validate_vehicles(self):
        """Validate vehicle data"""
        total_vehicles = Vehicle.objects.count()
        verified_vehicles = Vehicle.objects.filter(is_verified=True).count()
        active_vehicles = Vehicle.objects.filter(is_active=True).count()
        toyota_vehicles = Vehicle.objects.filter(make='Toyota').count()
        khi_plates = Vehicle.objects.filter(license_plate__startswith='KHI').count()
        
        self.stdout.write(f'\n🚗 Vehicle Validation:')
        self.stdout.write(f'  - Total vehicles: {total_vehicles}')
        self.stdout.write(f'  - Verified vehicles: {verified_vehicles}')
        self.stdout.write(f'  - Active vehicles: {active_vehicles}')
        self.stdout.write(f'  - Toyota vehicles: {toyota_vehicles}')
        self.stdout.write(f'  - Karachi license plates: {khi_plates}')
        
        # Sample vehicle data
        sample_vehicle = Vehicle.objects.first()
        if sample_vehicle:
            self.stdout.write(f'  - Sample vehicle: {sample_vehicle.make} {sample_vehicle.model} ({sample_vehicle.license_plate})')

    def validate_rides(self):
        """Validate ride data"""
        total_rides = Ride.objects.count()
        scheduled_rides = Ride.objects.filter(status='scheduled').count()
        recurring_rides = Ride.objects.filter(is_recurring=True).count()
        commute_rides = Ride.objects.filter(ride_type='commute').count()
        ac_rides = Ride.objects.filter(has_ac=True).count()
        
        self.stdout.write(f'\n🚙 Ride Validation:')
        self.stdout.write(f'  - Total rides: {total_rides}')
        self.stdout.write(f'  - Scheduled rides: {scheduled_rides}')
        self.stdout.write(f'  - Recurring rides: {recurring_rides}')
        self.stdout.write(f'  - Commute rides: {commute_rides}')
        self.stdout.write(f'  - AC rides: {ac_rides}')
        
        # Sample ride data
        sample_ride = Ride.objects.first()
        if sample_ride:
            self.stdout.write(f'  - Sample ride: {sample_ride.pickup_location} → {sample_ride.dropoff_location}')

    def validate_locations(self):
        """Validate location data"""
        total_locations = Location.objects.count()
        karachi_locations = Location.objects.filter(city='Karachi').count()
        universities = Location.objects.filter(is_university=True).count()
        workplaces = Location.objects.filter(is_workplace=True).count()
        landmarks = Location.objects.filter(is_landmark=True).count()
        
        self.stdout.write(f'\n📍 Location Validation:')
        self.stdout.write(f'  - Total locations: {total_locations}')
        self.stdout.write(f'  - Karachi locations: {karachi_locations}')
        self.stdout.write(f'  - Universities: {universities}')
        self.stdout.write(f'  - Workplaces: {workplaces}')
        self.stdout.write(f'  - Landmarks: {landmarks}')
        
        # Sample location data
        sample_location = Location.objects.first()
        if sample_location:
            self.stdout.write(f'  - Sample location: {sample_location.name} ({sample_location.address})')
            
        # Check coordinate bounds for Karachi
        locations_with_coords = Location.objects.exclude(latitude__isnull=True, longitude__isnull=True)
        karachi_bound_locations = locations_with_coords.filter(
            latitude__gte=24.7, latitude__lte=25.0,
            longitude__gte=66.9, longitude__lte=67.3
        ).count()
        
        if locations_with_coords.count() > 0:
            self.stdout.write(f'  - Locations within Karachi bounds: {karachi_bound_locations}/{locations_with_coords.count()}')
