from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count, Q, Avg, Sum, Case, When, IntegerField
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate, TruncMonth
from datetime import datetime, timedelta
import csv
import json

try:
    from import_export import resources, fields
    from import_export.admin import ImportExportModelAdmin
    from import_export.widgets import ForeignKeyWidget, DateTimeWidget, BooleanWidget
    HAS_IMPORT_EXPORT = True
except ImportError:
    HAS_IMPORT_EXPORT = False
    ImportExportModelAdmin = admin.ModelAdmin

from .models import User, PaymentMethod
# Vehicle import moved to admin_vehicle.py
from apps.rides.models import Ride, RideRequest, RideReview


# Enhanced Resources for Import/Export
if HAS_IMPORT_EXPORT:
    class UserResource(resources.ModelResource):
        full_name = fields.Field(column_name='full_name')
        verification_status = fields.Field(column_name='driver_verification_status')
        total_rides_offered = fields.Field(column_name='total_rides_offered')
        total_rides_taken = fields.Field(column_name='total_rides_taken')
        average_rating = fields.Field(column_name='average_rating')
        
        class Meta:
            model = User
            fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name',
                     'phone', 'role', 'is_driver', 'verification_status', 'cnic_number',
                     'driver_license_number', 'workplace', 'department', 'is_active', 
                     'is_verified', 'email_verified', 'total_rides_offered', 'total_rides_taken',
                     'average_rating', 'date_joined', 'last_login')
            export_order = fields
        
        def dehydrate_full_name(self, user):
            return f"{user.first_name} {user.last_name}".strip() or user.username
        
        def dehydrate_total_rides_offered(self, user):
            return user.offered_rides.count()
        
        def dehydrate_total_rides_taken(self, user):
            return user.joined_rides.count()
        
        def dehydrate_average_rating(self, user):
            return user.average_rating or 0

    class PaymentMethodResource(resources.ModelResource):
        user = fields.Field(
            column_name='user',
            attribute='user',
            widget=ForeignKeyWidget(User, 'username')
        )
        
        class Meta:
            model = PaymentMethod
            fields = ('id', 'user', 'type', 'holder_name', 'last_four', 'brand',
                     'phone_number', 'bank_name', 'is_default', 'is_active', 'created_at')
            export_order = fields


