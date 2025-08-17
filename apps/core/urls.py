from django.urls import path, include
from .views import get_route, get_route_with_waypoints, get_route_alternatives

urlpatterns = [
    path('get-route/', get_route, name='get_route'),
    path('get-route-waypoints/', get_route_with_waypoints, name='get_route_waypoints'),
    path('get-route-alternatives/', get_route_alternatives, name='get_route_alternatives'),
    
    # Notification endpoints
    path('notifications/', include('apps.core.urls_notifications')),
]
