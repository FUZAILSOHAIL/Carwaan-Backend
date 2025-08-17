from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import TimeStampedModel
from django.conf import settings


class Vehicle(TimeStampedModel):
    """Model for user vehicles/cars"""
    
    VEHICLE_TYPE_CHOICES = (
        ('sedan', 'Sedan'),
        ('hatchback', 'Hatchback'),
        ('suv', 'SUV'),
        ('crossover', 'Crossover'),
        ('coupe', 'Coupe'),
        ('convertible', 'Convertible'),
        ('pickup', 'Pickup Truck'),
        ('van', 'Van'),
        ('other', 'Other'),
    )
    
    FUEL_TYPE_CHOICES = (
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('cng', 'CNG'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
    )
    
    AC_TYPE_CHOICES = (
        ('none', 'No AC'),
        ('standard', 'Standard AC'),
        ('climate_control', 'Climate Control'),
    )
    
    license_plate_regex = RegexValidator(
        regex=r'^[A-Z]{2,3}-\d{3,4}$',
        message="License plate must be in format: ABC-123 or AB-1234"
    )
    
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='vehicles'
    )
    
    # Basic vehicle information
    make = models.CharField(max_length=50, help_text="e.g., Toyota, Honda, Suzuki")
    model = models.CharField(max_length=50, help_text="e.g., Corolla, Civic, Cultus")
    year = models.PositiveIntegerField(help_text="Manufacturing year")
    color = models.CharField(max_length=30, help_text="Vehicle color")
    license_plate = models.CharField(
        max_length=20, 
        validators=[license_plate_regex],
        unique=True,
        help_text="Vehicle registration number (e.g., ABC-123)"
    )
    
    # Vehicle specifications
    vehicle_type = models.CharField(
        max_length=20, 
        choices=VEHICLE_TYPE_CHOICES, 
        default='sedan'
    )
    fuel_type = models.CharField(
        max_length=20, 
        choices=FUEL_TYPE_CHOICES, 
        default='petrol'
    )
    engine_capacity = models.CharField(
        max_length=20, 
        null=True,
        blank=True,
        help_text="e.g., 1300cc, 1600cc"
    )
    fuel_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fuel average in km/liter"
    )
    
    # Passenger capacity
    total_seats = models.PositiveIntegerField(
        default=4,
        help_text="Total number of seats including driver"
    )
    available_seats_for_ride = models.PositiveIntegerField(
        default=3,
        help_text="Maximum passengers (excluding driver)"
    )
    
    # Comfort features
    has_ac = models.BooleanField(default=True)
    ac_type = models.CharField(
        max_length=20, 
        choices=AC_TYPE_CHOICES, 
        default='standard'
    )
    has_music_system = models.BooleanField(default=True)
    has_phone_charger = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    
    # Vehicle condition and safety
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether vehicle documents are verified"
    )
    insurance_valid = models.BooleanField(default=True)
    fitness_certificate_valid = models.BooleanField(default=True)
    
    # Vehicle Registration Documents
    registration_book_image = models.ImageField(
        upload_to='vehicle_documents/registration/', 
        null=True, 
        blank=True,
        help_text="Car registration book/papers image"
    )
    car_registration_book_image = models.ImageField(
        upload_to='vehicle_documents/registration_book/', 
        null=True, 
        blank=True,
        help_text="Car registration book image (required for verification)"
    )
    car_image = models.ImageField(
        upload_to='vehicle_images/', 
        null=True, 
        blank=True,
        help_text="Car image (optional)"
    )
    
    # Verification status
    verification_status = models.CharField(
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ),
        default='pending',
        help_text="Vehicle verification status"
    )
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verification_approved_at = models.DateTimeField(null=True, blank=True)
    
    # Usage preferences
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this vehicle is available for offering rides"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary vehicle for the user"
    )
    
    # Additional details
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Additional information about the vehicle"
    )
    
    class Meta:
        ordering = ['-is_primary', '-is_active', 'make', 'model']
        
    def __str__(self):
        return f"{self.make} {self.model} ({self.year}) - {self.license_plate}"
    
    def save(self, *args, **kwargs):
        # If this is set as primary, unset other primary vehicles for this user
        if self.is_primary:
            Vehicle.objects.filter(
                owner=self.owner, 
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        return f"{self.make} {self.model} ({self.year})"
    
    @property
    def display_name(self):
        return f"{self.make} {self.model} - {self.license_plate}"
    
    @property
    def passenger_capacity(self):
        return self.total_seats - 1  # Excluding driver