# Custom Admin Views - Remove the problematic decorator
class AdminDashboardView:
    @staff_member_required
    def dashboard_stats(self, request):
        """Enhanced dashboard with comprehensive statistics"""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        
        # User Statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(is_verified=True).count()
        drivers = User.objects.filter(is_driver=True).count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_week = User.objects.filter(date_joined__date__gte=last_week).count()
        
        # Driver Verification Statistics
        pending_verifications = User.objects.filter(
            driver_verification_status='under_review'
        ).count()
        verified_drivers = User.objects.filter(
            driver_verification_status='verified'
        ).count()
        rejected_verifications = User.objects.filter(
            driver_verification_status='rejected'
        ).count()
        
        # Ride Statistics
        total_rides = Ride.objects.count()
        active_rides = Ride.objects.filter(status='active').count()
        completed_rides = Ride.objects.filter(status='completed').count()
        cancelled_rides = Ride.objects.filter(status='cancelled').count()
        rides_today = Ride.objects.filter(created_at__date=today).count()
        
        # Revenue Statistics (if applicable)
        total_revenue = Ride.objects.filter(
            status='completed'
        ).aggregate(total=Sum('price_per_seat'))['total'] or 0
        
        # Popular Routes
        popular_routes = Ride.objects.values(
            'pickup_location', 'dropoff_location'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Recent Activity
        recent_users = User.objects.filter(
            date_joined__gte=last_week
        ).order_by('-date_joined')[:10]
        
        recent_rides = Ride.objects.filter(
            created_at__gte=last_week
        ).order_by('-created_at')[:10]
        
        context = {
            'total_users': total_users,
            'active_users': active_users,
            'verified_users': verified_users,
            'drivers': drivers,
            'new_users_today': new_users_today,
            'new_users_week': new_users_week,
            'pending_verifications': pending_verifications,
            'verified_drivers': verified_drivers,
            'rejected_verifications': rejected_verifications,
            'total_rides': total_rides,
            'active_rides': active_rides,
            'completed_rides': completed_rides,
            'cancelled_rides': cancelled_rides,
            'rides_today': rides_today,
            'total_revenue': total_revenue,
            'popular_routes': popular_routes,
            'recent_users': recent_users,
            'recent_rides': recent_rides,
        }
        
        return render(request, 'admin/dashboard_stats.html', context)
    
    def dashboard_view(self, request):
        """Enhanced dashboard with comprehensive statistics"""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        
        # User Statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(is_verified=True).count()
        drivers = User.objects.filter(is_driver=True).count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_week = User.objects.filter(date_joined__date__gte=last_week).count()
        
        # Driver Verification Statistics
        pending_verifications = User.objects.filter(
            driver_verification_status='under_review'
        ).count()
        verified_drivers = User.objects.filter(
            driver_verification_status='verified'
        ).count()
        rejected_verifications = User.objects.filter(
            driver_verification_status='rejected'
        ).count()
        
        # Ride Statistics
        total_rides = Ride.objects.count()
        active_rides = Ride.objects.filter(status='active').count()
        completed_rides = Ride.objects.filter(status='completed').count()
        cancelled_rides = Ride.objects.filter(status='cancelled').count()
        rides_today = Ride.objects.filter(created_at__date=today).count()
        
        # Revenue Statistics (if applicable)
        total_revenue = Ride.objects.filter(
            status='completed'
        ).aggregate(total=Sum('price_per_seat'))['total'] or 0
        
        # Popular Routes
        popular_routes = Ride.objects.values(
            'pickup_location', 'dropoff_location'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Recent Activity
        recent_users = User.objects.filter(
            date_joined__gte=last_week
        ).order_by('-date_joined')[:10]
        
        recent_rides = Ride.objects.filter(
            created_at__gte=last_week
        ).order_by('-created_at')[:10]
        
        context = {
            'total_users': total_users,
            'active_users': active_users,
            'verified_users': verified_users,
            'drivers': drivers,
            'new_users_today': new_users_today,
            'new_users_week': new_users_week,
            'pending_verifications': pending_verifications,
            'verified_drivers': verified_drivers,
            'rejected_verifications': rejected_verifications,
            'total_rides': total_rides,
            'active_rides': active_rides,
            'completed_rides': completed_rides,
            'cancelled_rides': cancelled_rides,
            'rides_today': rides_today,
            'total_revenue': total_revenue,
            'popular_routes': popular_routes,
            'recent_users': recent_users,
            'recent_rides': recent_rides,
            'current_time': timezone.now(),
        }
        
        return TemplateResponse(request, 'admin/dashboard.html', context)
    
    def driver_verification_queue(self, request):
        """Enhanced driver verification queue with filtering"""
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        search = request.GET.get('search', '')
        
        # Base queryset
        queryset = User.objects.filter(is_driver=True).exclude(
            driver_verification_status='verified'
        )
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(driver_verification_status=status_filter)
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(verification_submitted_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(verification_submitted_at__date__lte=date_to)
            except ValueError:
                pass
        
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(cnic_number__icontains=search) |
                Q(driver_license_number__icontains=search)
            )
        
        queryset = queryset.order_by('verification_submitted_at')
        
        # Statistics
        pending_count = User.objects.filter(driver_verification_status='under_review').count()
        approved_count = User.objects.filter(driver_verification_status='verified').count()
        rejected_count = User.objects.filter(driver_verification_status='rejected').count()
        total_count = User.objects.filter(is_driver=True).count()
        
        # Pagination
        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'users': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'total_count': total_count,
        }
        
        return TemplateResponse(request, 'admin/driver_verification_queue.html', context)
    
    def approve_driver_verification(self, request, user_id):
        """Approve driver verification"""
        user = get_object_or_404(User, id=user_id)
        user.driver_verification_status = 'verified'
        user.verification_approved_at = timezone.now()
        user.verification_rejection_reason = ''
        user.save()
        
        # Send approval email
        self.send_verification_email(user, 'approved')
        
        messages.success(request, f'Driver verification approved for {user.get_full_name() or user.username}')
        return redirect('admin:driver_verification_queue')
    
    def reject_driver_verification(self, request, user_id):
        """Reject driver verification"""
        user = get_object_or_404(User, id=user_id)
        
        if request.method == 'POST':
            reason = request.POST.get('reason', 'Documents did not meet verification requirements')
            user.driver_verification_status = 'rejected'
            user.verification_rejected_at = timezone.now()
            user.verification_rejection_reason = reason
            user.save()
            
            # Send rejection email
            self.send_verification_email(user, 'rejected', reason)
            
            messages.success(request, f'Driver verification rejected for {user.get_full_name() or user.username}')
            return redirect('admin:driver_verification_queue')
        
        context = {
            'user': user,
            'title': f'Reject Driver Verification - {user.get_full_name() or user.username}',
        }
        return TemplateResponse(request, 'admin/reject_verification.html', context)
    
    def analytics_reports(self, request):
        """Analytics and reports view"""
        # This would contain comprehensive analytics
        context = {
            'title': 'Analytics & Reports',
        }
        return TemplateResponse(request, 'admin/analytics_reports.html', context)
    
    def system_settings(self, request):
        """System settings view"""
        context = {
            'title': 'System Settings',
        }
        return TemplateResponse(request, 'admin/system_settings.html', context)
    
    def bulk_actions(self, request):
        """Bulk actions view"""
        context = {
            'title': 'Bulk Actions',
        }
        return TemplateResponse(request, 'admin/bulk_actions.html', context)
    
    def export_users(self, request):
        """Export users to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="carwaan_users.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Username', 'Email', 'First Name', 'Last Name', 'Phone', 'Role',
            'Is Driver', 'Verification Status', 'CNIC', 'License Number', 'Is Active',
            'Date Joined', 'Last Login'
        ])
        
        for user in User.objects.all():
            writer.writerow([
                user.id, user.username, user.email, user.first_name, user.last_name,
                user.phone, user.role, user.is_driver, user.driver_verification_status,
                user.cnic_number, user.driver_license_number, user.is_active,
                user.date_joined, user.last_login
            ])
        
        return response
    
    def send_verification_email(self, user, status, reason=None):
        """Send verification status email to user"""
        if status == 'approved':
            subject = 'Driver Verification Approved - Carwaan'
            message = f'''
            Dear {user.first_name or user.username},
            
            Congratulations! Your driver verification has been approved.
            You can now start offering rides on Carwaan.
            
            Best regards,
            Carwaan Team
            '''
        elif status == 'rejected':
            subject = 'Driver Verification Update - Carwaan'
            message = f'''
            Dear {user.first_name or user.username},
            
            We regret to inform you that your driver verification was not approved.
            
            Reason: {reason}
            
            You can resubmit your documents after addressing the issues mentioned above.
            
            Best regards,
            Carwaan Team
            '''
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Failed to send email to {user.email}: {e}")
    
    # Action methods
    def verify_users(self, request, queryset):
        """Mark selected users as verified"""
        count = queryset.update(is_verified=True)
        self.message_user(request, f'{count} user(s) marked as verified.')
    verify_users.short_description = "Mark selected users as verified"
    
    def unverify_users(self, request, queryset):
        """Mark selected users as unverified"""
        count = queryset.update(is_verified=False)
        self.message_user(request, f'{count} user(s) marked as unverified.')
    unverify_users.short_description = "Mark selected users as unverified"
    
    def approve_drivers(self, request, queryset):
        """Approve driver verification for selected users"""
        driver_users = queryset.filter(is_driver=True)
        count = driver_users.update(
            driver_verification_status='verified',
            verification_approved_at=timezone.now(),
            verification_rejection_reason=''
        )
        self.message_user(request, f'{count} driver(s) approved.')
    approve_drivers.short_description = "Approve driver verification"
    
    def reject_drivers(self, request, queryset):
        """Reject driver verification for selected users"""
        driver_users = queryset.filter(is_driver=True)
        count = driver_users.update(
            driver_verification_status='rejected',
            verification_rejected_at=timezone.now(),
            verification_rejection_reason='Bulk rejection by admin'
        )
        self.message_user(request, f'{count} driver(s) rejected.')
    reject_drivers.short_description = "Reject driver verification"
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) activated.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) deactivated.')
    deactivate_users.short_description = "Deactivate selected users"
    
    def send_welcome_email(self, request, queryset):
        """Send welcome email to selected users"""
        count = 0
        for user in queryset:
            try:
                send_mail(
                    'Welcome to Carwaan!',
                    f'Dear {user.first_name or user.username},\n\nWelcome to Carwaan! We\'re excited to have you on board.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                count += 1
            except Exception:
                pass
        self.message_user(request, f'Welcome email sent to {count} user(s).')
    send_welcome_email.short_description = "Send welcome email"
    
    def send_verification_reminder(self, request, queryset):
        """Send verification reminder to selected users"""
        count = 0
        for user in queryset.filter(is_driver=True, driver_verification_status='pending'):
            try:
                send_mail(
                    'Complete Your Driver Verification - Carwaan',
                    f'Dear {user.first_name or user.username},\n\nPlease complete your driver verification to start offering rides.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                count += 1
            except Exception:
                pass
        self.message_user(request, f'Verification reminder sent to {count} user(s).')
    send_verification_reminder.short_description = "Send verification reminder"
    
    def bulk_email_users(self, request, queryset):
        """Send bulk email to selected users"""
        # This would open a form to compose bulk email
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        return redirect(f'/admin/bulk-email/?users={",".join(selected)}')
    bulk_email_users.short_description = "Send bulk email to selected users"


# Enhanced User Admin
class UserAdmin(BaseUserAdmin, ImportExportModelAdmin if HAS_IMPORT_EXPORT else admin.ModelAdmin):
    if HAS_IMPORT_EXPORT:
        resource_class = UserResource
    
    list_display = ('id', 'username_link', 'full_name_display', 'email', 'phone', 
                   'role_badge', 'driver_verification_badge', 'rating_display', 
                   'rides_stats', 'status_badges', 'last_login_display')
    
    list_filter = ('role', 'is_driver', 'driver_verification_status', 'gender', 
                  'is_verified', 'email_verified', 'is_staff', 'is_active', 
                  'workplace', 'department', 'created_at', 'last_login')
    
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone', 
                    'cnic_number', 'driver_license_number', 'workplace', 'department')
    
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 25
    
    actions = ['verify_users', 'unverify_users', 'approve_drivers', 'reject_drivers',
              'send_welcome_email', 'export_user_report', 'activate_users', 'deactivate_users',
              'send_verification_reminder', 'bulk_email_users']
    
    # Enhanced fieldsets
    fieldsets = (
        ('Basic Information', {
            'fields': ('username', 'email', 'password', 'role'),
            'classes': ('wide',)
        }),
        ('Personal Details', {
            'fields': ('first_name', 'last_name', 'gender', 'date_of_birth', 'phone', 
                      'profile_picture', 'bio', 'cnic_number'),
            'classes': ('wide',)
        }),
        ('Driver Information', {
            'fields': ('is_driver', 'driver_verification_status', 'driver_license_number',
                      'verification_submitted_at', 'verification_approved_at', 'verification_rejected_at',
                      'verification_rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Driver Documents', {
            'fields': ('cnic_front_image_preview', 'cnic_front_image', 'cnic_back_image_preview', 'cnic_back_image', 
                      'driver_license_front_image_preview', 'driver_license_front_image', 
                      'driver_license_back_image_preview', 'driver_license_back_image'),
            'classes': ('collapse',)
        }),
        ('Verification Status', {
            'fields': ('is_verified', 'email_verified', 'otp_code', 'otp_created_at', 'otp_attempts'),
            'classes': ('collapse',)
        }),
        ('Location Information', {
            'fields': ('address', 'workplace', 'department', 'workplace_address'),
            'classes': ('collapse',)
        }),
        # Preferences section removed - fields don't exist in model
        ('Statistics', {
            'fields': ('average_rating_display', 'total_rides_offered', 'total_rides_taken',
                      'rides_offered_count_display', 'rides_taken_count_display'),
            'classes': ('collapse',)
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'verification_submitted_at', 
                      'verification_approved_at',
                      'last_login', 'date_joined',
                      'average_rating_display', 'total_rides_offered', 'total_rides_taken',
                      'rides_offered_count_display', 'rides_taken_count_display',
                      'cnic_front_image_preview', 'cnic_back_image_preview',
                      'driver_license_front_image_preview', 'driver_license_back_image_preview')
    
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related().prefetch_related(
            'offered_rides', 'joined_rides', 'vehicles'
        ).annotate(
            rides_offered_count=Count('offered_rides', distinct=True),
            rides_taken_count=Count('joined_rides', distinct=True)
        )
    
    # Custom URLs temporarily removed to fix AttributeError
    # TODO: Move custom view methods into UserAdmin class if needed
    
    # Custom display methods
    def username_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.id])
        return format_html('<a href="{}" style="font-weight: bold; color: #007bff;">{}</a>', url, obj.username)
    username_link.short_description = "Username"
    username_link.admin_order_field = 'username'
    
    def full_name_display(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        if full_name:
            return format_html('<span title="{}">{}</span>', obj.email, full_name)
        return format_html('<span style="color: #999;" title="{}">No name set</span>', obj.email)
    full_name_display.short_description = "Full Name"
    full_name_display.admin_order_field = 'first_name'
    
    def role_badge(self, obj):
        colors = {
            'admin': '#dc3545',
            'driver': '#28a745', 
            'passenger': '#007bff',
            'moderator': '#fd7e14'
        }
        color = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 15px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.role.upper()
        )
    role_badge.short_description = "Role"
    role_badge.admin_order_field = 'role'
    
    def driver_verification_badge(self, obj):
        if not obj.is_driver:
            return format_html('<span style="color: #999; font-size: 11px;">Not a driver</span>')
        
        colors = {
            'pending': '#ffc107',
            'under_review': '#fd7e14',
            'verified': '#28a745',
            'rejected': '#dc3545'
        }
        color = colors.get(obj.driver_verification_status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 15px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.driver_verification_status.replace('_', ' ').upper()
        )
    driver_verification_badge.short_description = "Driver Status"
    driver_verification_badge.admin_order_field = 'driver_verification_status'
    
    def rating_display(self, obj):
        if hasattr(obj, 'average_rating') and obj.average_rating:
            try:
                rating = float(obj.average_rating)
                full_stars = int(rating)
                half_star = 1 if rating % 1 >= 0.5 else 0
                empty_stars = 5 - full_stars - half_star
                
                stars = "★" * full_stars + "☆" * half_star + "☆" * empty_stars
                return format_html(
                    '<span title="Rating: {}/5.0">{} <span style="color: #ffc107;">{}</span></span>',
                    rating, rating, stars
                )
            except (ValueError, TypeError):
                return format_html('<span style="color: #999; font-size: 11px;">Invalid rating</span>')
        return format_html('<span style="color: #999; font-size: 11px;">No ratings</span>')
    rating_display.short_description = "Rating"
    rating_display.admin_order_field = 'average_rating'
    
    def rides_stats(self, obj):
        offered = getattr(obj, 'rides_offered_count', 0)
        taken = getattr(obj, 'rides_taken_count', 0)
        return format_html(
            '<div style="font-size: 11px; line-height: 1.3;">'
            '<div style="color: #28a745;">📤 {}</div>'
            '<div style="color: #007bff;">📥 {}</div>'
            '</div>',
            offered, taken
        )
    rides_stats.short_description = "Rides"
    
    def status_badges(self, obj):
        badges = []
        if obj.is_verified:
            badges.append('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">✓ VERIFIED</span>')
        if obj.email_verified:
            badges.append('<span style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">✉ EMAIL</span>')
        if obj.is_staff:
            badges.append('<span style="background: #6f42c1; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">👑 STAFF</span>')
        if not obj.is_active:
            badges.append('<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">⛔ INACTIVE</span>')
        
        return format_html('<div style="display: flex; flex-direction: column; gap: 2px;">{}</div>', 
                          ''.join(badges) if badges else '<span style="color: #999; font-size: 11px;">-</span>')
    status_badges.short_description = "Status"
    
    def last_login_display(self, obj):
        if obj.last_login:
            return format_html('<span title="{}">{}</span>', 
                             obj.last_login.strftime("%Y-%m-%d %H:%M:%S"), 
                             obj.last_login.strftime("%m/%d"))
        return format_html('<span style="color: #999;">Never</span>')
    last_login_display.short_description = "Last Login"
    last_login_display.admin_order_field = 'last_login'
    
    # Image preview methods
    def cnic_front_image_preview(self, obj):
        if obj.cnic_front_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" />',
                obj.cnic_front_image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    cnic_front_image_preview.short_description = "CNIC Front Preview"
    
    def cnic_back_image_preview(self, obj):
        if obj.cnic_back_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" />',
                obj.cnic_back_image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    cnic_back_image_preview.short_description = "CNIC Back Preview"
    
    def driver_license_front_image_preview(self, obj):
        if obj.driver_license_front_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" />',
                obj.driver_license_front_image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    driver_license_front_image_preview.short_description = "License Front Preview"
    
    def driver_license_back_image_preview(self, obj):
        if obj.driver_license_back_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" />',
                obj.driver_license_back_image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    driver_license_back_image_preview.short_description = "License Back Preview"
    
    # Statistics display methods
    def average_rating_display(self, obj):
        return self.rating_display(obj)
    average_rating_display.short_description = "Average Rating"
    
    def rides_offered_count_display(self, obj):
        count = getattr(obj, 'rides_offered_count', 0)
        return format_html('<strong style="color: #28a745;">{}</strong>', count)
    rides_offered_count_display.short_description = "Rides Offered"
    
    def rides_taken_count_display(self, obj):
        count = getattr(obj, 'rides_taken_count', 0)
        return format_html('<strong style="color: #007bff;">{}</strong>', count)
    rides_taken_count_display.short_description = "Rides Taken"
    
    # Custom actions
    def verify_users(self, request, queryset):
        queryset.update(is_verified=True, email_verified=True)
        self.message_user(request, f'{queryset.count()} users marked as verified.')
    verify_users.short_description = 'Mark selected users as verified'
    
    def unverify_users(self, request, queryset):
        queryset.update(is_verified=False)
        self.message_user(request, f'{queryset.count()} users marked as unverified.')
    unverify_users.short_description = 'Mark selected users as unverified'
    
    def approve_drivers(self, request, queryset):
        updated = queryset.filter(
            driver_verification_status__in=['pending', 'under_review']
        ).update(
            driver_verification_status='verified',
            is_driver=True,
            verification_approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} drivers approved.')
    approve_drivers.short_description = 'Approve selected drivers'
    
    def reject_drivers(self, request, queryset):
        updated = queryset.filter(
            driver_verification_status__in=['pending', 'under_review']
        ).update(
            driver_verification_status='rejected',
            verification_rejected_at=timezone.now()
        )
        self.message_user(request, f'{updated} drivers rejected.')
    reject_drivers.short_description = 'Reject selected drivers'
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def export_user_report(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="users_report_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Username', 'Email', 'Full Name', 'Phone', 'Role', 'Driver Status', 
                        'Verification Status', 'Rides Offered', 'Rides Taken', 'Rating', 
                        'Last Login', 'Date Joined'])
        
        for user in queryset:
            writer.writerow([
                user.username,
                user.email,
                f"{user.first_name} {user.last_name}".strip(),
                user.phone,
                user.role,
                'Yes' if user.is_driver else 'No',
                user.driver_verification_status if user.is_driver else 'N/A',
                user.offered_rides.count(),
                user.joined_rides.count(),
                user.average_rating or 'No ratings',
                user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
                user.date_joined.strftime('%Y-%m-%d %H:%M')
            ])
        
        self.message_user(request, f'Exported {queryset.count()} users to CSV.')
        return response
    export_user_report.short_description = 'Export selected users to CSV'


# Vehicle admin is now in admin_vehicle.py - removed duplicate class definition
# Enhanced Vehicle Admin moved to admin_vehicle.py


# Enhanced Payment Method Admin
class PaymentMethodAdmin(ImportExportModelAdmin if HAS_IMPORT_EXPORT else admin.ModelAdmin):
    if HAS_IMPORT_EXPORT:
        resource_class = PaymentMethodResource
    
    list_display = ('id', 'user_link', 'type_badge', 'holder_name', 'masked_number', 
                   'brand_badge', 'default_badge', 'status_badge', 'created_at')
    list_filter = ('type', 'brand', 'is_default', 'is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'holder_name', 'last_four', 'phone_number')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('user', 'type', 'holder_name')
        }),
        ('Card/Account Details', {
            'fields': ('last_four', 'brand', 'phone_number', 'bank_name'),
            'classes': ('wide',)
        }),
        ('Status', {
            'fields': ('is_default', 'is_active'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def user_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = "User"
    user_link.admin_order_field = 'user__username'
    
    def type_badge(self, obj):
        colors = {
            'card': '#007bff',
            'bank': '#28a745',
            'mobile': '#ffc107'
        }
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.type.upper()
        )
    type_badge.short_description = "Type"
    type_badge.admin_order_field = 'type'
    
    def masked_number(self, obj):
        if obj.last_four:
            return f"****{obj.last_four}"
        return obj.phone_number or "-"
    masked_number.short_description = "Number"
    
    def brand_badge(self, obj):
        if obj.brand:
            return format_html(
                '<span style="background: #6c757d; color: white; padding: 2px 8px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
                obj.brand.upper()
            )
        return "-"
    brand_badge.short_description = "Brand"
    
    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span style="background: #ffc107; color: black; padding: 2px 8px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">⭐ DEFAULT</span>'
            )
        return "-"
    default_badge.short_description = "Default"
    default_badge.admin_order_field = 'is_default'
    
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 8px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">✗ INACTIVE</span>'
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'is_active'


# Custom Admin Site Configuration
class CarwaanAdminSite(admin.AdminSite):
    site_header = "Carwaan Administration"
    site_title = "Carwaan Admin"
    index_title = "Welcome to Carwaan Administration"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls
    
    def index(self, request, extra_context=None):
        # Redirect to custom dashboard
        return redirect('admin:dashboard')


# Register models with enhanced admin
admin.site.register(User, UserAdmin)
# Vehicle is registered in admin_vehicle.py
admin.site.register(PaymentMethod, PaymentMethodAdmin)

# Customize admin site
admin.site.site_header = "Carwaan Administration"
admin.site.site_title = "Carwaan Admin"
admin.site.index_title = "Welcome to Carwaan Administration"

# Customize admin site
admin.site.site_header = "Carwaan Administration"
admin.site.site_title = "Carwaan Admin"
admin.site.index_title = "Welcome to Carwaan Administration"

# Customize admin site
admin.site.site_header = "Carwaan Administration"
admin.site.site_title = "Carwaan Admin"
admin.site.index_title = "Welcome to Carwaan Administration"
