from rest_framework import serializers
from .models_vehicle import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle model"""
    
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    passenger_capacity = serializers.ReadOnlyField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'make', 'model', 'year', 'color', 'license_plate',
            'vehicle_type', 'fuel_type', 'engine_capacity', 'fuel_average',
            'total_seats', 'available_seats_for_ride',
            'has_ac', 'ac_type', 'has_music_system', 'has_phone_charger',
            'smoking_allowed', 'is_verified', 'insurance_valid',
            'fitness_certificate_valid', 'is_active', 'is_primary',
            'notes', 'full_name', 'display_name', 'passenger_capacity',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']
    
    def validate_license_plate(self, value):
        """Validate license plate format and uniqueness"""
        value = value.upper().strip()
        
        # Check if another vehicle with this license plate exists
        # (excluding current instance during updates)
        queryset = Vehicle.objects.filter(license_plate=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise serializers.ValidationError("A vehicle with this license plate already exists.")
        
        return value
    
    def validate_year(self, value):
        """Validate vehicle year"""
        from datetime import datetime
        current_year = datetime.now().year
        
        if value < 1990:
            raise serializers.ValidationError("Vehicle year cannot be before 1990.")
        if value > current_year + 1:
            raise serializers.ValidationError(f"Vehicle year cannot be more than {current_year + 1}.")
        
        return value
    
    def validate_available_seats_for_ride(self, value):
        """Validate available seats"""
        total_seats = self.initial_data.get('total_seats', 4)
        if isinstance(total_seats, str):
            total_seats = int(total_seats)
        
        if value >= total_seats:
            raise serializers.ValidationError("Available seats for ride must be less than total seats (driver seat excluded).")
        
        return value


class VehicleCreateSerializer(VehicleSerializer):
    """Serializer for creating vehicles"""
    
    class Meta(VehicleSerializer.Meta):
        fields = VehicleSerializer.Meta.fields
        
    def create(self, validated_data):
        """Create vehicle with owner set to current user"""
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class VehicleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing vehicles"""
    
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'make', 'model', 'year', 'color', 'license_plate',
            'vehicle_type', 'total_seats', 'available_seats_for_ride',
            'has_ac', 'is_active', 'is_primary', 'full_name', 'display_name'
        ]
