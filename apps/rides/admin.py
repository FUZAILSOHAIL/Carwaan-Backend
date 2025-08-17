from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Q, Avg, Sum
from django.utils.safestring import mark_safe
from django.utils import timezone
from datetime import timedelta

try:
    from import_export import resources, fields
    from import_export.admin import ImportExportModelAdmin
    from import_export.widgets import ForeignKeyWidget
    HAS_IMPORT_EXPORT = True
except ImportError:
    HAS_IMPORT_EXPORT = False
    ImportExportModelAdmin = admin.ModelAdmin

from .models import Ride, RidePassenger, Location, RoutePoint, RideStop, ScheduledRide, RideReview, RideDirection, FareCalculation, RideRequest


if HAS_IMPORT_EXPORT:
    class RideResource(resources.ModelResource):
        class Meta:
            model = Ride
            fields = ('id', 'driver__username', 'pickup_location', 'dropoff_location', 
                     'departure_time', 'status', 'ride_type', 'total_seats', 'available_seats',
                     'price_per_seat', 'created_at')
            export_order = fields


    class RidePassengerResource(resources.ModelResource):
        class Meta:
            model = RidePassenger
            fields = ('id', 'ride__id', 'passenger__username', 'status', 'relationship',
                     'contribution_amount', 'has_contributed', 'joined_at')
            export_order = fields


class RoutePointInline(admin.TabularInline):
    model = RoutePoint
    extra = 0
    fields = ('sequence', 'latitude', 'longitude')
    ordering = ('sequence',)


class RideStopInline(admin.TabularInline):
    model = RideStop
    extra = 0
    fields = ('sequence', 'location_name', 'address', 'latitude', 'longitude', 'scheduled_time')
    ordering = ('sequence',)


class RidePassengerInline(admin.TabularInline):
    model = RidePassenger
    extra = 0
    fields = ('passenger', 'status', 'relationship', 'contribution_amount', 'has_contributed')
    readonly_fields = ('joined_at',)


