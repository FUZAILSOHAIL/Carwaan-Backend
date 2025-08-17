#!/usr/bin/env python
import os
import sys
import django

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(__file__))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Setup Django
django.setup()

from apps.users.models import User
from apps.rides.models import Ride

print("=== Database Check ===")
print(f"Total users: {User.objects.count()}")
print(f"Total rides: {Ride.objects.count()}")

admin_users = User.objects.filter(role='admin')
print(f"Admin users: {admin_users.count()}")

for user in admin_users:
    print(f"  - {user.username} ({user.email})")

# Create an admin user if none exists
if admin_users.count() == 0:
    print("No admin users found. Creating one...")
    admin_user = User.objects.create_user(
        username='admin',
        email='admin@carwaan.com',
        password='admin123',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    print(f"Created admin user: {admin_user.username}")
else:
    print("Admin users already exist.")

print("=== End Check ===")
