from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.db.models import Count, Avg, Q
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib.admin import AdminSite
from apps.users.models import User
from apps.rides.models import Ride, RidePassenger
from datetime import datetime, timedelta
from django.utils import timezone


class CarwaanAdminSite(AdminSite):
    site_header = 'Carwaan Administration'
    site_title = 'Carwaan Admin'
    index_title = 'Welcome to Carwaan Administration'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
            path('user_analytics/', self.admin_view(self.user_analytics_view), name='user_analytics'),
            path('ride_analytics/', self.admin_view(self.ride_analytics_view), name='ride_analytics'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        """Main analytics dashboard"""
        try:
            context = self.get_analytics_context()
            context.update({
                'title': 'Analytics Dashboard',
                'site_title': self.site_title,
                'site_header': self.site_header,
                'has_permission': request.user.is_active and request.user.is_staff,
            })
            return render(request, 'admin/analytics_dashboard.html', context)
        except Exception as e:
            # Fallback context in case of errors
            context = {
                'title': 'Analytics Dashboard',
                'site_title': self.site_title,
                'site_header': self.site_header,
                'has_permission': request.user.is_active and request.user.is_staff,
                'total_users': 0,
                'active_users': 0,
                'verified_users': 0,
                'drivers': 0,
                'new_users_30d': 0,
                'total_rides': 0,
                'active_rides': 0,
                'completed_rides': 0,
                'cancelled_rides': 0,
                'rides_30d': 0,
                'popular_pickups': [],
                'popular_dropoffs': [],
                'top_drivers': [],
                'recent_users': [],
                'recent_rides': [],
                'error_message': f'Error loading analytics: {str(e)}'
            }
            return render(request, 'admin/analytics_dashboard.html', context)
    
    def user_analytics_view(self, request):
        """User-specific analytics"""
        context = self.get_user_analytics_context()
        return render(request, 'admin/user_analytics.html', context)
    
    def ride_analytics_view(self, request):
        """Ride-specific analytics"""
        context = self.get_ride_analytics_context()
        return render(request, 'admin/ride_analytics.html', context)
    
    def get_analytics_context(self):
        """Get overall analytics data"""
        try:
            now = timezone.now()
            last_30_days = now - timedelta(days=30)
            last_7_days = now - timedelta(days=7)
            
            # User statistics
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            verified_users = User.objects.filter(is_verified=True).count()
            drivers = User.objects.filter(has_car=True).count()
            new_users_30d = User.objects.filter(created_at__gte=last_30_days).count()
            
            # Ride statistics
            total_rides = Ride.objects.count()
            active_rides = Ride.objects.filter(status='active').count()
            completed_rides = Ride.objects.filter(status='completed').count()
            cancelled_rides = Ride.objects.filter(status='cancelled').count()
            rides_30d = Ride.objects.filter(created_at__gte=last_30_days).count()
            
            # Popular locations
            popular_pickups = list(Ride.objects.values('pickup_location').annotate(
                count=Count('id')
            ).order_by('-count')[:10])
            
            popular_dropoffs = list(Ride.objects.values('dropoff_location').annotate(
                count=Count('id')
            ).order_by('-count')[:10])
            
            # Top drivers
            top_drivers = list(User.objects.filter(has_car=True).annotate(
                rides_count=Count('offered_rides')
            ).order_by('-rides_count')[:10])
            
            # Recent activity
            recent_users = list(User.objects.filter(
                created_at__gte=last_7_days
            ).order_by('-created_at')[:5])
            
            recent_rides = list(Ride.objects.filter(
                created_at__gte=last_7_days
            ).select_related('driver').order_by('-created_at')[:5])
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'verified_users': verified_users,
                'drivers': drivers,
                'new_users_30d': new_users_30d,
                'total_rides': total_rides,
                'active_rides': active_rides,
                'completed_rides': completed_rides,
                'cancelled_rides': cancelled_rides,
                'rides_30d': rides_30d,
                'popular_pickups': popular_pickups,
                'popular_dropoffs': popular_dropoffs,
                'top_drivers': top_drivers,
                'recent_users': recent_users,
                'recent_rides': recent_rides,
            }
        except Exception as e:
            # Return safe fallback data
            return {
                'total_users': 0,
                'active_users': 0,
                'verified_users': 0,
                'drivers': 0,
                'new_users_30d': 0,
                'total_rides': 0,
                'active_rides': 0,
                'completed_rides': 0,
                'cancelled_rides': 0,
                'rides_30d': 0,
                'popular_pickups': [],
                'popular_dropoffs': [],
                'top_drivers': [],
                'recent_users': [],
                'recent_rides': [],
                'error_message': str(e)
            }
    
    def get_user_analytics_context(self):
        """Get user-specific analytics"""
        # Gender distribution
        gender_stats = User.objects.values('gender').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Role distribution
        role_stats = User.objects.values('role').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Workplace distribution
        workplace_stats = User.objects.exclude(
            workplace=''
        ).values('workplace').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # User growth over time
        user_growth = User.objects.extra(
            select={'month': 'strftime("%Y-%m", created_at)'}
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Driver vs Passenger ratio
        driver_stats = {
            'drivers': User.objects.filter(has_car=True).count(),
            'passengers': User.objects.filter(has_car=False).count()
        }
        
        return {
            'gender_stats': gender_stats,
            'role_stats': role_stats,
            'workplace_stats': workplace_stats,
            'user_growth': user_growth,
            'driver_stats': driver_stats,
        }
    
    def get_ride_analytics_context(self):
        """Get ride-specific analytics"""
        # Ride status distribution
        status_stats = Ride.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Ride type distribution
        type_stats = Ride.objects.values('ride_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Average price per seat
        avg_price = Ride.objects.exclude(
            price_per_seat=0
        ).aggregate(avg_price=Avg('price_per_seat'))['avg_price'] or 0
        
        # Ride creation over time
        ride_growth = Ride.objects.extra(
            select={'month': 'strftime("%Y-%m", created_at)'}
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Popular routes
        popular_routes = Ride.objects.values(
            'pickup_location', 'dropoff_location'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Seat utilization
        seat_utilization = Ride.objects.aggregate(
            total_seats=Count('total_seats'),
            available_seats=Count('available_seats')
        )
        
        return {
            'status_stats': status_stats,
            'type_stats': type_stats,
            'avg_price': avg_price,
            'ride_growth': ride_growth,
            'popular_routes': popular_routes,
            'seat_utilization': seat_utilization,
        }


# Create custom admin site instance
admin_site = CarwaanAdminSite(name='carwaan_admin')

# Register all models with the custom admin site
from apps.users.admin import UserAdmin, PaymentMethodAdmin
from apps.users.admin_vehicle import VehicleAdmin
from apps.rides.admin import (
    RideAdmin, RidePassengerAdmin, LocationAdmin, 
    RoutePointAdmin, RideStopAdmin, ScheduledRideAdmin,
    RideReviewAdmin, RideDirectionAdmin, FareCalculationAdmin,
    RideRequestAdmin
)
from apps.rides.models import (
    Location, RoutePoint, RideStop, ScheduledRide, RideReview,
    RideDirection, FareCalculation, RideRequest
)

# Commented out - using default admin site instead of custom site
# 
# from apps.users.models_vehicle import Vehicle
# 
# admin_site.register(User, UserAdmin)
# admin_site.register(Vehicle, VehicleAdmin)
# admin_site.register(Ride, RideAdmin)
# admin_site.register(RidePassenger, RidePassengerAdmin)
# admin_site.register(Location, LocationAdmin)
# admin_site.register(RoutePoint, RoutePointAdmin)
# admin_site.register(RideStop, RideStopAdmin)
# admin_site.register(ScheduledRide, ScheduledRideAdmin)
# admin_site.register(RideReview, RideReviewAdmin)
# admin_site.register(RideDirection, RideDirectionAdmin)
# admin_site.register(FareCalculation, FareCalculationAdmin)
# admin_site.register(RideRequest, RideRequestAdmin)
# 
# # Also register PaymentMethod if it exists
# try:
#     from apps.users.models import PaymentMethod
#     admin_site.register(PaymentMethod, PaymentMethodAdmin)
# except ImportError:
#     pass
