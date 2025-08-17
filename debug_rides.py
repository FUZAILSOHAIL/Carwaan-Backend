#!/usr/bin/env python
import os
import sys
import django

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.rides.models import Ride, RideRequest
from apps.users.models import User
from django.utils import timezone

print("=== Database Debug Information ===")

# Check total users
total_users = User.objects.count()
print(f"Total users: {total_users}")

# Check drivers (users who have created rides)
drivers = User.objects.filter(offered_rides__isnull=False).distinct()
print(f"Users who are drivers: {drivers.count()}")

# Check total rides
total_rides = Ride.objects.count()
print(f"Total rides: {total_rides}")

if total_rides > 0:
    print("\n=== Recent Rides ===")
    recent_rides = Ride.objects.all().order_by('-created_at')[:5]
    for ride in recent_rides:
        print(f"Ride {ride.id}: Driver={ride.driver.username}, Status={ride.status}")
        print(f"  From: {ride.pickup_location}")
        print(f"  To: {ride.dropoff_location}")
        print(f"  Departure: {ride.departure_time}")
        print(f"  Created: {ride.created_at}")
        print(f"  Is future?: {ride.departure_time >= timezone.now()}")
        print()

# Check total ride requests
total_requests = RideRequest.objects.count()
print(f"Total ride requests: {total_requests}")

if total_requests > 0:
    print("\n=== Recent Ride Requests ===")
    recent_requests = RideRequest.objects.all().order_by('-created_at')[:5]
    for request in recent_requests:
        print(f"Request {request.id}: Passenger={request.passenger.username}, Status={request.status}")
        print(f"  For ride: {request.ride.id} (Driver: {request.ride.driver.username})")
        print(f"  Created: {request.created_at}")
        print()

print("\n=== Driver Specific Data ===")
# Check data for each driver
for driver in drivers:
    print(f"\nDriver: {driver.username} (ID: {driver.id})")
    
    # Upcoming rides
    upcoming_rides = Ride.objects.filter(
        driver=driver,
        departure_time__gte=timezone.now(),
        status__in=['scheduled', 'in_progress']
    )
    print(f"  Upcoming rides: {upcoming_rides.count()}")
    
    # All rides
    all_driver_rides = Ride.objects.filter(driver=driver)
    print(f"  Total rides: {all_driver_rides.count()}")
    
    # Pending requests
    pending_requests = RideRequest.objects.filter(
        ride__driver=driver,
        status='pending'
    )
    print(f"  Pending requests: {pending_requests.count()}")
    
    # All requests
    all_requests = RideRequest.objects.filter(ride__driver=driver)
    print(f"  Total requests: {all_requests.count()}")
