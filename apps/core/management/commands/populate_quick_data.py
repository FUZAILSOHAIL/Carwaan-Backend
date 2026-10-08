#!/usr/bin/env python3
"""
Quick Data Population Script for Carwaan
Generates minimal but complete test data for immediate use

Run with: python manage.py populate_quick_data
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from apps.core.envconf import required_env
from apps.users.models import User, Vehicle
from apps.rides.models import Ride, Location
import pytz

class Command(BaseCommand):
    help = 'Quickly populate essential test data for Carwaan'

    def handle(self, *args, **options):
        self.stdout.write('Creating quick test data for Carwaan...')
        
        # Create essential locations first
        self.create_essential_locations()
        
        # Create a few test users
        users = self.create_test_users()
        
        # Create vehicles for drivers
        vehicles = self.create_test_vehicles(users)
        
        # Create some test rides
        rides = self.create_test_rides(users, vehicles)
        
        self.stdout.write(
            self.style.SUCCESS(
                'Quick test data created successfully!\n'
                'Test accounts (passwords come from the environment, not the source tree):\n'
                '- Male Driver: hassan.ahmed.0@test.carwaan.pk (TEST_USER_PASSWORD)\n'
                '- Female Driver: aisha.malik.2@test.carwaan.pk (TEST_USER_PASSWORD)\n'
                '- Female Passenger: fatima.khan.1@test.carwaan.pk (TEST_USER_PASSWORD)\n'
                '- Admin: admin@carwaan.pk (ADMIN_PASSWORD)\n'
                f'- Created {len(rides)} test rides (including female-only rides)'
            )
        )

    def create_essential_locations(self):
        """Create key Karachi locations"""
        locations_data = [
            ('University of Karachi', 'University Road, Karachi', 24.9408, 67.1017),
            ('IBA Karachi', 'University Road, Karachi', 24.9472, 67.1191),
            ('Clifton Block 2', 'Clifton, Karachi', 24.8138, 67.0299),
            ('DHA Phase 5', 'DHA Phase 5, Karachi', 24.8243, 67.0633),
            ('Gulshan-e-Iqbal', 'Gulshan-e-Iqbal, Karachi', 24.9183, 67.1078),
            ('Saddar', 'Saddar, Karachi', 24.8535, 67.0146),
            ('I.I. Chundrigar Road', 'Business District, Karachi', 24.8453, 67.0240),
            ('Jinnah International Airport', 'Airport Road, Karachi', 24.9065, 67.1607),
        ]
        
        for name, address, lat, lng in locations_data:
            Location.objects.get_or_create(
                name=name,
                defaults={
                    'address': address,
                    'latitude': lat,
                    'longitude': lng,
                    'city': 'Karachi',
                    'state': 'Sindh'
                }
            )

    def create_test_users(self):
        """Create a few test users with different roles"""
        users = []
        admin_password = required_env("ADMIN_PASSWORD")
        test_password = required_env("TEST_USER_PASSWORD")
        
        # Create admin user
        admin_user, created = User.objects.get_or_create(
            email='admin@carwaan.pk',
            defaults={
                'username': 'admin',
                'password': make_password(admin_password),
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'gender': 'male',
                'is_driver': False,
                'has_car': False,
                'driver_verification_status': 'pending'  # Set to pending since not a driver
            }
        )
        if created:
            users.append(admin_user)
        else:
            # Ensure admin is not a driver
            admin_user.is_driver = False
            admin_user.has_car = False
            admin_user.driver_verification_status = 'pending'
            admin_user.save()
            users.append(admin_user)

        # Test driver
        driver, created = User.objects.get_or_create(
            email='hassan.ahmed.0@test.carwaan.pk',
            defaults={
                'username': 'hassan_ahmed',
                'password': make_password(test_password),
                'first_name': 'Hassan',
                'last_name': 'Ahmed',
                'gender': 'male',
                'is_verified': True,
                'is_driver': True,
                'has_car': True,
                'driver_verification_status': 'verified'
            }
        )
        if created:
            users.append(driver)
        else:
            # Update existing user to ensure has_car is True
            driver.has_car = True
            driver.is_driver = True
            driver.save()
            users.append(driver)

        # Test passenger
        passenger, created = User.objects.get_or_create(
            email='fatima.khan.1@test.carwaan.pk',
            defaults={
                'username': 'fatima_khan',
                'password': make_password(test_password),
                'first_name': 'Fatima',
                'last_name': 'Khan',
                'gender': 'female',
                'is_verified': True,
                'is_driver': False,
                'female_only_preference': True
            }
        )
        if created:
            users.append(passenger)
        else:
            users.append(passenger)

        # Test female driver for female-only rides
        female_driver, created = User.objects.get_or_create(
            email='aisha.malik.2@test.carwaan.pk',
            defaults={
                'username': 'aisha_malik',
                'password': make_password(test_password),
                'first_name': 'Aisha',
                'last_name': 'Malik',
                'gender': 'female',
                'is_verified': True,
                'is_driver': True,
                'has_car': True,
                'driver_verification_status': 'verified',
                'female_only_preference': True
            }
        )
        if created:
            users.append(female_driver)
        else:
            # Update existing user to ensure has_car is True
            female_driver.has_car = True
            female_driver.is_driver = True
            female_driver.save()
            users.append(female_driver)

        return users

    def create_test_vehicles(self, users):
        """Create test vehicles for drivers"""
        vehicles = []
        drivers = [user for user in users if user.is_driver]
        
        vehicle_data = [
            ('Toyota', 'Corolla', 2020, 'White', 'KHI-1234'),
            ('Honda', 'Civic', 2019, 'Silver', 'KHI-5678'),
            ('Suzuki', 'Alto', 2021, 'Red', 'KHI-9101')
        ]
        
        for i, driver in enumerate(drivers):
            # Check if driver already has a vehicle
            if not driver.vehicles.exists():
                try:
                    # Use different vehicle data for each driver
                    vehicle_info = vehicle_data[i % len(vehicle_data)]
                    make, model, year, color, license_plate = vehicle_info
                    
                    # Make license plate unique for each driver
                    unique_license = f"{license_plate[:-2]}{str(10 + i).zfill(2)}"
                    
                    vehicle = Vehicle.objects.create(
                        owner=driver,
                        make=make,
                        model=model,
                        year=year,
                        color=color,
                        license_plate=unique_license,
                        vehicle_type='sedan',
                        fuel_type='petrol',
                        total_seats=5,
                        available_seats_for_ride=3,
                        has_ac=True,
                        is_verified=True,
                        is_active=True
                    )
                    vehicles.append(vehicle)
                except Exception as e:
                    self.stdout.write(f'Warning: Could not create vehicle for {driver.username}: {e}')
        
        return vehicles

    def create_test_rides(self, users, vehicles):
        """Create test rides"""
        rides = []
        locations = list(Location.objects.all())
        karachi_timezone = pytz.timezone('Asia/Karachi')
        
        # Get drivers with vehicles
        drivers_with_vehicles = [user for user in users if user.is_driver and user.vehicles.exists()]
        
        if not drivers_with_vehicles or len(locations) < 2:
            return rides
            
        for i, driver in enumerate(drivers_with_vehicles):
            vehicle = driver.vehicles.first()
            
            # Create 3 test rides for each driver
            for j in range(3):
                if len(locations) >= 2:
                    pickup_location = random.choice(locations)
                    dropoff_location = random.choice([loc for loc in locations if loc != pickup_location])
                    
                    # Create rides for different times (ensure future dates)
                    base_time = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
                    departure_time = base_time + timedelta(days=j+1, hours=random.randint(1, 8))  # j+1 to ensure future dates
                    departure_time = karachi_timezone.localize(departure_time.replace(tzinfo=None))
                    
                    # Make female drivers create some female-only rides
                    female_only = False
                    if driver.gender == 'female':
                        female_only = j == 0 or random.choice([True, False])  # First ride is always female-only for female drivers
                    
                    try:
                        ride = Ride.objects.create(
                            driver=driver,
                            vehicle=vehicle,
                            departure_time=departure_time,
                            pickup_location=pickup_location.name,
                            dropoff_location=dropoff_location.name,
                            pickup_latitude=pickup_location.latitude,
                            pickup_longitude=pickup_location.longitude,
                            dropoff_latitude=dropoff_location.latitude,
                            dropoff_longitude=dropoff_location.longitude,
                            total_seats=3,
                            available_seats=random.randint(1, 3),
                            ride_type='commute',
                            status='scheduled',
                            gender_preference='female_only' if female_only else 'any',
                            notes=f"{'Female-only ' if female_only else ''}Daily commute from {pickup_location.name} to {dropoff_location.name}. Safe and comfortable ride.",
                            is_recurring=j == 0,  # Make first ride recurring
                            female_only_ride=female_only
                        )
                        
                        if ride.is_recurring:
                            ride.recurring_days = [0, 1, 2, 3, 4]  # Monday to Friday
                            ride.save()
                        
                        rides.append(ride)
                    except Exception as e:
                        self.stdout.write(f'Warning: Could not create ride: {e}')
        
        return rides
