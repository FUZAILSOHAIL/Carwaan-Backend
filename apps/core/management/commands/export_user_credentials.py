import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.users.models import User


class Command(BaseCommand):
    help = 'Export all user credentials to a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='user_credentials.csv',
            help='Output CSV file name (default: user_credentials.csv)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Ensure the file path is absolute
        if not os.path.isabs(output_file):
            output_file = os.path.join(settings.BASE_DIR, output_file)
            
        self.stdout.write(f"Exporting user credentials to: {output_file}")
        
        # Get all users
        users = User.objects.all().order_by('username')
        
        # Create CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'username', 'email', 'password', 'first_name', 'last_name', 
                'phone', 'gender', 'role', 'is_driver', 'driver_verification_status',
                'has_car', 'is_active', 'is_verified', 'date_joined'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for user in users:
                # Note: In a real application, passwords are hashed and cannot be retrieved
                # For testing purposes, we'll include the default password
                password = 'testpass123' if user.username != 'admin' else 'admin123'
                
                writer.writerow({
                    'username': user.username,
                    'email': user.email,
                    'password': password,  # Default test password
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
                    'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S')
                })
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully exported {users.count()} users to {output_file}'
            )
        )
        
        # Print some sample credentials for quick reference
        self.stdout.write(self.style.WARNING('\n=== SAMPLE CREDENTIALS ==='))
        sample_users = users[:5]
        for user in sample_users:
            password = 'testpass123' if user.username != 'admin' else 'admin123'
            self.stdout.write(f"Username: {user.username} | Password: {password} | Role: {user.role}")
        
        if users.count() > 5:
            self.stdout.write(f"... and {users.count() - 5} more users")
        
        self.stdout.write(self.style.WARNING('\n=== ADMIN CREDENTIALS ==='))
        admin_user = users.filter(role='admin').first()
        if admin_user:
            self.stdout.write(f"Admin Username: {admin_user.username}")
            self.stdout.write(f"Admin Password: admin123")
            self.stdout.write(f"Admin Email: {admin_user.email}")