class RideAdmin(ImportExportModelAdmin):
    if HAS_IMPORT_EXPORT:
        resource_class = RideResource
    list_display = ('id', 'driver_link', 'ride_route', 'departure_time', 'ride_type',
                   'seats_display', 'status_display', 'recurring', 'price_display', 
                   'passenger_count', 'created_at')
    list_filter = ('status', 'ride_type', 'recurring', 'is_workplace_ride', 'gender_preference',
                  'created_at', 'departure_time', 'has_stops', 'cost_splitting')
    search_fields = ('driver__username', 'driver__first_name', 'driver__last_name',
                    'pickup_location', 'dropoff_location', 'notes', 'route_description')
    readonly_fields = ('created_at', 'updated_at', 'available_seats', 'average_rating', 
                      'total_ratings', 'passenger_count', 'current_male_passengers', 
                      'current_female_passengers')
    raw_id_fields = ('driver',)
    inlines = [RideStopInline, RoutePointInline, RidePassengerInline]
    date_hierarchy = 'departure_time'
    
    # Add actions
    actions = ['mark_as_active', 'mark_as_completed', 'mark_as_cancelled', 'duplicate_ride']
    
    def mark_as_active(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f'{queryset.count()} rides marked as active.')
    mark_as_active.short_description = 'Mark selected rides as active'
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f'{queryset.count()} rides marked as completed.')
    mark_as_completed.short_description = 'Mark selected rides as completed'
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f'{queryset.count()} rides marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark selected rides as cancelled'
    
    def duplicate_ride(self, request, queryset):
        # Implementation for duplicating rides
        count = 0
        for ride in queryset:
            ride.pk = None
            ride.status = 'active'
            ride.save()
            count += 1
        self.message_user(request, f'{count} rides duplicated.')
    duplicate_ride.short_description = 'Duplicate selected rides'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('driver', 'departure_time', 'status', 'ride_type')
        }),
        ('Route Information', {
            'fields': ('pickup_location', 'pickup_latitude', 'pickup_longitude',
                      'dropoff_location', 'dropoff_latitude', 'dropoff_longitude',
                      'route_description', 'estimated_distance_km', 'estimated_duration_minutes')
        }),
        ('Capacity & Pricing', {
            'fields': ('total_seats', 'available_seats', 'price_per_seat', 'cost_splitting')
        }),
        ('Ride Details', {
            'fields': ('notes', 'comfort_features', 'is_private')
        }),
        ('Preferences & Settings', {
            'fields': ('gender_preference', 'is_workplace_ride', 'friend_group', 'workplace_department')
        }),
        ('Recurring Settings', {
            'fields': ('recurring', 'recurring_days', 'time_flexibility_minutes')
        }),
        ('Stops & Route', {
            'fields': ('has_stops', 'polyline'),
            'classes': ('collapse',)
        }),
        ('Ratings & Statistics', {
            'fields': ('average_rating', 'total_ratings', 'current_male_passengers', 
                      'current_female_passengers', 'passenger_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver').annotate(
            passenger_count=Count('ridepassenger')
        )
    
    def driver_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.driver.id])
        return format_html('<a href="{}">{}</a>', url, obj.driver)
    driver_link.short_description = 'Driver'
    driver_link.admin_order_field = 'driver__username'
    
    def ride_route(self, obj):
        return format_html(
            '<span title="Route: {} to {}">{} → {}</span>',
            obj.pickup_location, obj.dropoff_location,
            obj.pickup_location[:30] + "..." if len(obj.pickup_location) > 30 else obj.pickup_location,
            obj.dropoff_location[:30] + "..." if len(obj.dropoff_location) > 30 else obj.dropoff_location
        )
    ride_route.short_description = 'Route'
    
    def seats_display(self, obj):
        color = "green" if obj.available_seats > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{}</span>',
            color, obj.available_seats, obj.total_seats
        )
    seats_display.short_description = 'Seats (Avail/Total)'
    seats_display.admin_order_field = 'available_seats'
    
    def status_display(self, obj):
        colors = {
            'active': 'green',
            'completed': 'blue',
            'cancelled': 'red',
            'pending': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def price_display(self, obj):
        return f"₨{obj.price_per_seat}" if obj.price_per_seat else "Free"
    price_display.short_description = 'Price/Seat'
    price_display.admin_order_field = 'price_per_seat'
    
    def passenger_count(self, obj):
        return getattr(obj, 'passenger_count', 0)
    passenger_count.short_description = 'Passengers'
    passenger_count.admin_order_field = 'passenger_count'


class RidePassengerAdmin(ImportExportModelAdmin):
    if HAS_IMPORT_EXPORT:
        resource_class = RidePassengerResource
    list_display = ('id', 'ride_link', 'passenger_link', 'status_display', 'relationship', 
                   'joined_at', 'contribution_status')
    list_filter = ('status', 'relationship', 'joined_at', 'has_contributed', 'regular_passenger')
    search_fields = ('ride__id', 'ride__pickup_location', 'ride__dropoff_location', 
                    'passenger__username', 'passenger__first_name', 'passenger__last_name', 
                    'pickup_note')
    raw_id_fields = ('ride', 'passenger', 'invited_by')
    readonly_fields = ('created_at', 'updated_at', 'joined_at')
    date_hierarchy = 'joined_at'
    
    # Add actions
    actions = ['mark_as_confirmed', 'mark_as_completed', 'mark_as_cancelled', 'mark_as_paid']
    
    def mark_as_confirmed(self, request, queryset):
        queryset.update(status='confirmed')
        self.message_user(request, f'{queryset.count()} passengers marked as confirmed.')
    mark_as_confirmed.short_description = 'Mark selected passengers as confirmed'
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f'{queryset.count()} passengers marked as completed.')
    mark_as_completed.short_description = 'Mark selected passengers as completed'
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f'{queryset.count()} passengers marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark selected passengers as cancelled'
    
    def mark_as_paid(self, request, queryset):
        queryset.update(has_contributed=True)
        self.message_user(request, f'{queryset.count()} passengers marked as paid.')
    mark_as_paid.short_description = 'Mark selected passengers as paid'
    
    fieldsets = (
        ('Ride Information', {
            'fields': ('ride', 'passenger', 'status', 'joined_at')
        }),
        ('Pickup Details', {
            'fields': ('pickup_note',)
        }),
        ('Relationship & Payment', {
            'fields': ('relationship', 'contribution_amount', 'has_contributed')
        }),
        ('Social Aspects', {
            'fields': ('invited_by', 'regular_passenger')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ride', 'passenger', 'invited_by')
    
    def ride_link(self, obj):
        url = reverse("admin:rides_ride_change", args=[obj.ride.id])
        return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
    ride_link.short_description = 'Ride'
    ride_link.admin_order_field = 'ride__id'
    
    def passenger_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.passenger.id])
        return format_html('<a href="{}">{}</a>', url, obj.passenger)
    passenger_link.short_description = 'Passenger'
    passenger_link.admin_order_field = 'passenger__username'
    
    def status_display(self, obj):
        colors = {
            'confirmed': 'green',
            'completed': 'blue',
            'cancelled': 'red',
            'pending': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def contribution_status(self, obj):
        if obj.has_contributed:
            return format_html('<span style="color: green;">✓ Paid ₨{}</span>', obj.contribution_amount)
        elif obj.contribution_amount and obj.contribution_amount > 0:
            return format_html('<span style="color: red;">✗ Pending ₨{}</span>', obj.contribution_amount)
        return format_html('<span style="color: gray;">—</span>')
    contribution_status.short_description = 'Payment'


class LocationAdmin(ImportExportModelAdmin):
    list_display = ('id', 'name', 'address', 'city', 'location_type', 'coordinates', 'usage_count')
    list_filter = ('is_workplace', 'is_landmark', 'is_university', 'city', 'state')
    search_fields = ('name', 'address', 'city', 'state')
    readonly_fields = ('usage_count',)
    
    def get_queryset(self, request):
        # Since pickup_location and dropoff_location are CharField, 
        # we'll just return the base queryset and calculate usage in the method
        return super().get_queryset(request)
    
    fieldsets = (
        ('Location Information', {
            'fields': ('name', 'address', 'city', 'state')
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude')
        }),
        ('Location Type', {
            'fields': ('is_workplace', 'is_landmark', 'is_university')
        }),
        ('Usage Statistics', {
            'fields': ('usage_count',),
            'classes': ('collapse',)
        }),
    )
    
    def location_type(self, obj):
        types = []
        if obj.is_workplace:
            types.append('<span class="badge badge-primary">Workplace</span>')
        if obj.is_landmark:
            types.append('<span class="badge badge-success">Landmark</span>')
        if obj.is_university:
            types.append('<span class="badge badge-info">University</span>')
        return mark_safe(" ".join(types)) if types else "Regular"
    location_type.short_description = 'Type'
    
    def coordinates(self, obj):
        return f"{obj.latitude:.6f}, {obj.longitude:.6f}"
    coordinates.short_description = 'Coordinates'
    
    def usage_count(self, obj):
        # Count rides that use this location as pickup or dropoff
        pickup_count = Ride.objects.filter(pickup_location__icontains=obj.name).count()
        dropoff_count = Ride.objects.filter(dropoff_location__icontains=obj.name).count()
        return pickup_count + dropoff_count
    usage_count.short_description = 'Usage Count'
    usage_count.admin_order_field = 'usage_count'


class RoutePointAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride_link', 'sequence', 'coordinates')
    list_filter = ('ride__status', 'ride__ride_type')
    search_fields = ('ride__id', 'ride__pickup_location', 'ride__dropoff_location')
    raw_id_fields = ('ride',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ride')
    
    def ride_link(self, obj):
        url = reverse("admin:rides_ride_change", args=[obj.ride.id])
        return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
    ride_link.short_description = 'Ride'
    ride_link.admin_order_field = 'ride__id'
    
    def coordinates(self, obj):
        return f"{obj.latitude:.6f}, {obj.longitude:.6f}"
    coordinates.short_description = 'Coordinates'


class RideStopAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride_link', 'location_name', 'sequence', 'coordinates', 'scheduled_time')
    list_filter = ('ride__status', 'ride__ride_type')
    search_fields = ('ride__id', 'location_name', 'address', 'ride__pickup_location', 'ride__dropoff_location')
    raw_id_fields = ('ride',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ride')
    
    def ride_link(self, obj):
        url = reverse("admin:rides_ride_change", args=[obj.ride.id])
        return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
    ride_link.short_description = 'Ride'
    ride_link.admin_order_field = 'ride__id'
    
    def coordinates(self, obj):
        return f"{obj.latitude:.6f}, {obj.longitude:.6f}"
    coordinates.short_description = 'Coordinates'


# Additional model registrations for missing models
from .models import (
    ScheduledRide, RideReview, RideDirection, FareCalculation, RideRequest
)

class ScheduledRideAdmin(ImportExportModelAdmin):
    list_display = ('id', 'user_link', 'ride_type_display', 'route_display', 'scheduled_date', 'scheduled_time', 'is_active')
    list_filter = ('is_driver', 'is_active', 'scheduled_date', 'gender_preference')
    search_fields = ('user__username', 'pickup_location', 'dropoff_location', 'notes')
    raw_id_fields = ('user', 'matched_ride')
    date_hierarchy = 'scheduled_date'
    
    def user_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def ride_type_display(self, obj):
        return "Driver" if obj.is_driver else "Passenger"
    ride_type_display.short_description = 'Type'
    
    def route_display(self, obj):
        return f"{obj.pickup_location} → {obj.dropoff_location}"
    route_display.short_description = 'Route'


class RideReviewAdmin(ImportExportModelAdmin):
    list_display = ('id', 'ride_link', 'reviewer_link', 'reviewee_link', 'rating_display', 'review_type', 'created_at')
    list_filter = ('rating', 'review_type', 'created_at')
    search_fields = ('ride__id', 'reviewer__username', 'reviewee__username', 'comment')
    raw_id_fields = ('ride', 'reviewer', 'reviewee')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def ride_link(self, obj):
        url = reverse("admin:rides_ride_change", args=[obj.ride.id])
        return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
    ride_link.short_description = 'Ride'
    
    def reviewer_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.reviewer.id])
        return format_html('<a href="{}">{}</a>', url, obj.reviewer.username)
    reviewer_link.short_description = 'Reviewer'
    
    def reviewee_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.reviewee.id])
        return format_html('<a href="{}">{}</a>', url, obj.reviewee.username)
    reviewee_link.short_description = 'Reviewee'
    
    def rating_display(self, obj):
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html('<span title="{}/5">{}</span>', obj.rating, stars)
    rating_display.short_description = 'Rating'


class RideDirectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'start_area', 'end_area', 'average_distance_km', 'average_duration_minutes', 'usage_count')
    list_filter = ('start_area', 'end_area')
    search_fields = ('name', 'start_area', 'end_area', 'waypoints')
    list_editable = ('average_distance_km', 'average_duration_minutes')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-usage_count', 'name')


class FareCalculationAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride_link', 'total_fare', 'fare_per_passenger', 'distance_km', 'is_peak_hour', 'calculated_at')
    list_filter = ('is_peak_hour', 'calculated_at')
    search_fields = ('ride__id', 'ride__pickup_location', 'ride__dropoff_location')
    raw_id_fields = ('ride',)
    readonly_fields = ('calculated_at',)
    date_hierarchy = 'calculated_at'
    
    def ride_link(self, obj):
        if obj.ride:
            url = reverse("admin:rides_ride_change", args=[obj.ride.id])
            return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
        return "No Ride"
    ride_link.short_description = 'Ride'


class RideRequestAdmin(ImportExportModelAdmin):
    list_display = ('id', 'passenger_link', 'ride_link', 'status_display', 'estimated_fare', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('passenger__username', 'ride__pickup_location', 'ride__dropoff_location', 
                    'pickup_location', 'dropoff_location', 'message')
    raw_id_fields = ('passenger', 'ride')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    actions = ['mark_as_accepted', 'mark_as_rejected', 'mark_as_cancelled']
    
    def mark_as_accepted(self, request, queryset):
        queryset.update(status='accepted')
        self.message_user(request, f'{queryset.count()} ride requests marked as accepted.')
    mark_as_accepted.short_description = 'Mark selected requests as accepted'
    
    def mark_as_rejected(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} ride requests marked as rejected.')
    mark_as_rejected.short_description = 'Mark selected requests as rejected'
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f'{queryset.count()} ride requests marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark selected requests as cancelled'
    
    def passenger_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.passenger.id])
        return format_html('<a href="{}">{}</a>', url, obj.passenger.username)
    passenger_link.short_description = 'Passenger'
    
    def ride_link(self, obj):
        if obj.ride:
            url = reverse("admin:rides_ride_change", args=[obj.ride.id])
            return format_html('<a href="{}">{}</a>', url, f"Ride #{obj.ride.id}")
        return "No Ride"
    ride_link.short_description = 'Ride'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'accepted': 'green',
            'rejected': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'


# Register models with admin
admin.site.register(Ride, RideAdmin)
admin.site.register(RidePassenger, RidePassengerAdmin)
admin.site.register(RideRequest, RideRequestAdmin)
admin.site.register(RideReview, RideReviewAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(RoutePoint, RoutePointAdmin)
admin.site.register(RideStop, RideStopAdmin)
admin.site.register(ScheduledRide, ScheduledRideAdmin)
admin.site.register(RideDirection, RideDirectionAdmin)
admin.site.register(FareCalculation, FareCalculationAdmin)
