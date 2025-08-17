# Core services package
from .google_drive_service import GoogleDriveService, google_drive_service

# Import OpenRouteService from rides app for compatibility
try:
    from apps.rides.route_service import OpenRouteServiceProvider as OpenRouteService
    from apps.rides.route_service import calculate_route_distance, get_route_alternatives, route_service
except ImportError:
    pass
