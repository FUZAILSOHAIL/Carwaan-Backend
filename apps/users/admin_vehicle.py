from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q, Avg
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
import csv

try:
    from import_export import resources, fields
    from import_export.admin import ImportExportModelAdmin
    from import_export.widgets import ForeignKeyWidget
    HAS_IMPORT_EXPORT = True
except ImportError:
    HAS_IMPORT_EXPORT = False
    ImportExportModelAdmin = admin.ModelAdmin

from .models_vehicle import Vehicle
from .models import User


if HAS_IMPORT_EXPORT:
    class VehicleResource(resources.ModelResource):
        owner = fields.Field(
            column_name='owner',
            attribute='owner',
            widget=ForeignKeyWidget(User, 'username')
        )
        full_name = fields.Field(column_name='full_name')
        rides_count = fields.Field(column_name='rides_count')
        
        class Meta:
            model = Vehicle
            fields = ('id', 'owner', 'full_name', 'make', 'model', 'year', 'color', 
                     'license_plate', 'vehicle_type', 'total_seats', 'fuel_type', 
                     'ac_type', 'is_verified', 'verification_status', 'is_active', 
                     'rides_count', 'created_at')
            export_order = fields
        
        def dehydrate_full_name(self, vehicle):
            return f"{vehicle.owner.first_name} {vehicle.owner.last_name}".strip() or vehicle.owner.username
        
        def dehydrate_rides_count(self, vehicle):
            return vehicle.rides.count()


