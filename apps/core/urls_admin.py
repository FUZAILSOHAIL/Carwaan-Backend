from django.urls import path
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

# Simple placeholder views for admin analytics
@staff_member_required
def user_analytics_placeholder(request):
    """Placeholder for user analytics - prevents URL reverse errors"""
    return JsonResponse({'message': 'User analytics endpoint'})

@staff_member_required  
def ride_analytics_placeholder(request):
    """Placeholder for ride analytics - prevents URL reverse errors"""
    return JsonResponse({'message': 'Ride analytics endpoint'})

# Admin URL patterns to prevent reverse lookup errors
admin_urlpatterns = [
    path('user_analytics/', user_analytics_placeholder, name='user_analytics'),
    path('ride_analytics/', ride_analytics_placeholder, name='ride_analytics'),
]
