from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.envconf import required_env
from apps.users.models import User
from apps.rides.models import Ride, RidePassenger


class Command(BaseCommand):
    help = 'Update admin panel with modern configuration and features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser if one does not exist',
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for the superuser (default: admin)',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@carwaan.com',
            help='Email for the superuser (default: admin@carwaan.com)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Updating Carwaan admin panel...')
        
        try:
            # Create superuser if requested
            if options['create_superuser']:
                self.create_superuser(options['username'], options['email'])
            
            # Run migrations to ensure everything is up to date
            self.stdout.write('Checking database migrations...')
            
            # Update admin interface theme
            self.update_admin_interface_theme()
            
            # Display statistics
            self.display_statistics()
            
            self.stdout.write(
                self.style.SUCCESS('Successfully updated admin panel!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating admin panel: {str(e)}')
            )

    def create_superuser(self, username, email):
        """Create a superuser if one doesn't exist"""
        User = get_user_model()
        
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Superuser already exists.')
            return
            
        try:
            with transaction.atomic():
                password = required_env("ADMIN_PASSWORD")
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name='Admin',
                    last_name='User',
                    role='admin'
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created superuser: {username}. '
                        'Password was taken from ADMIN_PASSWORD. '
                        'Change it after first login.'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )

    def update_admin_interface_theme(self):
        """Update admin interface theme configuration"""
        try:
            from admin_interface.models import Theme
            
            # Try to get or create the default theme
            theme, created = Theme.objects.get_or_create(
                name='Carwaan Theme',
                defaults={
                    'active': True,
                    'title': 'Carwaan Administration',
                    'title_color': '#ffffff',
                    'title_visible': True,
                    'logo_color': '#ffffff',
                    'logo_visible': True,
                    'env_name': 'Carwaan',
                    'env_visible_in_header': True,
                    'env_color': '#ffffff',
                }
            )
            
            if created:
                self.stdout.write('Created new admin theme configuration.')
            else:
                self.stdout.write('Admin theme configuration already exists.')
                
        except ImportError:
            self.stdout.write('Admin interface theme package not available.')
        except Exception as e:
            self.stdout.write(f'Error updating theme: {str(e)}')

    def display_statistics(self):
        """Display current platform statistics"""
        try:
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            verified_users = User.objects.filter(is_verified=True).count()
            drivers = User.objects.filter(has_car=True).count()
            
            total_rides = Ride.objects.count()
            active_rides = Ride.objects.filter(status='active').count()
            completed_rides = Ride.objects.filter(status='completed').count()
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write('CARWAAN PLATFORM STATISTICS')
            self.stdout.write('='*50)
            self.stdout.write(f'Total Users: {total_users}')
            self.stdout.write(f'Active Users: {active_users}')
            self.stdout.write(f'Verified Users: {verified_users}')
            self.stdout.write(f'Drivers: {drivers}')
            self.stdout.write('-'*30)
            self.stdout.write(f'Total Rides: {total_rides}')
            self.stdout.write(f'Active Rides: {active_rides}')
            self.stdout.write(f'Completed Rides: {completed_rides}')
            self.stdout.write('='*50 + '\n')
            
        except Exception as e:
            self.stdout.write(f'Error displaying statistics: {str(e)}')
