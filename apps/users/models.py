from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
import secrets
from apps.core.models import TimeStampedModel

# Import Vehicle model
from .models_vehicle import Vehicle


class User(AbstractUser, TimeStampedModel):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("user", "User"),
    )
    
    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer not to say"),
    )
    
    DRIVER_VERIFICATION_STATUS = (
        ("pending", "Pending"),
        ("under_review", "Under Review"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    cnic_regex = RegexValidator(
        regex=r'^\d{5}-\d{7}-\d{1}$',
        message="CNIC must be in format: 12345-1234567-1"
    )
    
    # Override email to make it required and unique
    email = models.EmailField(unique=True, help_text="Email address (required for account verification)")
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="prefer_not_to_say")
    phone = models.CharField(validators=[phone_regex], max_length=15, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    
    # CNIC and Identity Verification
    cnic = models.CharField(
        validators=[cnic_regex], 
        max_length=15, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="CNIC number (required for identity verification)"
    )
    full_name = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Full name as per CNIC"
    )
    
    # Driver Verification Fields
    is_driver = models.BooleanField(default=False, help_text="Whether user can offer rides")
    driver_verification_status = models.CharField(
        max_length=20, 
        choices=DRIVER_VERIFICATION_STATUS, 
        default="pending",
        help_text="Driver verification status"
    )
    cnic_number = models.CharField(
        validators=[cnic_regex],
        max_length=15,
        blank=True,
        help_text="CNIC number in format: 12345-1234567-1"
    )
    driver_license_number = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Driver's license number"
    )
    
    # Verification Documents
    cnic_front_image = models.ImageField(
        upload_to='verification/cnic_front/', 
        null=True, 
        blank=True,
        help_text="CNIC front side image"
    )
    cnic_back_image = models.ImageField(
        upload_to='verification/cnic_back/', 
        null=True, 
        blank=True,
        help_text="CNIC back side image"
    )
    driver_license_front_image = models.ImageField(
        upload_to='verification/driver_license_front/', 
        null=True, 
        blank=True,
        help_text="Driver's license front side image"
    )
    driver_license_back_image = models.ImageField(
        upload_to='verification/driver_license_back/', 
        null=True, 
        blank=True,
        help_text="Driver's license back side image"
    )
    
    # Verification dates
    verification_submitted_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When verification documents were submitted"
    )
    verification_approved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When driver verification was approved"
    )
    verification_rejected_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When driver verification was rejected"
    )
    verification_rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for verification rejection"
    )
    
    # Email verification and OTP
    email_verified = models.BooleanField(default=False, help_text="Whether email is verified")
    otp_code = models.CharField(max_length=6, blank=True, null=True, help_text="Current OTP code")
    otp_created_at = models.DateTimeField(null=True, blank=True, help_text="When OTP was generated")
    otp_attempts = models.PositiveIntegerField(default=0, help_text="Number of OTP verification attempts")
    
    # New fields for carpooling
    workplace = models.CharField(max_length=255, blank=True, help_text="Company or institution where you work/study")
    department = models.CharField(max_length=100, blank=True, help_text="Department or team within the workplace")
    has_car = models.BooleanField(default=False, help_text="Whether the user has a car to offer rides")
    car_model = models.CharField(max_length=100, blank=True, help_text="Model of the user's car")
    car_color = models.CharField(max_length=50, blank=True, help_text="Color of the user's car")
    license_plate = models.CharField(max_length=20, blank=True, help_text="License plate of the user's car")
    
    # Social connections for carpooling
    connections = models.ManyToManyField('self', blank=True, symmetrical=False,
                                       related_name='connected_by',
                                       help_text="Colleagues, friends, etc.")
    friend_groups = models.JSONField(null=True, blank=True, 
                                   help_text="Groups of friends for organizing carpools")
    trusted_drivers = models.ManyToManyField('self', blank=True, symmetrical=False,
                                           related_name='trusted_by',
                                           help_text="Drivers you trust and prefer to ride with")
    
    # Enhanced fields for ride matching
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, 
                                        help_text="User's average rating as driver/passenger")
    total_ratings = models.PositiveIntegerField(default=0, help_text="Number of ratings received")
    
    # User preferences for ride matching
    preferred_days = models.JSONField(null=True, blank=True, 
                               help_text="Preferred days for commuting [0-6], where 0 is Monday")
    preferred_departure_times = models.JSONField(null=True, blank=True, 
                                         help_text="Preferred departure times in 24h format")
    preferred_music = models.JSONField(null=True, blank=True, 
                                     help_text="Music preferences for rides")
    
    smoking_preference = models.CharField(max_length=20, choices=[
        ("no_smoking", "No Smoking"),
        ("smoking_allowed", "Smoking Allowed"),
        ("no_preference", "No Preference"),
    ], default="no_smoking")
    
    ac_preference = models.CharField(max_length=20, choices=[
        ("ac_required", "AC Required"),
        ("no_ac", "No AC"),
        ("no_preference", "No Preference"),
    ], default="no_preference")
    
    chat_preference = models.CharField(max_length=20, choices=[
        ("chatty", "Enjoy Conversation"),
        ("quiet", "Prefer Quiet"),
        ("no_preference", "No Preference"),
    ], default="no_preference")
    
    home_address = models.CharField(max_length=255, blank=True, 
                                   help_text="Home address for better ride matching")
    home_latitude = models.FloatField(null=True, blank=True)
    home_longitude = models.FloatField(null=True, blank=True)
    
    workplace_address = models.CharField(max_length=255, blank=True, 
                                        help_text="Complete workplace address")
    workplace_latitude = models.FloatField(null=True, blank=True)
    workplace_longitude = models.FloatField(null=True, blank=True)
    
    # Enhanced localization and preferences
    preferred_areas = models.JSONField(
        default=list,
        help_text="List of preferred pickup/dropoff areas in Karachi"
    )
    
    # Female safety preferences
    female_only_preference = models.BooleanField(
        default=False,
        help_text="Prefer female-only rides (for female users)"
    )
    
    # Local/Desi profile enhancements
    native_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Native/Local name (Urdu/Local language)"
    )
    
    # Enhanced profile for ride sharing
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    
    # Rating aggregates
    driver_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    passenger_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_driver_reviews = models.PositiveIntegerField(default=0)
    total_passenger_reviews = models.PositiveIntegerField(default=0)
    
    # Activity stats
    total_rides_offered = models.PositiveIntegerField(default=0)
    total_rides_taken = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self):
        return self.role == "admin" or self.is_staff or self.is_superuser
    
    def is_verified_driver(self):
        """Check if user is a verified driver"""
        return self.is_driver and self.driver_verification_status == "verified"

    def can_offer_rides(self):
        """Check if user can offer rides (verified driver with at least one active car)"""
        return (self.is_driver and 
                self.driver_verification_status == "verified" and 
                self.vehicles.filter(is_active=True).exists())

    def submit_driver_verification(self, cnic_front, cnic_back, driver_license):
        """Submit driver verification documents"""
        self.cnic_front_image = cnic_front
        self.cnic_back_image = cnic_back
        self.driver_license_image = driver_license
        self.driver_verification_status = "under_review"
        self.verification_submitted_at = timezone.now()
        self.save()
    
    def approve_driver_verification(self):
        """Approve driver verification"""
        self.driver_verification_status = "verified"
        self.verification_approved_at = timezone.now()
        self.is_driver = True
        self.save()
    
    def reject_driver_verification(self, reason=""):
        """Reject driver verification"""
        self.driver_verification_status = "rejected"
        self.verification_rejected_at = timezone.now()
        self.verification_rejection_reason = reason
        self.save()

    def update_rating(self, new_rating):
        """Update average rating with a new rating (1-5)"""
        if new_rating < 1 or new_rating > 5:
            raise ValueError("Rating must be between 1 and 5")
            
        if self.total_ratings == 0:
            self.average_rating = new_rating
        else:
            total = self.average_rating * self.total_ratings
            self.average_rating = (total + new_rating) / (self.total_ratings + 1)
            
        self.total_ratings += 1
        self.save()

    def generate_otp(self):
        """Generate a new 6-digit OTP code"""
        self.otp_code = str(secrets.randbelow(900000) + 100000)  # 6-digit number
        self.otp_created_at = timezone.now()
        self.otp_attempts = 0
        self.save()
        return self.otp_code
    
    @property
    def user_type(self):
        """Return the effective user type based on role and driver status"""
        if self.role == 'admin':
            return 'admin'
        elif self.is_driver:
            return 'driver'
        else:
            return 'passenger'
    
    def verify_otp(self, otp_code):
        """Verify OTP code and mark email as verified"""
        # Check if OTP exists
        if not self.otp_code:
            return False, "No OTP generated"
        
        # Check if OTP has expired (valid for 10 minutes)
        if self.otp_created_at and timezone.now() > self.otp_created_at + timedelta(minutes=10):
            return False, "OTP has expired"
        
        # Check attempt limit (max 3 attempts)
        if self.otp_attempts >= 3:
            return False, "Too many attempts. Please request a new OTP"
        
        # Increment attempts
        self.otp_attempts += 1
        self.save()
        
        # Verify OTP
        if self.otp_code == otp_code:
            self.email_verified = True
            self.otp_code = None
            self.otp_created_at = None
            self.otp_attempts = 0
            self.save()
            return True, "Email verified successfully"
        
        return False, "Invalid OTP code"
    
    def is_otp_valid(self):
        """Check if current OTP is still valid"""
        if not self.otp_code or not self.otp_created_at:
            return False
        return timezone.now() <= self.otp_created_at + timedelta(minutes=10)

    def get_display_name(self):
        """Get the best available display name"""
        if self.native_name:
            return self.native_name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username
    
    def update_driver_rating(self, new_rating):
        """Update driver rating with new review"""
        if self.total_driver_reviews == 0:
            self.driver_rating = new_rating
        else:
            total = self.driver_rating * self.total_driver_reviews
            self.driver_rating = (total + new_rating) / (self.total_driver_reviews + 1)
        
        self.total_driver_reviews += 1
        self.save()
    
    def update_passenger_rating(self, new_rating):
        """Update passenger rating with new review"""
        if self.total_passenger_reviews == 0:
            self.passenger_rating = new_rating
        else:
            total = self.passenger_rating * self.total_passenger_reviews
            self.passenger_rating = (total + new_rating) / (self.total_passenger_reviews + 1)
        
        self.total_passenger_reviews += 1
        self.save()
    
    def can_join_female_only_ride(self):
        """Check if user can join female-only rides"""
        return self.gender == 'female'
    
    def get_safety_score(self):
        """Calculate a safety score based on ratings and activity"""
        base_score = 3.0  # Default score
        
        if self.total_driver_reviews > 0:
            driver_score = float(self.driver_rating)
        else:
            driver_score = base_score
        
        if self.total_passenger_reviews > 0:
            passenger_score = float(self.passenger_rating)
        else:
            passenger_score = base_score
        
        # Weight more recent activity higher
        activity_bonus = min(0.5, (self.total_rides_offered + self.total_rides_taken) * 0.01)
        
        overall_score = (driver_score + passenger_score) / 2 + activity_bonus
        return min(5.0, overall_score)  # Cap at 5.0

    def get_average_rating(self):
        """Calculate average rating from all received reviews"""
        from apps.rides.models import Review
        
        reviews = Review.objects.filter(reviewee=self)
        if not reviews.exists():
            return 0.0
        
        total_rating = sum(review.overall_rating for review in reviews)
        average = total_rating / reviews.count()
        return round(average, 1)  # Round to one decimal place
    
    def get_review_count(self):
        """Get total number of reviews received"""
        from apps.rides.models import Review
        return Review.objects.filter(reviewee=self).count()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]


