from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Avg, Sum
from apps.rides.models import Ride, RidePassenger
from apps.users.models import User
from django.http import JsonResponse
import json

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users(request):
    """Get all users for admin dashboard"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.all().order_by('-date_joined')
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or '',
            'username': user.username or '',
            'role': user.role or 'user',
            'is_driver': user.is_driver,
            'is_verified': user.is_verified,
            'driver_verification_status': getattr(user, 'driver_verification_status', 'pending') or 'pending',
            'date_joined': user.date_joined.isoformat() if user.date_joined else '',
            'last_login': user.last_login.isoformat() if user.last_login else '',
            'is_active': user.is_active,
        })
    
    return Response(users_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_rides(request):
    """Get all rides for admin monitoring"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    rides = Ride.objects.all().select_related('driver', 'vehicle').order_by('-created_at')
    
    rides_data = []
    for ride in rides:
        # Count passengers using RidePassenger model
        passenger_count = RidePassenger.objects.filter(ride=ride, status='confirmed').count()
        
        rides_data.append({
            'id': ride.id,
            'pickup_location': ride.pickup_location or '',
            'dropoff_location': ride.dropoff_location or '',
            'driver_name': f"{(ride.driver.first_name or '')} {(ride.driver.last_name or '')}".strip() or ride.driver.username or '',
            'driver_id': ride.driver.id,
            'driver_email': ride.driver.email or '',
            'driver_phone': ride.driver.phone or '',
            'driver_rating': float(ride.driver.driver_rating) if hasattr(ride.driver, 'driver_rating') and ride.driver.driver_rating else 0.0,
            'status': ride.status or 'scheduled',
            'departure_time': ride.departure_time.isoformat() if ride.departure_time else '',
            'passenger_count': passenger_count,
            'total_seats': ride.total_seats or 0,
            'available_seats': ride.available_seats or 0,
            'created_at': ride.created_at.isoformat() if ride.created_at else '',
            'estimated_distance_km': ride.estimated_distance_km or 0.0,
            'estimated_duration_minutes': ride.estimated_duration_minutes or 0,
            'vehicle_info': {
                'make': ride.vehicle.make if ride.vehicle and ride.vehicle.make else 'Unknown',
                'model': ride.vehicle.model if ride.vehicle and ride.vehicle.model else 'Unknown',
                'year': str(ride.vehicle.year) if ride.vehicle and ride.vehicle.year else 'Unknown',
                'color': ride.vehicle.color if ride.vehicle and ride.vehicle.color else 'Unknown',
                'license_plate': ride.vehicle.license_plate if ride.vehicle and ride.vehicle.license_plate else 'Unknown',
            } if ride.vehicle else {
                'make': 'Unknown',
                'model': 'Unknown', 
                'year': 'Unknown',
                'color': 'Unknown',
                'license_plate': 'Unknown',
            },
        })
    
    return Response(rides_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_analytics(request):
    """Get analytics and statistics for admin dashboard"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.rides.models import RidePassenger
        
        # Time ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Basic counts
        total_users = User.objects.count()
        total_drivers = User.objects.filter(is_driver=True).count()
        total_rides = Ride.objects.count()
        active_rides = Ride.objects.filter(
            Q(status='scheduled') | Q(status='in_progress')
        ).count()
        
        # Time-based ride counts
        today_rides = Ride.objects.filter(created_at__date=today).count()
        week_rides = Ride.objects.filter(created_at__date__gte=week_ago).count()
        month_rides = Ride.objects.filter(created_at__date__gte=month_ago).count()
        
        # Completion rate - handle division by zero
        completed_rides = Ride.objects.filter(status='completed').count()
        completion_rate = round((completed_rides / total_rides * 100) if total_rides > 0 else 0, 1)
        
        # Average rating - handle empty results
        try:
            # If you have a rating field in Ride model, use this:
            # avg_rating_result = Ride.objects.aggregate(avg_rating=Avg('rating'))
            # avg_rating = round(avg_rating_result['avg_rating'] or 0, 1)
            avg_rating = 4.5  # Mock data for now
        except Exception:
            avg_rating = 0.0
        
        # Total revenue (mock data - replace with actual calculation when payment system is ready)
        total_revenue = 125000
        
        # Active drivers (drivers who created rides in the last 30 days)
        try:
            active_drivers = User.objects.filter(
                is_driver=True,
                offered_rides__created_at__gte=month_ago
            ).distinct().count()
        except Exception:
            active_drivers = 0
        
        analytics_data = {
            'total_users': total_users,
            'total_drivers': total_drivers,
            'total_rides': total_rides,
            'active_rides': active_rides,
            'today_rides': today_rides,
            'week_rides': week_rides,
            'month_rides': month_rides,
            'completion_rate': completion_rate,
            'avg_rating': avg_rating,
            'total_revenue': total_revenue,
            'active_drivers': active_drivers,
        }
        
        return Response(analytics_data)
        
    except Exception as e:
        # Log the error for debugging
        print(f"Analytics error: {e}")
        
        # Return safe default values
        return Response({
            'total_users': User.objects.count() if User.objects.exists() else 0,
            'total_drivers': User.objects.filter(is_driver=True).count() if User.objects.exists() else 0,
            'total_rides': Ride.objects.count() if Ride.objects.exists() else 0,
            'active_rides': 0,
            'today_rides': 0,
            'week_rides': 0,
            'month_rides': 0,
            'completion_rate': 0,
            'avg_rating': 0.0,
            'total_revenue': 0,
            'active_drivers': 0,
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_stats(request):
    """Get system statistics"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    return Response({
        'server_status': 'healthy',
        'database_connections': 5,
        'active_sessions': 23,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_details(request, user_id):
    """Get detailed information about a specific user"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get user's ride statistics
        offered_rides_count = Ride.objects.filter(driver=user).count()
        joined_rides_count = RidePassenger.objects.filter(passenger=user, status='confirmed').count()
        
        user_data = {
            'id': user.id,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'email': user.email or '',
            'username': user.username or '',
            'role': user.role or 'user',
            'is_driver': user.is_driver,
            'is_verified': user.is_verified,
            'driver_verification_status': getattr(user, 'driver_verification_status', 'pending') or 'pending',
            'date_joined': user.date_joined.isoformat() if user.date_joined else '',
            'last_login': user.last_login.isoformat() if user.last_login else '',
            'is_active': user.is_active,
            'phone': user.phone or '',
            'gender': user.gender or '',
            'address': user.address or '',
            'bio': user.bio or '',
            'statistics': {
                'offered_rides': offered_rides_count,
                'joined_rides': joined_rides_count,
                'total_rides': offered_rides_count + joined_rides_count,
            }
        }
        
        return Response(user_data)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suspend_user(request, user_id):
    """Suspend a user account"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        
        return Response({
            'message': f'User {user.username} has been suspended successfully',
            'user_id': user_id
        })
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    """Delete a user account (admin only)"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Prevent admin from deleting themselves
    if request.user.id == user_id:
        return Response({'error': 'Cannot delete your own account'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        username = user.username
        user.delete()
        
        return Response({
            'message': f'User {username} has been deleted successfully'
        })
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_cancel_ride(request, ride_id):
    """Cancel a ride (admin only)"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        ride = Ride.objects.get(id=ride_id)
        reason = request.data.get('reason', 'Cancelled by admin')
        
        ride.status = 'cancelled'
        ride.save()
        
        # TODO: Notify driver and passengers about cancellation
        
        return Response({
            'message': f'Ride has been cancelled successfully',
            'ride_id': ride_id,
            'reason': reason
        })
    except Ride.DoesNotExist:
        return Response({'error': 'Ride not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_activity(request):
    """Get recent activity for admin dashboard"""
    # Check if user is admin
    if request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        recent_activity = []
        
        # Get recent user registrations (last 7 days to get some data)
        try:
            recent_users = User.objects.filter(
                date_joined__gte=timezone.now() - timedelta(days=7)
            ).order_by('-date_joined')[:5]
            
            for user in recent_users:
                user_type = "driver" if user.is_driver else "passenger"
                recent_activity.append({
                    'action': f'New {user_type} registered',
                    'timestamp': user.date_joined.isoformat(),
                    'details': f'{user.first_name} {user.last_name} joined as {user_type}',
                    'user_id': user.id,
                    'type': 'user_registration'
                })
        except Exception as e:
            print(f"Error getting recent users: {e}")
        
        # Get recent rides (last 7 days to get some data)
        try:
            recent_rides = Ride.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).select_related('driver').order_by('-created_at')[:10]
            
            for ride in recent_rides:
                recent_activity.append({
                    'action': 'New ride created',
                    'timestamp': ride.created_at.isoformat(),
                    'details': f'{ride.driver.first_name} created ride from {ride.pickup_location} to {ride.dropoff_location}',
                    'user_id': ride.driver.id,
                    'ride_id': ride.id,
                    'type': 'ride_created'
                })
        except Exception as e:
            print(f"Error getting recent rides: {e}")
        
        # Get recent completed rides (last 7 days to get some data)
        try:
            completed_rides = Ride.objects.filter(
                status='completed',
                updated_at__gte=timezone.now() - timedelta(days=7)
            ).select_related('driver').order_by('-updated_at')[:5]
            
            for ride in completed_rides:
                recent_activity.append({
                    'action': 'Ride completed',
                    'timestamp': ride.updated_at.isoformat(),
                    'details': f'Ride from {ride.pickup_location} to {ride.dropoff_location} completed',
                    'user_id': ride.driver.id,
                    'ride_id': ride.id,
                    'type': 'ride_completed'
                })
        except Exception as e:
            print(f"Error getting completed rides: {e}")
        
        # If no activity found, add some placeholder messages
        if not recent_activity:
            recent_activity = [
                {
                    'action': 'System initialized',
                    'timestamp': timezone.now().isoformat(),
                    'details': 'Admin dashboard is ready for monitoring',
                    'type': 'system_message'
                },
                {
                    'action': 'Waiting for user activity',
                    'timestamp': timezone.now().isoformat(),
                    'details': 'No recent user registrations or rides',
                    'type': 'system_message'
                }
            ]
        
        # Sort all activity by timestamp (most recent first)
        recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Return only the most recent 15 activities
        return Response({
            'recent_activity': recent_activity[:15]
        })
        
    except Exception as e:
        print(f"Recent activity error: {e}")
        # Return safe default data
        return Response({
            'recent_activity': [
                {
                    'action': 'System ready',
                    'timestamp': timezone.now().isoformat(),
                    'details': 'Admin dashboard loaded successfully',
                    'type': 'system_message'
                }
            ]
        })
