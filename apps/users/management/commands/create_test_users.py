from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import date
import random

from apps.core.envconf import required_env

User = get_user_model()

class Command(BaseCommand):
    help = 'Create test driver and passenger accounts'

    def handle(self, *args, **options):
        test_password = required_env("TEST_USER_PASSWORD")
        self.stdout.write(self.style.SUCCESS('Creating test users...'))
        
        # Create Test Driver
        test_driver_data = {
            'username': 'test_driver',
            'email': 'testdriver@carwaan.com',
            'first_name': 'Ahmed',
            'last_name': 'Khan',
            'role': 'user',
            'gender': 'male',
            'phone': '+923001234567',
            'has_car': True,
            'car_model': 'Toyota Corolla 2020',
            'car_color': 'White',
            'license_plate': 'KHI-1234',
            'workplace': 'Tech Solutions Inc',
            'department': 'Software Development',
            'home_address': 'North Nazimabad, Block L, Karachi',
            'home_latitude': 24.9345,
            'home_longitude': 67.0361,
            'workplace_address': 'Clifton Block 9, Karachi',
            'workplace_latitude': 24.8138,
            'workplace_longitude': 67.0299,
            'bio': 'Experienced driver with 5+ years of safe driving. Prefer quiet rides but open to conversation.',
            'date_of_birth': date(1990, 5, 15),
            'is_verified': True,
            'average_rating': 4.7,
            'total_ratings': 23,
            'smoking_preference': 'no_smoking',
            'ac_preference': 'ac_required',
            'chat_preference': 'no_preference',
            'preferred_days': [0, 1, 2, 3, 4],  # Monday to Friday
            'preferred_departure_times': ['08:00', '17:30'],
            'preferred_music': ['classical', 'soft rock'],
            'payment_methods': ['cash', 'bank_transfer']
        }
        
        # Create Test Passenger
        test_passenger_data = {
            'username': 'test_passenger',
            'email': 'testpassenger@carwaan.com',
            'first_name': 'Fatima',
            'last_name': 'Ahmed',
            'role': 'user',
            'gender': 'female',
            'phone': '+923009876543',
            'has_car': False,
            'workplace': 'Karachi University',
            'department': 'Computer Science',
            'home_address': 'Gulshan-e-Iqbal, Block 13-D, Karachi',
            'home_latitude': 24.9207,
            'home_longitude': 67.0682,
            'workplace_address': 'University of Karachi, University Road',
            'workplace_latitude': 24.9470,
            'workplace_longitude': 67.1174,
            'bio': 'University student looking for reliable and safe rides to campus.',
            'date_of_birth': date(1998, 8, 22),
            'is_verified': True,
            'average_rating': 4.9,
            'total_ratings': 15,
            'smoking_preference': 'no_smoking',
            'ac_preference': 'ac_required',
            'chat_preference': 'chatty',
            'preferred_days': [0, 1, 2, 3, 4],  # Monday to Friday
            'preferred_departure_times': ['07:30', '16:00'],
            'preferred_music': ['pop', 'indie'],
            'payment_methods': ['cash', 'mobile_wallet']
        }
        
        # Create or update test driver
        try:
            driver = User.objects.get(username='test_driver')
            for key, value in test_driver_data.items():
                setattr(driver, key, value)
            driver.save()
            self.stdout.write(self.style.WARNING('Updated existing test_driver'))
        except User.DoesNotExist:
            driver = User.objects.create_user(password=test_password, **test_driver_data)
            self.stdout.write(self.style.SUCCESS('Created new test_driver'))
        
        # Create or update test passenger
        try:
            passenger = User.objects.get(username='test_passenger')
            for key, value in test_passenger_data.items():
                setattr(passenger, key, value)
            passenger.save()
            self.stdout.write(self.style.WARNING('Updated existing test_passenger'))
        except User.DoesNotExist:
            passenger = User.objects.create_user(password=test_password, **test_passenger_data)
            self.stdout.write(self.style.SUCCESS('Created new test_passenger'))
        
        # Additional test users with different profiles
        additional_users = [
            {
                'username': 'driver_male_south',
                'email': 'maledriver@carwaan.com',
                'first_name': 'Muhammad',
                'last_name': 'Ali',
                'role': 'user',
                'gender': 'male',
                'phone': '+923021111111',
                'has_car': True,
                'car_model': 'Honda Civic 2019',
                'car_color': 'Silver',
                'license_plate': 'KHI-5678',
                'workplace': 'Bank Alfalah',
                'department': 'Operations',
                'home_address': 'Defence Phase 2, Karachi',
                'home_latitude': 24.8059,
                'home_longitude': 67.0756,
                'workplace_address': 'I.I. Chundrigar Road, Karachi',
                'workplace_latitude': 24.8615,
                'workplace_longitude': 67.0099,
                'average_rating': 4.5,
                'total_ratings': 18,
            },
            {
                'username': 'passenger_female_east',
                'email': 'femalepassenger@carwaan.com',
                'first_name': 'Ayesha',
                'last_name': 'Siddiqui',
                'role': 'user',
                'gender': 'female',
                'phone': '+923032222222',
                'has_car': False,
                'workplace': 'Aga Khan Hospital',
                'department': 'Nursing',
                'home_address': 'Gulistan-e-Johar, Block 16, Karachi',
                'home_latitude': 24.9146,
                'home_longitude': 67.1378,
                'workplace_address': 'Stadium Road, Karachi',
                'workplace_latitude': 24.8912,
                'workplace_longitude': 67.0734,
                'average_rating': 4.8,
                'total_ratings': 12,
            }
        ]
        
        for user_data in additional_users:
            try:
                user = User.objects.get(username=user_data['username'])
                self.stdout.write(self.style.WARNING(f"User {user_data['username']} already exists"))
            except User.DoesNotExist:
                user = User.objects.create_user(password=test_password, **user_data)
                self.stdout.write(self.style.SUCCESS(f"Created {user_data['username']}"))
        
        self.stdout.write(self.style.SUCCESS('\n=== TEST ACCOUNTS CREATED ==='))
        self.stdout.write(self.style.SUCCESS('Main Test Accounts:'))
        self.stdout.write('Driver: test_driver (Ahmed Khan - Toyota Corolla)')
        self.stdout.write('Passenger: test_passenger (Fatima Ahmed - Student)')
        self.stdout.write(self.style.SUCCESS('\nAdditional Test Accounts:'))
        self.stdout.write('Driver: driver_male_south (Muhammad Ali - Honda Civic)')
        self.stdout.write('Passenger: passenger_female_east (Ayesha Siddiqui - Nurse)')
        self.stdout.write('Password for every account above: TEST_USER_PASSWORD from the environment.')
        self.stdout.write(self.style.SUCCESS('\nAll accounts have detailed profiles with:'))
        self.stdout.write('- Realistic Karachi addresses')
        self.stdout.write('- Car details (for drivers)')
        self.stdout.write('- Workplace information')
        self.stdout.write('- Preferences and ratings')
        self.stdout.write('- Contact information')
