"""
URL patterns for route API endpoints
"""

from django.urls import path
from . import api_views

app_name = 'routes_api'

urlpatterns = [
    # Route calculation endpoints
    path('calculate/', api_views.calculate_route, name='calculate_route'),
    path('alternatives/', api_views.get_route_alternatives_api, name='route_alternatives'),
    path('waypoints/', api_views.calculate_route_with_waypoints, name='route_waypoints'),
    path('status/', api_views.route_service_status, name='route_status'),
]