class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('card', 'Credit/Debit Card'),
        ('easypaisa', 'EasyPaisa'),
        ('jazzcash', 'JazzCash'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='user_payment_methods')
    type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    holder_name = models.CharField(max_length=100)
    
    # For cards
    last_four = models.CharField(max_length=4, blank=True, null=True)
    brand = models.CharField(max_length=20, blank=True, null=True)  # Visa, MasterCard, etc.
    expiry_month = models.IntegerField(blank=True, null=True)
    expiry_year = models.IntegerField(blank=True, null=True)
    
    # For mobile wallets (EasyPaisa, JazzCash)
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_validator], max_length=17, blank=True, null=True)
    
    # For bank transfers
    account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        
    def __str__(self):
        if self.type == 'card':
            return f"{self.holder_name} - **** {self.last_four} ({self.brand})"
        elif self.type in ['easypaisa', 'jazzcash']:
            return f"{self.holder_name} - {self.type.title()} ({self.phone_number})"
        else:
            return f"{self.holder_name} - {self.type.title()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
    
    def to_dict(self):
        """Return a dictionary representation for API responses"""
        data = {
            'id': self.id,
            'type': self.type,
            'holder_name': self.holder_name,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
        }
        
        if self.type == 'card':
            data.update({
                'last_four': self.last_four,
                'brand': self.brand,
                'expiry_month': self.expiry_month,
                'expiry_year': self.expiry_year,
            })
        elif self.type in ['easypaisa', 'jazzcash']:
            data['phone_number'] = self.phone_number
        elif self.type == 'bank_transfer':
            data.update({
                'account_number': self.account_number,
                'bank_name': self.bank_name,
            })
            
        return data


