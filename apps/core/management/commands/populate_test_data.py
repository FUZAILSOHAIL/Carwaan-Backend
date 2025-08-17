from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import random
import csv
import os
from decimal import Decimal
from django.conf import settings
from apps.users.models import User, Vehicle, PaymentMethod
from apps.rides.models import Ride, RidePassenger, RideReview, RideDirection, Location
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'Populate database with comprehensive test data for Carwaan'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=50,
            help='Number of users to create'
        )
        parser.add_argument(
            '--rides',
            type=int,
            default=100,
            help='Number of rides to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            self.clear_data()

        with transaction.atomic():
            self.stdout.write('Creating test data...')
            
            # Create admin user
            admin_user = self.create_admin_user()
            
            # Create locations
            locations = self.create_locations()
            
            # Create users
            users = self.create_users(options['users'])
            
            # Create vehicles
            vehicles = self.create_vehicles(users)
            
            # Create payment methods
            self.create_payment_methods(users)
            
            # Create ride directions
            directions = self.create_ride_directions()
            
            # Create rides
            rides = self.create_rides(users, vehicles, directions, options['rides'])
            
            # Create ride passengers
            self.create_ride_passengers(rides, users)
            
            # Create reviews
            self.create_reviews(rides, users)

        # Export user credentials to CSV
        self.export_credentials_to_csv(users)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created test data: '
                f'{len(users)} users, {len(vehicles)} vehicles, '
                f'{len(rides)} rides with passengers and reviews'
            )
        )

    def clear_data(self):
        """Clear existing test data"""
        RideReview.objects.all().delete()
        RidePassenger.objects.all().delete()
        Ride.objects.all().delete()
        Vehicle.objects.all().delete()
        PaymentMethod.objects.all().delete()
        Location.objects.all().delete()
        RideDirection.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def create_admin_user(self):
        """Create admin user"""
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@carwaan.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'email_verified': True,
                'password': make_password('admin123'),
                'gender': 'male',
                'phone': '+923001234567',
                'workplace': 'Carwaan Technologies',
                'department': 'Administration',
                'has_car': False,
                'is_driver': False,
                'driver_verification_status': 'pending'
            }
        )
        if created:
            self.stdout.write(f'Created admin user: {admin.username}')
        else:
            # Ensure existing admin is not a driver
            admin.is_driver = False
            admin.has_car = False
            admin.driver_verification_status = 'pending'
            admin.save()
            
        return admin

    def create_locations(self):
        """Create common locations in Karachi"""
        karachi_locations = [
            {'name': 'Karachi University', 'lat': 24.9474, 'lng': 67.1339, 'type': 'university'},
            {'name': 'NED University', 'lat': 24.9230, 'lng': 67.1085, 'type': 'university'},
            {'name': 'IBA Karachi', 'lat': 24.8506, 'lng': 67.0354, 'type': 'university'},
            {'name': 'LUMS Karachi Campus', 'lat': 24.8607, 'lng': 67.0011, 'type': 'university'},
            {'name': 'Packages Mall', 'lat': 24.8077, 'lng': 67.0277, 'type': 'landmark'},
            {'name': 'Lucky One Mall', 'lat': 24.8845, 'lng': 67.0567, 'type': 'landmark'},
            {'name': 'Dolmen Mall Clifton', 'lat': 24.8138, 'lng': 67.0299, 'type': 'landmark'},
            {'name': 'Ocean Mall', 'lat': 24.8202, 'lng': 67.0334, 'type': 'landmark'},
            {'name': 'State Bank of Pakistan', 'lat': 24.8456, 'lng': 67.0282, 'type': 'workplace'},
            {'name': 'KPT Building', 'lat': 24.8394, 'lng': 67.0084, 'type': 'workplace'},
            {'name': 'PTCL Tower', 'lat': 24.8614, 'lng': 67.0099, 'type': 'workplace'},
            {'name': 'Jinnah International Airport', 'lat': 24.9056, 'lng': 67.1608, 'type': 'landmark'},
            {'name': 'Saddar Bus Station', 'lat': 24.8597, 'lng': 67.0097, 'type': 'landmark'},
            {'name': 'Gulshan-e-Iqbal', 'lat': 24.9207, 'lng': 67.0832, 'type': 'landmark'},
            {'name': 'Defence Phase 2', 'lat': 24.8059, 'lng': 67.0761, 'type': 'landmark'},
        ]

        locations = []
        for loc_data in karachi_locations:
            location, created = Location.objects.get_or_create(
                name=loc_data['name'],
                defaults={
                    'latitude': loc_data['lat'],
                    'longitude': loc_data['lng'],
                    'address': f"{loc_data['name']}, Karachi",
                    'city': 'Karachi',
                    'state': 'Sindh',
                    'is_university': loc_data['type'] == 'university',
                    'is_workplace': loc_data['type'] == 'workplace',
                    'is_landmark': loc_data['type'] == 'landmark',
                }
            )
            locations.append(location)
        
        return locations

    def create_users(self, count):
        """Create test users with Pakistani names"""
        pakistani_names = {
            'male': [
                ('Ahmed', 'Ali'), ('Muhammad', 'Hassan'), ('Ali', 'Khan'), 
                ('Usman', 'Ahmad'), ('Shahid', 'Iqbal'), ('Tariq', 'Mahmood'),
                ('Kamran', 'Sheikh'), ('Imran', 'Khan'), ('Fahad', 'Malik'),
                ('Bilal', 'Ahmed'), ('Saqib', 'Raza'), ('Adnan', 'Siddiqui'),
                ('Faisal', 'Sheikh'), ('Rizwan', 'Ali'), ('Zubair', 'Ahmed'),
                ('Asad', 'Butt'), ('Naveed', 'Akhtar'), ('Waqas', 'Hussain'),
                ('Shoaib', 'Malik'), ('Kashif', 'Mughal')
            ],
            'female': [
                ('Fatima', 'Khan'), ('Ayesha', 'Ahmed'), ('Sana', 'Ali'),
                ('Mariam', 'Sheikh'), ('Zara', 'Malik'), ('Nida', 'Hassan'),
                ('Farah', 'Iqbal'), ('Samina', 'Khatoon'), ('Rabia', 'Siddiqui'),
                ('Hina', 'Tariq'), ('Shazia', 'Begum'), ('Noor', 'Fatima'),
                ('Saira', 'Khan'), ('Rubina', 'Ahmed'), ('Mehreen', 'Ali'),
                ('Kiran', 'Butt'), ('Bushra', 'Akhtar'), ('Sadia', 'Hussain'),
                ('Nazia', 'Malik'), ('Fozia', 'Mughal')
            ]
        }

        workplaces = [
            'Pakistan State Oil', 'Unilever Pakistan', 'Packages Limited',
            'Engro Corporation', 'Lucky Cement', 'Habib Bank Limited',
            'United Bank Limited', 'MCB Bank', 'Telenor Pakistan',
            'Jazz (Mobilink)', 'K-Electric', 'PTCL', 'Systems Limited',
            'NetSol Technologies', 'TRG Pakistan', 'Dawlance', 'Haier Pakistan',
            'Suzuki Motors', 'Honda Atlas Cars', 'Toyota Indus Motor'
        ]

        departments = [
            'Engineering', 'Marketing', 'Finance', 'Human Resources',
            'Operations', 'IT', 'Sales', 'Customer Service', 'Quality Assurance',
            'Research & Development', 'Administration', 'Procurement'
        ]

        karachi_areas = [
            'Saddar', 'Gulshan-e-Iqbal', 'Defence (DHA)', 'Clifton',
            'Nazimabad', 'North Nazimabad', 'Gulberg', 'Malir', 'Korangi',
            'Landhi', 'Shah Faisal Colony', 'Garden', 'Keamari',
            'Orangi Town', 'New Karachi', 'Surjani Town', 'Scheme 33',
            'Gulistan-e-Johar', 'Pechs', 'Bahadurabad'
        ]

        users = []
        for i in range(count):
            gender = random.choice(['male', 'female'])
            first_name, last_name = random.choice(pakistani_names[gender])
            
            # Create unique username and email
            username = f"{first_name.lower()}.{last_name.lower()}{i}"
            email = f"{username}@test.com"
            
            # Generate phone number
            phone = f"+9230{random.randint(10000000, 99999999)}"
            
            # Determine driver status before creating user
            has_car = random.choice([True, False, False])  # 33% have cars
            is_driver = True if has_car else random.choice([True, False])
            
            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=make_password('password123'),
                gender=gender,
                phone=phone,
                is_verified=True,
                email_verified=True,
                workplace=random.choice(workplaces),
                department=random.choice(departments),
                has_car=has_car,
                bio=f"Hi! I'm {first_name}, working at {random.choice(workplaces)}. Love carpooling to save environment and make new friends!",
                address=f"House #{random.randint(1, 500)}, {random.choice(karachi_areas)}, Karachi",
                home_address=f"{random.choice(karachi_areas)}, Karachi",
                workplace_address=f"{random.choice(workplaces)}, {random.choice(karachi_areas)}, Karachi",
                
                # Driver verification
                is_driver=is_driver,
                driver_verification_status='verified' if is_driver else 'pending',
                
                # Ratings
                average_rating=round(random.uniform(3.5, 5.0), 2),
                driver_rating=round(random.uniform(3.5, 5.0), 2),
                passenger_rating=round(random.uniform(3.5, 5.0), 2),
                total_ratings=random.randint(5, 50),
                total_driver_reviews=random.randint(0, 25),
                total_passenger_reviews=random.randint(0, 25),
                
                # Activity stats
                total_rides_offered=random.randint(0, 30),
                total_rides_taken=random.randint(0, 50),
                
                # Preferences
                smoking_preference=random.choice(['no_smoking', 'smoking_allowed', 'no_preference']),
                ac_preference=random.choice(['ac_required', 'no_ac', 'no_preference']),
                chat_preference=random.choice(['chatty', 'quiet', 'no_preference']),
                female_only_preference=gender == 'female' and random.choice([True, False]),
            )
            
            users.append(user)
            
            if i % 10 == 0:
                self.stdout.write(f'Created {i} users...')
        
        return users

    def create_vehicles(self, users):
        """Create vehicles for users who have cars"""
        car_makes_models = [
            ('Toyota', ['Corolla', 'Vitz', 'Prius', 'Camry', 'Yaris']),
            ('Honda', ['Civic', 'City', 'Accord', 'BR-V', 'Vezel']),
            ('Suzuki', ['Cultus', 'Wagon R', 'Swift', 'Bolan', 'Alto']),
            ('Nissan', ['Sunny', 'Note', 'X-Trail', 'Juke', 'Dayz']),
            ('Hyundai', ['Elantra', 'Tucson', 'Santro', 'Accent', 'Sonata']),
            ('KIA', ['Picanto', 'Sportage', 'Cerato', 'Stonic', 'Sorento']),
            ('Daihatsu', ['Mira', 'Move', 'Hijet', 'Terios', 'Charade']),
        ]

        colors = [
            'White', 'Silver', 'Black', 'Red', 'Blue', 'Gray', 
            'Green', 'Brown', 'Gold', 'Maroon'
        ]

        vehicles = []
        car_owners = [user for user in users if user.has_car]
        
        for user in car_owners:
            # Some users might have multiple cars
            num_cars = random.choices([1, 2], weights=[0.8, 0.2], k=1)[0]
            
            for i in range(num_cars):
                make, models = random.choice(car_makes_models)
                model = random.choice(models)
                year = random.randint(2010, 2024)
                color = random.choice(colors)
                
                # Generate license plate in Pakistani format
                letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
                numbers = random.randint(100, 9999)
                license_plate = f"{letters}-{numbers}"
                
                vehicle = Vehicle.objects.create(
                    owner=user,
                    make=make,
                    model=model,
                    year=year,
                    color=color,
                    license_plate=license_plate,
                    vehicle_type=random.choice(['sedan', 'hatchback', 'suv', 'crossover']),
                    fuel_type=random.choice(['petrol', 'diesel', 'cng', 'hybrid']),
                    engine_capacity=random.choice(['1000cc', '1300cc', '1500cc', '1600cc', '1800cc', '2000cc']),
                    fuel_average=round(random.uniform(8.0, 20.0), 2),
                    total_seats=random.choice([4, 5, 7]),
                    available_seats_for_ride=random.randint(1, 4),
                    has_ac=random.choice([True, False]),
                    ac_type=random.choice(['none', 'standard', 'climate_control']),
                    has_music_system=random.choice([True, False]),
                    has_phone_charger=random.choice([True, False]),
                    smoking_allowed=random.choice([True, False]),
                    is_verified=True,  # Always verified for testing
                    insurance_valid=True,
                    fitness_certificate_valid=True,
                    verification_status='verified',  # Always verified for testing
                    is_active=True,
                    is_primary=i == 0,  # First car is primary
                    notes=f"Well-maintained {make} {model}. Perfect for comfortable carpooling!"
                )
                
                vehicles.append(vehicle)
        
        return vehicles

    def create_payment_methods(self, users):
        """Create payment methods for users"""
        payment_types = ['card', 'easypaisa', 'jazzcash', 'bank_transfer']
        card_brands = ['Visa', 'MasterCard', 'UnionPay']
        
        for user in users:
            # Each user gets 1-3 payment methods
            num_methods = random.randint(1, 3)
            
            for _ in range(num_methods):
                payment_type = random.choice(payment_types)
                
                if payment_type == 'card':
                    PaymentMethod.objects.create(
                        user=user,
                        type=payment_type,
                        holder_name=f"{user.first_name} {user.last_name}",
                        last_four=str(random.randint(1000, 9999)),
                        brand=random.choice(card_brands),
                        expiry_month=random.randint(1, 12),
                        expiry_year=random.randint(2024, 2030),
                        is_default=random.choice([True, False])
                    )
                elif payment_type in ['easypaisa', 'jazzcash']:
                    PaymentMethod.objects.create(
                        user=user,
                        type=payment_type,
                        holder_name=f"{user.first_name} {user.last_name}",
                        phone_number=f"+9230{random.randint(10000000, 99999999)}",
                        is_default=random.choice([True, False])
                    )
                else:  # bank_transfer
                    PaymentMethod.objects.create(
                        user=user,
                        type=payment_type,
                        holder_name=f"{user.first_name} {user.last_name}",
                        account_number=str(random.randint(1000000000, 9999999999)),
                        bank_name=random.choice(['HBL', 'UBL', 'MCB', 'Allied Bank', 'Bank Alfalah']),
                        is_default=random.choice([True, False])
                    )

    def create_ride_directions(self):
        """Create common ride directions in Karachi"""
        directions_data = [
            {
                'name': 'University to Defence',
                'start_area': 'University Road',
                'end_area': 'Defence (DHA)',
                'waypoints': ['Shahrah-e-Faisal', 'Nursery', 'Teen Talwar'],
                'average_distance_km': 14.2,
                'average_duration_minutes': 40
            },
            {
                'name': 'Gulshan to Clifton',
                'start_area': 'Gulshan-e-Iqbal',
                'end_area': 'Clifton',
                'waypoints': ['Rashid Minhas Road', 'Millennium Mall', 'Sea View'],
                'average_distance_km': 16.8,
                'average_duration_minutes': 45
            },
            {
                'name': 'Nazimabad to Saddar',
                'start_area': 'Nazimabad',
                'end_area': 'Saddar',
                'waypoints': ['Nishtar Road', 'Burns Road', 'Empress Market'],
                'average_distance_km': 11.5,
                'average_duration_minutes': 35
            },
            {
                'name': 'Malir to I.I. Chundrigar',
                'start_area': 'Malir',
                'end_area': 'I.I. Chundrigar Road',
                'waypoints': ['Shahrah-e-Faisal', 'Airport', 'Civic Centre'],
                'average_distance_km': 22.1,
                'average_duration_minutes': 55
            },
            {
                'name': 'North Karachi to Gulberg',
                'start_area': 'North Karachi',
                'end_area': 'Gulberg',
                'waypoints': ['Sohrab Goth', 'New Karachi', 'Johar'],
                'average_distance_km': 18.3,
                'average_duration_minutes': 50
            }
        ]

        directions = []
        for direction_data in directions_data:
            direction = RideDirection.objects.create(**direction_data)
            directions.append(direction)
        
        return directions

    def create_rides(self, users, vehicles, directions, count):
        """Create test rides"""
        ride_types = ['commute', 'event', 'social', 'errand', 'other']
        statuses = ['scheduled', 'in_progress', 'completed', 'cancelled']
        gender_preferences = ['any', 'male_only', 'female_only', 'family_only']
        
        karachi_areas = [
            'Saddar', 'Gulshan-e-Iqbal', 'Defence (DHA)', 'Clifton',
            'Nazimabad', 'North Nazimabad', 'Gulberg', 'Malir', 'Korangi',
            'University Road', 'Shahrah-e-Faisal', 'Tariq Road'
        ]

        rides = []
        drivers_with_vehicles = [v.owner for v in vehicles if v.is_active]
        
        for i in range(count):
            if not drivers_with_vehicles:
                break
                
            driver = random.choice(drivers_with_vehicles)
            driver_vehicles = [v for v in vehicles if v.owner == driver and v.is_active]
            
            if not driver_vehicles:
                continue
                
            vehicle = random.choice(driver_vehicles)
            
            # Generate realistic departure time (always in the future)
            departure_time = timezone.now() + timedelta(
                days=random.randint(0, 30),  # Only future dates
                hours=random.choice([7, 8, 9, 17, 18, 19]),  # Common commute times
                minutes=random.choice([0, 15, 30, 45])
            )
            
            pickup_area = random.choice(karachi_areas)
            dropoff_area = random.choice([area for area in karachi_areas if area != pickup_area])
            
            ride = Ride.objects.create(
                driver=driver,
                vehicle=vehicle,
                departure_time=departure_time,
                pickup_location=f"{pickup_area}, Karachi",
                dropoff_location=f"{dropoff_area}, Karachi",
                total_seats=vehicle.available_seats_for_ride,  # Use vehicle's available seats for ride
                available_seats=random.randint(1, vehicle.available_seats_for_ride),  # Ensure available <= vehicle capacity
                gender_preference=random.choice(gender_preferences),
                female_only_ride=driver.gender == 'female' and random.choice([True, False]),
                status=random.choice(statuses),
                notes=f"Comfortable ride from {pickup_area} to {dropoff_area}. {random.choice(['AC available', 'Music system', 'Phone charging', 'Quiet ride', 'Friendly conversation welcome'])}!",
                
                # Enhanced fields
                ride_type=random.choice(ride_types),
                route_description=f"Taking main route via {random.choice(['Shahrah-e-Faisal', 'University Road', 'Rashid Minhas Road'])}",
                price_per_seat=Decimal(str(random.randint(50, 300))),
                cost_splitting=random.choice([True, False]),
                calculated_fare=Decimal(str(random.randint(100, 500))),
                
                # Route info
                estimated_distance_km=round(random.uniform(5.0, 50.0), 2),
                estimated_duration_minutes=random.randint(15, 90),
                
                # Coordinates (approximate for Karachi areas)
                pickup_latitude=24.8607 + random.uniform(-0.5, 0.5),
                pickup_longitude=67.0011 + random.uniform(-0.5, 0.5),
                dropoff_latitude=24.8607 + random.uniform(-0.5, 0.5),
                dropoff_longitude=67.0011 + random.uniform(-0.5, 0.5),
                
                # Preferences
                time_flexibility_minutes=random.choice([5, 10, 15, 30]),
                is_workplace_ride=random.choice([True, False]),
                
                # Ratings
                average_rating=round(random.uniform(3.5, 5.0), 2),
                total_ratings=random.randint(0, 20),
                
                # Recurring rides
                is_recurring=random.choice([True, False]),
                recurring_days=[random.randint(0, 6) for _ in range(random.randint(1, 5))] if random.choice([True, False]) else None,
                
                # Gender stats
                current_male_passengers=random.randint(0, 2),
                current_female_passengers=random.randint(0, 2),
            )
            
            # Set ride direction
            if directions:
                ride.ride_direction = random.choice(directions)
                ride.save()
            
            rides.append(ride)
            
            if i % 20 == 0:
                self.stdout.write(f'Created {i} rides...')
        
        return rides

    def create_ride_passengers(self, rides, users):
        """Create ride passengers"""
        for ride in rides:
            if ride.status in ['completed', 'in_progress']:
                # Add some passengers to completed/ongoing rides
                available_passengers = [u for u in users if u != ride.driver]
                num_passengers = random.randint(0, min(ride.total_seats, 3))
                
                selected_passengers = random.sample(available_passengers, 
                                                   min(num_passengers, len(available_passengers)))
                
                for passenger in selected_passengers:
                    RidePassenger.objects.create(
                        ride=ride,
                        passenger=passenger,
                        status='confirmed',
                        passenger_pickup_location=ride.pickup_location,
                        passenger_dropoff_location=ride.dropoff_location,
                        individual_fare=ride.price_per_seat,
                        joined_at=ride.departure_time - timedelta(hours=random.randint(1, 24)),
                        relationship=random.choice(['colleague', 'friend', 'family', 'acquaintance']),
                        contribution_amount=ride.price_per_seat,
                        has_contributed=random.choice([True, False])
                    )

    def create_reviews(self, rides, users):
        """Create ride reviews"""
        for ride in rides:
            if ride.status == 'completed':
                passengers = RidePassenger.objects.filter(ride=ride, status='confirmed')
                
                # Driver reviews passengers
                for ride_passenger in passengers:
                    if random.choice([True, False]):  # 50% chance of review
                        RideReview.objects.create(
                            ride=ride,
                            reviewer=ride.driver,
                            reviewee=ride_passenger.passenger,
                            review_type='driver_to_passenger',
                            rating=random.randint(3, 5),
                            comment=random.choice([
                                "Great passenger! Very punctual and friendly.",
                                "Pleasant journey. Would recommend!",
                                "Nice conversation throughout the ride.",
                                "Respectful and well-behaved passenger.",
                                "Perfect passenger. No complaints!"
                            ])
                        )
                
                # Passengers review driver
                for ride_passenger in passengers:
                    if random.choice([True, False]):  # 50% chance of review
                        RideReview.objects.create(
                            ride=ride,
                            reviewer=ride_passenger.passenger,
                            reviewee=ride.driver,
                            review_type='passenger_to_driver',
                            rating=random.randint(3, 5),
                            comment=random.choice([
                                "Excellent driver! Safe and comfortable ride.",
                                "Very professional and punctual.",
                                "Smooth ride with great conversation.",
                                "Highly recommended driver!",
                                "Perfect timing and clean car.",
                                "Great driving skills and friendly nature."
                            ])
                        )

    def export_credentials_to_csv(self, users):
        """Export user credentials to CSV file"""
        output_file = os.path.join(settings.BASE_DIR, 'test_user_credentials.csv')
        
        self.stdout.write(f"Exporting user credentials to: {output_file}")
        
        # Create CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'username', 'email', 'password', 'first_name', 'last_name', 
                'phone', 'gender', 'role', 'is_driver', 'driver_verification_status',
                'has_car', 'is_active', 'is_verified', 'user_type_for_login'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for user in users:
                # All test users use the same password for easy testing
                password = 'testpass123' if user.username != 'admin' else 'admin123'
                
                # Determine user type for login purposes
                if user.role == 'admin':
                    user_type = 'admin'
                elif user.is_driver and user.driver_verification_status == 'verified':
                    user_type = 'driver'
                else:
                    user_type = 'passenger'
                
                writer.writerow({
                    'username': user.username,
                    'email': user.email,
                    'password': password,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone or '',
                    'gender': user.gender or '',
                    'role': user.role,
                    'is_driver': user.is_driver,
                    'driver_verification_status': user.driver_verification_status,
                    'has_car': user.has_car,
                    'is_active': user.is_active,
                    'is_verified': user.is_verified,
                    'user_type_for_login': user_type
                })
        
        self.stdout.write(
            self.style.SUCCESS(
                f'User credentials exported to {output_file}'
            )
        )
        
        # Print quick reference for testing
        self.stdout.write(self.style.WARNING('\n=== QUICK TEST CREDENTIALS ==='))
        
        # Admin user
        admin_user = next((u for u in users if u.role == 'admin'), None)
        if admin_user:
            self.stdout.write(f"🔑 ADMIN: {admin_user.username} / admin123")
        
        # Sample drivers
        drivers = [u for u in users if u.is_driver and u.driver_verification_status == 'verified'][:3]
        if drivers:
            self.stdout.write("🚗 DRIVERS:")
            for driver in drivers:
                self.stdout.write(f"   {driver.username} / testpass123")
        
        # Sample passengers
        passengers = [u for u in users if not u.is_driver][:3]
        if passengers:
            self.stdout.write("👥 PASSENGERS:")
            for passenger in passengers:
                self.stdout.write(f"   {passenger.username} / testpass123")
        
        self.stdout.write(f"\n📄 Full credentials list: {output_file}")
        self.stdout.write("💡 All users (except admin) use password: testpass123")
