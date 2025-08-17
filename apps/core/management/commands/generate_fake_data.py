#!/usr/bin/env python3
"""
Django Management Command to Generate Fake Data for Carwaan App
Localized for Karachi, Pakistan

This script generates realistic test data including:
- Users with Pakistani names and Karachi addresses
- Vehicles with Pakistani specifications
- Rides between real Karachi locations
- Bookings and related data

Run with: python manage.py generate_fake_data [--users 50] [--rides 100]
"""

import random
import secrets
from datetime import datetime, timedelta, time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from apps.users.models import User, Vehicle
from apps.rides.models import Ride, Location, RoutePoint, RidePassenger, RideRequest
import pytz

class Command(BaseCommand):
    help = 'Generate fake data for testing - localized for Karachi, Pakistan'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=50, help='Number of users to create')
        parser.add_argument('--rides', type=int, default=100, help='Number of rides to create')
        parser.add_argument('--clear', action='store_true', help='Clear existing data first')

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        import math
        R = 6371  # Earth's radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            self.clear_data()

        self.stdout.write('Generating fake data for Karachi, Pakistan...')
        
        # Generate data
        users = self.create_users(options['users'])
        vehicles = self.create_vehicles(users)
        locations = self.create_locations()
        rides = self.create_rides(users, vehicles, locations, options['rides'])
        passengers = self.create_ride_passengers(users, rides)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated:\n'
                f'- {len(users)} users\n'
                f'- {len(vehicles)} vehicles\n'
                f'- {len(locations)} locations\n'
                f'- {len(rides)} rides\n'
                f'- {len(passengers)} ride passengers'
            )
        )

    def clear_data(self):
        """Clear existing test data"""
        RidePassenger.objects.all().delete()
        RideRequest.objects.all().delete()
        Ride.objects.all().delete()
        Vehicle.objects.all().delete()
        User.objects.filter(email__contains='test.carwaan').delete()
        Location.objects.all().delete()

    def create_users(self, count):
        """Create realistic Pakistani users"""
        
        # Pakistani male names
        male_first_names = [
            'Muhammad', 'Ahmed', 'Ali', 'Hassan', 'Hussain', 'Omar', 'Usman', 'Bilal',
            'Fahad', 'Shahzad', 'Asim', 'Tariq', 'Imran', 'Zubair', 'Kamran', 'Salman',
            'Adnan', 'Waseem', 'Naeem', 'Amin', 'Saad', 'Hamza', 'Yusuf', 'Ibrahim'
        ]
        
        # Pakistani female names
        female_first_names = [
            'Fatima', 'Aisha', 'Khadija', 'Zainab', 'Maryam', 'Amna', 'Sara', 'Hira',
            'Bushra', 'Sadia', 'Nadia', 'Farah', 'Sana', 'Rabia', 'Rubina', 'Samina',
            'Shazia', 'Nazia', 'Tahira', 'Uzma', 'Shaista', 'Nasreen', 'Lubna', 'Saima'
        ]
        
        # Pakistani last names
        last_names = [
            'Khan', 'Ahmed', 'Ali', 'Sheikh', 'Malik', 'Qureshi', 'Siddiqui', 'Chaudhry',
            'Butt', 'Hussain', 'Awan', 'Rajput', 'Bhatti', 'Mughal', 'Afridi', 'Baloch',
            'Sindhi', 'Pathan', 'Janjua', 'Gillani', 'Hashmi', 'Mirza', 'Shah', 'Dar'
        ]
        
        # Karachi areas for addresses
        karachi_areas = [
            'DHA Phase 1', 'DHA Phase 2', 'DHA Phase 5', 'DHA Phase 6', 'DHA Phase 8',
            'Clifton Block 1', 'Clifton Block 2', 'Clifton Block 5', 'Clifton Block 8',
            'Gulshan-e-Iqbal Block 1', 'Gulshan-e-Iqbal Block 13A', 'Gulshan-e-Iqbal Block 2',
            'Nazimabad Block 1', 'Nazimabad Block 2', 'Nazimabad Block 4',
            'North Nazimabad Block A', 'North Nazimabad Block B', 'North Nazimabad Block L',
            'Gulberg Town', 'Johar Town', 'Malir', 'Shah Faisal Colony',
            'Korangi Industrial Area', 'Landhi', 'Model Colony', 'PECHS Block 2',
            'PECHS Block 6', 'Bahadurabad', 'Tariq Road', 'Saddar',
            'II Chundrigar Road', 'Karsaz', 'Tipu Sultan Road', 'University Road',
            'Hassan Square', 'Soldier Bazaar', 'Garden East', 'Garden West',
            'FB Area Block 8', 'FB Area Block 9', 'FB Area Block 16',
            'Shahrah-e-Faisal', 'Stadium Road', 'Shahra-e-Quaideen'
        ]
        
        # Pakistani companies/workplaces
        workplaces = [
            'Karachi Stock Exchange', 'Port Qasim Authority', 'Karachi Port Trust',
            'Pakistan International Airlines', 'National Bank of Pakistan', 'Habib Bank Limited',
            'United Bank Limited', 'MCB Bank', 'Allied Bank', 'Standard Chartered Pakistan',
            'Unilever Pakistan', 'Nestle Pakistan', 'Engro Corporation', 'Lucky Cement',
            'Pakistan Petroleum Limited', 'Oil & Gas Development Company',
            'Pakistan State Oil', 'Shell Pakistan', 'Total Parco Pakistan',
            'University of Karachi', 'NED University', 'IBA Karachi', 'Aga Khan University',
            'Bahria University', 'PAF-KIET', 'Sindh University', 'FAST-NU Karachi',
            'Adamjee Cantonment College', 'DJ Science College', 'Government College',
            'St. Patricks High School', 'Karachi Grammar School', 'City School',
            'Beaconhouse School System', 'The Lyceum School'
        ]
        
        # Pakistani phone number prefixes
        phone_prefixes = ['0300', '0301', '0302', '0303', '0304', '0305', '0306', '0307', '0308', '0309',
                         '0310', '0311', '0312', '0313', '0314', '0315', '0316', '0317', '0318', '0320',
                         '0321', '0322', '0323', '0324', '0325', '0330', '0331', '0332', '0333', '0334', '0335']
        
        users = []
        
        for i in range(count):
            # Random gender
            gender = random.choice(['male', 'female'])
            
            # Generate name based on gender
            if gender == 'male':
                first_name = random.choice(male_first_names)
            else:
                first_name = random.choice(female_first_names)
                
            last_name = random.choice(last_names)
            full_name = f"{first_name} {last_name}"
            
            # Generate CNIC (Pakistani ID format: 42101-1234567-1)
            # 42101 is Karachi's code
            cnic_part1 = "42101"
            cnic_part2 = f"{random.randint(1000000, 9999999)}"
            cnic_part3 = str(random.randint(1, 9))
            cnic = f"{cnic_part1}-{cnic_part2}-{cnic_part3}"
            
            # Generate phone number
            phone_prefix = random.choice(phone_prefixes)
            phone_suffix = f"{random.randint(1000000, 9999999)}"
            phone = f"+92{phone_prefix[1:]}{phone_suffix}"
            
            # Email
            email = f"{first_name.lower()}.{last_name.lower()}.{i}@test.carwaan.pk"
            
            # Address in Karachi
            area = random.choice(karachi_areas)
            house_no = random.randint(1, 999)
            address = f"House {house_no}, {area}, Karachi"
            
            # Date of birth (18-60 years old)
            birth_year = random.randint(1964, 2006)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            date_of_birth = datetime(birth_year, birth_month, birth_day).date()
            
            # Random verification status
            is_driver = random.choice([True, False])
            driver_verification_status = 'verified' if is_driver and random.choice([True, False]) else 'pending'
            
            # Generate coordinates for Karachi (approximate bounds)
            # Karachi roughly: lat 24.7-25.0, lng 66.9-67.3
            home_latitude = round(random.uniform(24.7, 25.0), 6)
            home_longitude = round(random.uniform(66.9, 67.3), 6)
            workplace_latitude = round(random.uniform(24.7, 25.0), 6)
            workplace_longitude = round(random.uniform(66.9, 67.3), 6)
            
            user = User.objects.create(
                username=f"user_{i}_{first_name.lower()}",
                email=email,
                password=make_password('testpass123'),
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                gender=gender,
                phone=phone,
                cnic=cnic,
                cnic_number=cnic,
                date_of_birth=date_of_birth,
                address=address,
                home_address=address,
                home_latitude=home_latitude,
                home_longitude=home_longitude,
                workplace=random.choice(workplaces),
                workplace_address=f"{random.choice(workplaces)}, {random.choice(karachi_areas)}, Karachi",
                workplace_latitude=workplace_latitude,
                workplace_longitude=workplace_longitude,
                is_verified=True,
                email_verified=True,
                is_driver=is_driver,
                driver_verification_status=driver_verification_status,
                average_rating=round(random.uniform(3.5, 5.0), 2),
                total_ratings=random.randint(0, 50),
                smoking_preference=random.choice(['no_smoking', 'smoking_allowed', 'no_preference']),
                ac_preference=random.choice(['ac_required', 'no_ac', 'no_preference']),
                chat_preference=random.choice(['chatty', 'quiet', 'no_preference']),
                preferred_days=[random.randint(0, 6) for _ in range(random.randint(3, 7))],
                preferred_departure_times=[f"{random.randint(6, 22):02d}:{random.choice(['00', '15', '30', '45'])}" 
                                         for _ in range(random.randint(2, 4))]
            )
            users.append(user)
            
        self.stdout.write(f'Created {len(users)} users')
        return users
    
    def create_vehicles(self, users):
        """Create vehicles for driver users"""
        
        # Pakistani car makes and models
        car_data = [
            ('Toyota', ['Corolla', 'Camry', 'Vitz', 'Prius', 'Hilux', 'Fortuner']),
            ('Honda', ['Civic', 'City', 'Accord', 'BR-V', 'HR-V', 'Vezel']),
            ('Suzuki', ['Cultus', 'Swift', 'Wagon R', 'Alto', 'Bolan', 'Ravi']),
            ('Hyundai', ['Elantra', 'Tucson', 'Santro', 'Accent']),
            ('KIA', ['Picanto', 'Sportage', 'Stonic', 'Cerato']),
            ('Nissan', ['Sunny', 'X-Trail', 'Juke', 'Note']),
            ('Daihatsu', ['Mira', 'Move', 'Cuore', 'Hijet']),
            ('Mitsubishi', ['Lancer', 'Pajero', 'Outlander']),
            ('Changan', ['Alsvin', 'Karvaan', 'M8', 'M9'])
        ]
        
        # Pakistani license plate patterns: ABC-123, KHI-1234, etc.
        city_codes = ['KHI', 'KAR', 'ABC', 'DEF', 'GHI', 'JKL', 'MNO', 'PQR']
        
        colors = ['White', 'Silver', 'Black', 'Blue', 'Red', 'Grey', 'Brown', 'Green']
        
        vehicles = []
        drivers = [user for user in users if user.is_driver and user.driver_verification_status == 'verified']
        
        for driver in drivers:
            # Some drivers might have multiple vehicles
            num_vehicles = random.choices([1, 2], weights=[0.8, 0.2])[0]
            
            for _ in range(num_vehicles):
                make, models = random.choice(car_data)
                model = random.choice(models)
                year = random.randint(2010, 2024)
                color = random.choice(colors)
                
                # Generate Pakistani license plate
                city_code = random.choice(city_codes)
                plate_number = random.randint(100, 9999)
                license_plate = f"{city_code}-{plate_number}"
                
                # Ensure unique license plate
                while Vehicle.objects.filter(license_plate=license_plate).exists():
                    plate_number = random.randint(100, 9999)
                    license_plate = f"{city_code}-{plate_number}"
                
                vehicle = Vehicle.objects.create(
                    owner=driver,
                    make=make,
                    model=model,
                    year=year,
                    color=color,
                    license_plate=license_plate,
                    vehicle_type=random.choice(['sedan', 'hatchback', 'suv', 'crossover']),
                    fuel_type=random.choice(['petrol', 'cng', 'hybrid']),
                    engine_capacity=random.choice(['1000cc', '1300cc', '1600cc', '1800cc', '2000cc']),
                    total_seats=random.choice([4, 5, 6, 7]),
                    available_seats_for_ride=random.randint(2, 4),
                    has_ac=random.choice([True, False]),
                    ac_type=random.choice(['none', 'standard', 'climate_control']),
                    has_music_system=random.choice([True, False]),
                    has_phone_charger=random.choice([True, False]),
                    smoking_allowed=random.choice([True, False]),
                    is_verified=True,
                    is_active=True,
                    average_rating=round(random.uniform(3.5, 5.0), 2),
                    total_ratings=random.randint(0, 30)
                )
                vehicles.append(vehicle)
        
        self.stdout.write(f'Created {len(vehicles)} vehicles')
        return vehicles
    
    def create_locations(self):
        """Create common locations in Karachi"""
        
        locations_data = [
            # Universities
            ('University of Karachi', 'University Road, Karachi', 24.9408, 67.1017, True, False, True),
            ('NED University', 'University Road, Karachi', 24.9215, 67.1141, True, False, True),
            ('IBA Karachi', 'University Road, Karachi', 24.9472, 67.1191, True, False, True),
            ('Aga Khan University', 'Stadium Road, Karachi', 24.8972, 67.0693, True, False, True),
            ('Bahria University Karachi', 'Shangrila Road, Karachi', 24.9419, 67.1328, True, False, True),
            ('FAST-NU Karachi', 'Block 7, Gulshan-e-Iqbal, Karachi', 24.9207, 67.1153, True, False, True),
            
            # Major workplaces/offices
            ('I.I. Chundrigar Road', 'I.I. Chundrigar Road, Karachi', 24.8453, 67.0240, False, True, False),
            ('Clifton Commercial Area', 'Clifton, Karachi', 24.8138, 67.0299, False, True, False),
            ('DHA Phase 2 Commercial', 'DHA Phase 2, Karachi', 24.8090, 67.0376, False, True, False),
            ('Gulshan-e-Iqbal Commercial', 'Gulshan-e-Iqbal, Karachi', 24.9183, 67.1078, False, True, False),
            ('Shahrah-e-Faisal Commercial', 'Shahrah-e-Faisal, Karachi', 24.8774, 67.0574, False, True, False),
            
            # Landmarks and important places
            ('Jinnah International Airport', 'Airport Road, Karachi', 24.9065, 67.1607, False, False, False),
            ('Karachi Cantonment Station', 'Saddar, Karachi', 24.8607, 67.0115, False, False, False),
            ('City Railway Station', 'Serai Quarter, Karachi', 24.8729, 67.0111, False, False, False),
            ('Saddar Empress Market', 'Saddar, Karachi', 24.8535, 67.0146, False, False, False),
            ('Teen Talwar', 'Clifton, Karachi', 24.8043, 67.0279, False, False, False),
            ('Dolmen City Mall', 'Clifton, Karachi', 24.8158, 67.0365, False, False, False),
            ('Lucky One Mall', 'Rashid Minhas Road, Karachi', 24.9403, 67.1334, False, False, False),
            ('Port Grand', 'Keamari, Karachi', 24.8175, 66.9751, False, False, False),
            ('Mazar-e-Quaid', 'Jamshed Quarters, Karachi', 24.8726, 67.0287, False, False, False),
            ('Frere Hall', 'Fatima Jinnah Road, Karachi', 24.8556, 67.0187, False, False, False)
        ]
        
        locations = []
        for name, address, lat, lng, is_workplace, is_landmark, is_university in locations_data:
            location = Location.objects.create(
                name=name,
                address=address,
                latitude=lat,
                longitude=lng,
                city="Karachi",
                state="Sindh",
                is_workplace=is_workplace,
                is_landmark=is_landmark,
                is_university=is_university
            )
            locations.append(location)
        
        self.stdout.write(f'Created {len(locations)} locations')
        return locations
    
    def create_rides(self, users, vehicles, locations, count):
        """Create realistic rides between Karachi locations"""
        
        rides = []
        drivers = [user for user in users if user.is_driver and user.vehicles.exists()]
        
        karachi_timezone = pytz.timezone('Asia/Karachi')
        
        for i in range(count):
            driver = random.choice(drivers)
            vehicle = random.choice(list(driver.vehicles.filter(is_active=True)))
            
            # Select pickup and dropoff locations
            pickup_location = random.choice(locations)
            dropoff_location = random.choice([loc for loc in locations if loc != pickup_location])
            
            # Generate departure time (next 30 days)
            base_time = timezone.now()
            departure_time = base_time + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(6, 22),
                minutes=random.choice([0, 15, 30, 45])
            )
            
            # Ensure departure time is in Karachi timezone
            departure_time = karachi_timezone.localize(departure_time.replace(tzinfo=None))
            
            # Calculate fare based on distance (rough estimate)
            base_fare = random.randint(150, 800)  # PKR
            
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
                total_seats=vehicle.available_seats_for_ride,
                available_seats=random.randint(1, vehicle.available_seats_for_ride),
                fare_per_seat=base_fare,
                ride_type=random.choice(['commute', 'event', 'social', 'errand']),
                status=random.choices(
                    ['scheduled', 'in_progress', 'completed', 'cancelled'],
                    weights=[0.6, 0.1, 0.25, 0.05]
                )[0],
                gender_preference=random.choices(
                    ['any', 'male_only', 'female_only'],
                    weights=[0.7, 0.15, 0.15]
                )[0],
                smoking_allowed=vehicle.smoking_allowed,
                has_ac=vehicle.has_ac,
                time_flexibility_minutes=random.choice([5, 10, 15, 30]),
                is_recurring=random.choice([True, False]),
                description=f"Comfortable ride from {pickup_location.name} to {dropoff_location.name}. " +
                          random.choice([
                              "Looking for friendly passengers!",
                              "Regular commute, reliable timing.",
                              "Safe and comfortable journey.",
                              "Cost-effective travel option.",
                              "Great for daily commuters."
                          ]),
                average_rating=round(random.uniform(3.5, 5.0), 2),
                total_ratings=random.randint(0, 20)
            )
            
            # Add recurring days if applicable
            if ride.is_recurring:
                ride.recurring_days = random.sample(range(7), random.randint(3, 5))
                ride.save()
            
            rides.append(ride)
        
        self.stdout.write(f'Created {len(rides)} rides')
        return rides
    
    def create_ride_passengers(self, users, rides):
        """Create realistic ride passengers and requests"""
        
        passengers = []
        non_drivers = [user for user in users if not user.is_driver or random.choice([True, False])]
        
        # Create passengers for some rides
        for ride in random.sample(rides, min(len(rides) // 2, len(rides))):
            if ride.available_seats > 0:
                # Add some passengers
                num_passengers = random.randint(1, min(ride.available_seats, 3))
                
                for _ in range(num_passengers):
                    passenger = random.choice([p for p in non_drivers if p != ride.driver])
                    
                    # Check if passenger already joined this ride
                    if not RidePassenger.objects.filter(ride=ride, passenger=passenger).exists():
                        passenger_status = random.choices(
                            ['pending', 'confirmed', 'cancelled', 'completed'],
                            weights=[0.1, 0.6, 0.1, 0.2]
                        )[0]
                        
                        # Generate passenger pickup/dropoff locations near ride route
                        pickup_lat = ride.pickup_latitude + random.uniform(-0.01, 0.01)
                        pickup_lng = ride.pickup_longitude + random.uniform(-0.01, 0.01)
                        dropoff_lat = ride.dropoff_latitude + random.uniform(-0.01, 0.01)
                        dropoff_lng = ride.dropoff_longitude + random.uniform(-0.01, 0.01)
                        
                        # Calculate distance for passenger
                        passenger_distance = self.haversine_distance(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
                        individual_fare = Decimal(str(round(passenger_distance * random.uniform(15, 25), 2)))  # PKR per km
                        
                        ride_passenger = RidePassenger.objects.create(
                            ride=ride,
                            passenger=passenger,
                            status=passenger_status,
                            pickup_note=random.choice([
                                "Near main gate", "Outside McDonald's", "At bus stop",
                                "University entrance", "Main road", "Office building"
                            ]),
                            passenger_pickup_location=f"Near {ride.pickup_location}",
                            passenger_dropoff_location=f"Near {ride.dropoff_location}",
                            passenger_pickup_latitude=pickup_lat,
                            passenger_pickup_longitude=pickup_lng,
                            passenger_dropoff_latitude=dropoff_lat,
                            passenger_dropoff_longitude=dropoff_lng,
                            passenger_distance_km=passenger_distance,
                            individual_fare=individual_fare,
                            relationship=random.choice(['colleague', 'friend', 'acquaintance', 'other']),
                            has_contributed=random.choice([True, False]),
                            contribution_amount=individual_fare if random.choice([True, False]) else Decimal('0.00')
                        )
                        
                        passengers.append(ride_passenger)
                        
                        # Update ride's available seats if confirmed
                        if passenger_status == 'confirmed':
                            ride.available_seats -= 1
                            ride.save()
        
        # Create some ride requests (pending requests)
        for _ in range(min(20, len(non_drivers))):
            passenger = random.choice(non_drivers)
            available_rides = [r for r in rides if r.driver != passenger and r.available_seats > 0]
            
            if available_rides:
                ride = random.choice(available_rides)
                
                # Check if passenger already has a request for this ride
                if not RideRequest.objects.filter(ride=ride, passenger=passenger).exists():
                    pickup_lat = ride.pickup_latitude + random.uniform(-0.02, 0.02)
                    pickup_lng = ride.pickup_longitude + random.uniform(-0.02, 0.02)
                    dropoff_lat = ride.dropoff_latitude + random.uniform(-0.02, 0.02)
                    dropoff_lng = ride.dropoff_longitude + random.uniform(-0.02, 0.02)
                    
                    request_distance = self.haversine_distance(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
                    estimated_fare = Decimal(str(round(request_distance * random.uniform(15, 25), 2)))
                    
                    RideRequest.objects.create(
                        ride=ride,
                        passenger=passenger,
                        pickup_location=f"Near {ride.pickup_location}",
                        dropoff_location=f"Near {ride.dropoff_location}",
                        pickup_latitude=pickup_lat,
                        pickup_longitude=pickup_lng,
                        dropoff_latitude=dropoff_lat,
                        dropoff_longitude=dropoff_lng,
                        status='pending',
                        message=random.choice([
                            "Hi, can I join your ride?",
                            "Looking for a comfortable ride, thanks!",
                            "Regular commuter, reliable passenger.",
                            "Need a ride for tomorrow, please confirm.",
                            "Safe driver references available if needed."
                        ]),
                        seats_requested=1,
                        estimated_distance_km=request_distance,
                        estimated_fare=estimated_fare
                    )
        
        self.stdout.write(f'Created {len(passengers)} ride passengers and some ride requests')
        return passengers
