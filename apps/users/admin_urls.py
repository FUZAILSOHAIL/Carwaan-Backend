from django.urls import path
from . import admin_views

urlpatterns = [
    # Admin endpoints
    path('admin/users/', admin_views.get_all_users, name='admin_get_all_users'),
    path('admin/users/<int:user_id>/', admin_views.get_user_details, name='admin_get_user_details'),
    path('admin/users/<int:user_id>/suspend/', admin_views.suspend_user, name='admin_suspend_user'),
    path('admin/users/<int:user_id>/delete/', admin_views.delete_user, name='admin_delete_user'),  # Fixed path
    path('admin/rides/', admin_views.get_all_rides, name='admin_get_all_rides'),
    path('admin/rides/<int:ride_id>/cancel/', admin_views.admin_cancel_ride, name='admin_cancel_ride'),
    path('admin/analytics/', admin_views.get_admin_analytics, name='admin_get_analytics'),
    path('admin/stats/', admin_views.get_system_stats, name='admin_get_system_stats'),
    path('admin/recent-activity/', admin_views.get_recent_activity, name='admin_get_recent_activity'),
]
