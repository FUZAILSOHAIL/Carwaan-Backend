"""
Admin URL patches to fix reverse lookup errors
"""
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def user_analytics(request):
    """Placeholder user analytics view"""
    context = {
        'title': 'User Analytics',
        'site_title': admin.site.site_title,
        'site_header': admin.site.site_header,
        'has_permission': request.user.is_active and request.user.is_staff,
    }
    return render(request, 'admin/simple_analytics.html', context)

@staff_member_required  
def ride_analytics(request):
    """Placeholder ride analytics view"""
    context = {
        'title': 'Ride Analytics', 
        'site_title': admin.site.site_title,
        'site_header': admin.site.site_header,
        'has_permission': request.user.is_active and request.user.is_staff,
    }
    return render(request, 'admin/simple_analytics.html', context)

# Monkey patch the admin site to add missing URLs
original_get_urls = admin.site.get_urls

def patched_get_urls():
    urls = original_get_urls()
    custom_urls = [
        path('user_analytics/', admin.site.admin_view(user_analytics), name='user_analytics'),
        path('ride_analytics/', admin.site.admin_view(ride_analytics), name='ride_analytics'),
    ]
    return custom_urls + urls

admin.site.get_urls = patched_get_urls