class ImageBackup(TimeStampedModel):
    """Model to track Google Drive image backups"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('uploading', 'Uploading'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='image_backups')
    filename = models.CharField(max_length=255, help_text="Original filename")
    google_drive_file_id = models.CharField(max_length=255, null=True, blank=True, help_text="Google Drive file ID")
    google_drive_filename = models.CharField(max_length=255, null=True, blank=True, help_text="Filename in Google Drive")
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    image_count = models.IntegerField(default=0, help_text="Number of images in the backup")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    upload_started_at = models.DateTimeField(null=True, blank=True)
    upload_completed_at = models.DateTimeField(null=True, blank=True)
    google_drive_link = models.URLField(null=True, blank=True, help_text="Link to view file in Google Drive")
    download_link = models.URLField(null=True, blank=True, help_text="Direct download link")
    error_message = models.TextField(null=True, blank=True, help_text="Error message if upload failed")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Image Backup"
        verbose_name_plural = "Image Backups"
    
    def __str__(self):
        return f"{self.user.email} - {self.filename} ({self.status})"
    
    def mark_as_uploading(self):
        """Mark backup as currently uploading"""
        self.status = 'uploading'
        self.upload_started_at = timezone.now()
        self.save()
    
    def mark_as_completed(self, google_drive_info):
        """Mark backup as completed with Google Drive info"""
        self.status = 'completed'
        self.upload_completed_at = timezone.now()
        self.google_drive_file_id = google_drive_info.get('id')
        self.google_drive_filename = google_drive_info.get('name')
        self.file_size = google_drive_info.get('size')
        self.google_drive_link = google_drive_info.get('web_view_link')
        self.download_link = google_drive_info.get('download_link')
        self.save()
    
    def mark_as_failed(self, error_message):
        """Mark backup as failed with error message"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
    
    def to_dict(self):
        """Return a dictionary representation for API responses"""
        return {
            'id': self.id,
            'filename': self.filename,
            'google_drive_filename': self.google_drive_filename,
            'file_size': self.file_size,
            'image_count': self.image_count,
            'status': self.status,
            'upload_started_at': self.upload_started_at.isoformat() if self.upload_started_at else None,
            'upload_completed_at': self.upload_completed_at.isoformat() if self.upload_completed_at else None,
            'google_drive_link': self.google_drive_link,
            'download_link': self.download_link,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
        }
