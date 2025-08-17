#!/usr/bin/env python3
"""
Test and Validate Population Methods for Carwaan
Checks if all required fields are properly populated

Run with: python manage.py test_population_methods
"""

from django.core.management.base import BaseCommand
from apps.users.models import User, Vehicle
from apps.rides.models import Ride, Location
from django.core.management import call_command
from django.db import transaction
import io
import sys


class Command(BaseCommand):
    help = 'Test and validate the population methods for Carwaan'

    def add_arguments(self, parser):
        parser.add_argument(
            '--method',
            type=str,
            choices=['quick', 'full', 'both'],
            default='both',
            help='Which population method to test'
        )

    def handle(self, *args, **options):
        self.stdout.write('Testing population methods for Carwaan...')
        
        if options['method'] in ['quick', 'both']:
            self.test_quick_populate()
            
        if options['method'] in ['full', 'both']:
            self.test_full_populate()
            
        self.stdout.write(
            self.style.SUCCESS('Population method testing completed!')
        )

    def test_quick_populate(self):
        """Test the quick populate data method"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('TESTING QUICK POPULATE METHOD')
        self.stdout.write('='*50)
        
        # Clear existing test data
        self.clear_test_data()
        
        try:
            # Run quick populate
            self.stdout.write('Running populate_quick_data...')
            call_command('populate_quick_data')
            
            # Validate the created data
            self.validate_users()
            self.validate_vehicles()
            self.validate_rides()
            self.validate_female_only_functionality()
            
            self.stdout.write(
                self.style.SUCCESS('✅ Quick populate method passed all tests!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Quick populate method failed: {str(e)}')
            )

    def test_full_populate(self):
        """Test the full populate data method"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('TESTING FULL POPULATE METHOD')
        self.stdout.write('='*50)
        
        # Clear existing test data
        self.clear_test_data()
        
        try:
            # Run full populate with smaller numbers for testing
            self.stdout.write('Running populate_test_data...')
            call_command('populate_test_data', '--users', '10', '--rides', '20', '--clear')
            
            # Validate the created data
            self.validate_users()
            self.validate_vehicles()
            self.validate_rides()
            self.validate_female_only_functionality()
            
            self.stdout.write(
                self.style.SUCCESS('✅ Full populate method passed all tests!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Full populate method failed: {str(e)}')
            )

    def clear_test_data(self):
        """Clear test data"""
        self.stdout.write('Clearing existing test data...')
        
        # Delete in correct order to avoid foreign key constraints
        Ride.objects.all().delete()
        Vehicle.objects.all().delete()
        
        # Clear all users except superusers (keep only real admin accounts)
        User.objects.filter(is_superuser=False).delete()
        # Also clear test admin accounts that might have been created
        User.objects.filter(email__contains='test.carwaan').delete()
        User.objects.filter(email='admin@carwaan.pk').delete()
        
        Location.objects.all().delete()

    def validate_users(self):
        """Validate user data"""
        self.stdout.write('\n📊 Validating Users:')
        
        users = User.objects.all()
        total_users = users.count()
        
        if total_users == 0:
            raise Exception("No users were created")
            
        # Check for admin user
        admin_users = users.filter(role='admin').count()
        if admin_users == 0:
            raise Exception("No admin user was created")
            
        # Check for drivers
        drivers = users.filter(is_driver=True)
        driver_count = drivers.count()
        if driver_count == 0:
            raise Exception("No drivers were created")
        
        # Debug: Print all drivers
        self.stdout.write(f'  📋 Debug - All drivers:')
        for driver in drivers:
            self.stdout.write(f'     - {driver.username} (role: {driver.role}, has_car: {driver.has_car}, is_driver: {driver.is_driver})')
            
        # Check driver fields
        for driver in drivers:
            if not hasattr(driver, 'has_car'):
                raise Exception(f"Driver {driver.username} missing has_car field")
            # Only check has_car for non-admin users who are drivers
            if driver.role != 'admin' and driver.is_driver and not driver.has_car:
                raise Exception(f"Driver {driver.username} (role: {driver.role}) has has_car=False but is_driver=True")
            if driver.is_driver and driver.driver_verification_status != 'verified':
                raise Exception(f"Driver {driver.username} not verified")
                
        # Check for female users
        female_users = users.filter(gender='female')
        female_count = female_users.count()
        
        # Check female-only preferences
        female_with_preference = users.filter(
            gender='female', 
            female_only_preference=True
        ).count()
        
        self.stdout.write(f'  ✓ Total users: {total_users}')
        self.stdout.write(f'  ✓ Admin users: {admin_users}')
        self.stdout.write(f'  ✓ Drivers: {driver_count}')
        self.stdout.write(f'  ✓ Female users: {female_count}')
        self.stdout.write(f'  ✓ Female users with female-only preference: {female_with_preference}')

    def validate_vehicles(self):
        """Validate vehicle data"""
        self.stdout.write('\n🚗 Validating Vehicles:')
        
        vehicles = Vehicle.objects.all()
        total_vehicles = vehicles.count()
        
        if total_vehicles == 0:
            raise Exception("No vehicles were created")
            
        # Check vehicle fields
        for vehicle in vehicles:
            if not vehicle.is_verified:
                raise Exception(f"Vehicle {vehicle.license_plate} not verified")
            if not vehicle.is_active:
                raise Exception(f"Vehicle {vehicle.license_plate} not active")
            if not vehicle.owner.is_driver:
                raise Exception(f"Vehicle {vehicle.license_plate} owner is not a driver")
                
        active_vehicles = vehicles.filter(is_active=True).count()
        verified_vehicles = vehicles.filter(is_verified=True).count()
        
        self.stdout.write(f'  ✓ Total vehicles: {total_vehicles}')
        self.stdout.write(f'  ✓ Active vehicles: {active_vehicles}')
        self.stdout.write(f'  ✓ Verified vehicles: {verified_vehicles}')

    def validate_rides(self):
        """Validate ride data"""
        self.stdout.write('\n🚙 Validating Rides:')
        
        rides = Ride.objects.all()
        total_rides = rides.count()
        
        if total_rides == 0:
            raise Exception("No rides were created")
            
        # Check ride fields
        for ride in rides:
            if not hasattr(ride, 'female_only_ride'):
                raise Exception(f"Ride {ride.id} missing female_only_ride field")
            if not ride.driver.is_driver:
                raise Exception(f"Ride {ride.id} driver is not marked as driver")
            if not ride.vehicle:
                raise Exception(f"Ride {ride.id} has no vehicle assigned")
                
        # Check female-only rides
        female_only_rides = rides.filter(female_only_ride=True)
        female_only_count = female_only_rides.count()
        
        # Validate female-only rides have female drivers
        for ride in female_only_rides:
            if ride.driver.gender != 'female':
                raise Exception(f"Female-only ride {ride.id} has non-female driver")
                
        scheduled_rides = rides.filter(status='scheduled').count()
        
        self.stdout.write(f'  ✓ Total rides: {total_rides}')
        self.stdout.write(f'  ✓ Scheduled rides: {scheduled_rides}')
        self.stdout.write(f'  ✓ Female-only rides: {female_only_count}')

    def validate_female_only_functionality(self):
        """Validate female-only ride functionality"""
        self.stdout.write('\n👩 Validating Female-Only Functionality:')
        
        # Check if we have female drivers
        female_drivers = User.objects.filter(gender='female', is_driver=True)
        female_driver_count = female_drivers.count()
        
        if female_driver_count == 0:
            self.stdout.write('  ⚠️  No female drivers found - skipping female-only ride validation')
            return
            
        # Check female-only rides
        female_only_rides = Ride.objects.filter(female_only_ride=True)
        female_only_count = female_only_rides.count()
        
        # Test can_join_female_only_ride method
        female_users = User.objects.filter(gender='female')
        male_users = User.objects.filter(gender='male')
        
        for female_user in female_users[:3]:  # Test first 3
            if not female_user.can_join_female_only_ride():
                raise Exception(f"Female user {female_user.username} cannot join female-only rides")
                
        for male_user in male_users[:3]:  # Test first 3
            if male_user.can_join_female_only_ride():
                raise Exception(f"Male user {male_user.username} can join female-only rides (should not be allowed)")
        
        self.stdout.write(f'  ✓ Female drivers: {female_driver_count}')
        self.stdout.write(f'  ✓ Female-only rides: {female_only_count}')
        self.stdout.write(f'  ✓ can_join_female_only_ride() method working correctly')
        
        if female_only_count > 0:
            self.stdout.write(f'  ✅ Female-only functionality is working properly!')
        else:
            self.stdout.write(f'  ⚠️  No female-only rides created - check ride creation logic')
