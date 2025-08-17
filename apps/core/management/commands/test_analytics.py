from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.users.models import User
from apps.rides.models import Ride


class Command(BaseCommand):
    help = 'Test the analytics dashboard functionality'

    def handle(self, *args, **options):
        self.stdout.write('Testing analytics dashboard...')
        
        try:
            # Test basic queries
            total_users = User.objects.count()
            total_rides = Ride.objects.count()
            
            self.stdout.write(f'✓ Total users: {total_users}')
            self.stdout.write(f'✓ Total rides: {total_rides}')
            
            # Test analytics queries
            from apps.core.admin import CarwaanAdminSite
            admin_site = CarwaanAdminSite()
            context = admin_site.get_analytics_context()
            
            self.stdout.write('✓ Analytics context generated successfully')
            self.stdout.write(f'  - Users: {context["total_users"]}')
            self.stdout.write(f'  - Active rides: {context["active_rides"]}')
            self.stdout.write(f'  - Popular pickups: {len(context["popular_pickups"])}')
            
            if 'error_message' in context:
                self.stdout.write(
                    self.style.WARNING(f'Warning: {context["error_message"]}')
                )
            
            self.stdout.write(
                self.style.SUCCESS('Analytics dashboard test completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error testing analytics: {str(e)}')
            )