class VehicleAdmin(ImportExportModelAdmin):
    if HAS_IMPORT_EXPORT:
        resource_class = VehicleResource
    
    list_display = ('id', 'owner_link', 'vehicle_display', 'license_plate_display', 
                   'type_badge', 'seats_display', 'verification_badge', 'status_badge',
                   'rides_count_display', 'created_at_display')
    
    list_filter = ('is_verified', 'is_active', 'verification_status', 'vehicle_type', 
                  'fuel_type', 'ac_type', 'year', 'make', 'created_at')
    
    search_fields = ('owner__username', 'owner__first_name', 'owner__last_name', 
                    'make', 'model', 'license_plate', 'color', 'owner__email', 'owner__phone')
    
    readonly_fields = ('created_at', 'updated_at', 'verification_submitted_at', 
                      'verification_approved_at', 'rides_count')
    
    raw_id_fields = ('owner',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    actions = ['verify_vehicles', 'unverify_vehicles', 'approve_verification', 
              'reject_verification', 'activate_vehicles', 'deactivate_vehicles',
              'export_vehicle_report']
    
    fieldsets = (
        ('Owner Information', {
            'fields': ('owner',),
            'classes': ('wide',)
        }),
        ('Vehicle Details', {
            'fields': ('make', 'model', 'year', 'color', 'license_plate', 'vehicle_type'),
            'classes': ('wide',)
        }),
        ('Specifications', {
            'fields': ('total_seats', 'available_seats_for_ride', 'fuel_type', 'ac_type', 'engine_capacity'),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': ('is_verified', 'verification_status', 
                      'verification_submitted_at', 'verification_approved_at'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('registration_book_image', 'car_registration_book_image', 'car_image'),
            'classes': ('collapse',)
        }),
        ('Comfort Features', {
            'fields': ('has_ac', 'has_music_system', 'has_phone_charger', 'smoking_allowed', 
                      'insurance_valid', 'fitness_certificate_valid'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('is_primary', 'notes'),
            'classes': ('collapse',)
        }),
        ('Status & Statistics', {
            'fields': ('is_active', 'rides_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner').prefetch_related('rides')
    
    # Custom display methods
    def owner_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.owner.id])
        full_name = f"{obj.owner.first_name} {obj.owner.last_name}".strip()
        display_name = full_name if full_name else obj.owner.username
        
        return format_html(
            '<a href="{}" style="text-decoration: none;">'
            '<strong>{}</strong><br>'
            '<small style="color: #666;">{}</small><br>'
            '<small style="color: #999;">{}</small>'
            '</a>', 
            url, display_name, obj.owner.username, obj.owner.email
        )
    owner_link.short_description = "Owner"
    owner_link.admin_order_field = 'owner__username'
    
    def vehicle_display(self, obj):
        return format_html(
            '<div style="line-height: 1.4;">'
            '<strong style="color: #333;">{} {} {}</strong><br>'
            '<span style="color: #666; font-size: 12px;">🎨 {}</span>'
            '</div>',
            obj.make, obj.model, obj.year, obj.color.title()
        )
    vehicle_display.short_description = "Vehicle"
    vehicle_display.admin_order_field = 'make'
    
    def license_plate_display(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; border: 2px solid #007bff; '
            'border-radius: 6px; padding: 4px 8px; text-align: center; '
            'font-family: monospace; font-weight: bold; font-size: 14px; '
            'color: #007bff; min-width: 80px;">{}</div>',
            obj.license_plate
        )
    license_plate_display.short_description = "License Plate"
    license_plate_display.admin_order_field = 'license_plate'
    
    def type_badge(self, obj):
        colors = {
            'sedan': '#007bff',
            'hatchback': '#28a745',
            'suv': '#fd7e14',
            'crossover': '#20c997',
            'coupe': '#6f42c1',
            'convertible': '#e83e8c',
            'wagon': '#6c757d'
        }
        icons = {
            'sedan': '🚗',
            'hatchback': '🚙',
            'suv': '🚐',
            'crossover': '🚗',
            'coupe': '🏎️',
            'convertible': '🚗',
            'wagon': '🚐'
        }
        color = colors.get(obj.vehicle_type, '#6c757d')
        icon = icons.get(obj.vehicle_type, '🚗')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">'
            '{} {}</span>',
            color, icon, obj.get_vehicle_type_display().upper()
        )
    type_badge.short_description = "Type"
    type_badge.admin_order_field = 'vehicle_type'
    
    def seats_display(self, obj):
        return format_html(
            '<div style="text-align: center;">'
            '<span style="background: #e9ecef; border-radius: 50%; '
            'width: 30px; height: 30px; display: inline-flex; '
            'align-items: center; justify-content: center; '
            'font-weight: bold; color: #495057;">👥</span><br>'
            '<small style="font-weight: bold;">{} seats</small>'
            '</div>',
            obj.total_seats
        )
    seats_display.short_description = "Capacity"
    seats_display.admin_order_field = 'total_seats'
    
    def verification_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'under_review': '#fd7e14',
            'approved': '#28a745',
            'rejected': '#dc3545'
        }
        icons = {
            'pending': '⏳',
            'under_review': '🔍',
            'approved': '✅',
            'rejected': '❌'
        }
        color = colors.get(obj.verification_status, '#6c757d')
        icon = icons.get(obj.verification_status, '❓')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">'
            '{} {}</span>',
            color, icon, obj.verification_status.replace('_', ' ').upper()
        )
    verification_badge.short_description = "Verification"
    verification_badge.admin_order_field = 'verification_status'
    
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 6px; '
                'border-radius: 8px; font-size: 10px; font-weight: bold;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 2px 6px; '
            'border-radius: 8px; font-size: 10px; font-weight: bold;">✗ INACTIVE</span>'
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'is_active'
    
    def rides_count_display(self, obj):
        count = getattr(obj, 'rides_count', 0)
        if count > 0:
            return format_html(
                '<div style="text-align: center;">'
                '<span style="background: #007bff; color: white; border-radius: 50%; '
                'width: 25px; height: 25px; display: inline-flex; '
                'align-items: center; justify-content: center; '
                'font-weight: bold; font-size: 11px;">🚗</span><br>'
                '<small style="font-weight: bold; color: #007bff;">{}</small>'
                '</div>',
                count
            )
        return format_html(
            '<div style="text-align: center; color: #999;">'
            '<span style="font-size: 20px;">🚗</span><br>'
            '<small>0</small>'
            '</div>'
        )
    rides_count_display.short_description = "Rides"
    rides_count_display.admin_order_field = 'rides_count'
    
    def created_at_display(self, obj):
        return format_html(
            '<span title="{}">{}</span>',
            obj.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            obj.created_at.strftime('%m/%d/%y')
        )
    created_at_display.short_description = "Added"
    created_at_display.admin_order_field = 'created_at'
    
    def rides_count(self, obj):
        return obj.rides.count()
    rides_count.short_description = "Total Rides"
    
    # Custom actions
    def verify_vehicles(self, request, queryset):
        updated = queryset.update(
            is_verified=True, 
            verification_status='approved',
            verification_approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} vehicles marked as verified.')
    verify_vehicles.short_description = 'Mark selected vehicles as verified'
    
    def unverify_vehicles(self, request, queryset):
        updated = queryset.update(
            is_verified=False, 
            verification_status='pending'
        )
        self.message_user(request, f'{updated} vehicles marked as unverified.')
    unverify_vehicles.short_description = 'Mark selected vehicles as unverified'
    
    def approve_verification(self, request, queryset):
        updated = queryset.filter(
            verification_status__in=['pending', 'under_review']
        ).update(
            verification_status='approved',
            is_verified=True,
            verification_approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} vehicle verifications approved.')
    approve_verification.short_description = 'Approve vehicle verification'
    
    def reject_verification(self, request, queryset):
        updated = queryset.filter(
            verification_status__in=['pending', 'under_review']
        ).update(
            verification_status='rejected',
            is_verified=False
        )
        self.message_user(request, f'{updated} vehicle verifications rejected.')
    reject_verification.short_description = 'Reject vehicle verification'
    
    def activate_vehicles(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} vehicles activated.')
    activate_vehicles.short_description = 'Activate selected vehicles'
    
    def deactivate_vehicles(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} vehicles deactivated.')
    deactivate_vehicles.short_description = 'Deactivate selected vehicles'
    
    def export_vehicle_report(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="vehicles_report_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Owner', 'Make', 'Model', 'Year', 'Color', 'License Plate', 
                        'Type', 'Seats', 'Fuel Type', 'AC Type', 'Verification Status', 
                        'Is Active', 'Rides Count', 'Created Date'])
        
        for vehicle in queryset:
            writer.writerow([
                vehicle.id,
                vehicle.owner.username,
                vehicle.make,
                vehicle.model,
                vehicle.year,
                vehicle.color,
                vehicle.license_plate,
                vehicle.get_vehicle_type_display(),
                vehicle.total_seats,
                vehicle.get_fuel_type_display(),
                vehicle.get_ac_type_display(),
                vehicle.verification_status,
                'Yes' if vehicle.is_active else 'No',
                vehicle.rides.count(),
                vehicle.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        self.message_user(request, f'Exported {queryset.count()} vehicles to CSV.')
        return response
    export_vehicle_report.short_description = 'Export selected vehicles to CSV'
    
    def vehicle_info(self, obj):
        return format_html(
            '<strong>{} {} ({})</strong><br><span style="color: #666; font-size: 11px;">{} • {}</span>',
            obj.make, obj.model, obj.year, obj.color.title(), obj.get_vehicle_type_display()
        )
    vehicle_info.short_description = 'Vehicle'
    
    def seats_display(self, obj):
        return format_html(
            '<span style="font-weight: bold;">{} seats</span>',
            obj.total_seats
        )
    seats_display.short_description = 'Capacity'
    seats_display.admin_order_field = 'total_seats'
    
    def verification_status(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified</span>'
            )
        elif obj.verification_status == 'rejected':
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Rejected</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Pending</span>'
            )
    verification_status.short_description = 'Verification'
    verification_status.admin_order_field = 'is_verified'
    
    def active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    active_status.short_description = 'Status'
    active_status.admin_order_field = 'is_active'
    
    def rides_count_display(self, obj):
        """Display the number of rides for this vehicle"""
        rides_count = getattr(obj, 'rides_count', 0)
        return format_html(
            '<span style="font-weight: bold; color: #0066cc;">{} rides</span>',
            rides_count
        )
    rides_count_display.short_description = 'Rides'
    rides_count_display.admin_order_field = 'rides_count'


# Register the Vehicle admin
admin.site.register(Vehicle, VehicleAdmin)
