from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_otp_email(user, otp_code):
        """Send OTP verification email to user"""
        try:
            subject = 'Carwaan - Email Verification Code'
            
            # HTML email template
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .logo {{ color: #2196F3; font-size: 24px; font-weight: bold; }}
                    .otp-code {{ background-color: #2196F3; color: white; font-size: 32px; font-weight: bold; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0; letter-spacing: 8px; }}
                    .info {{ background-color: #f0f7ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">🚗 Carwaan</div>
                        <h2>Email Verification</h2>
                    </div>
                    
                    <p>Hello {user.first_name or user.username},</p>
                    
                    <p>Thank you for joining Carwaan! Please verify your email address using the code below:</p>
                    
                    <div class="otp-code">{otp_code}</div>
                    
                    <div class="info">
                        <strong>Important:</strong>
                        <ul>
                            <li>This code is valid for 10 minutes only</li>
                            <li>You have 3 attempts to enter the correct code</li>
                            <li>Don't share this code with anyone</li>
                        </ul>
                    </div>
                    
                    <p>If you didn't request this verification, please ignore this email.</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>The Carwaan Team</p>
                        <p>🚗 Safe rides, trusted community</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text version for email clients that don't support HTML
            plain_message = f"""
            Carwaan - Email Verification
            
            Hello {user.first_name or user.username},
            
            Thank you for joining Carwaan! Please verify your email address using this code:
            
            Verification Code: {otp_code}
            
            Important:
            - This code is valid for 10 minutes only
            - You have 3 attempts to enter the correct code
            - Don't share this code with anyone
            
            If you didn't request this verification, please ignore this email.
            
            Best regards,
            The Carwaan Team
            """
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"OTP email sent successfully to {user.email}")
            return True, "OTP sent successfully"
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
            return False, f"Failed to send email: {str(e)}"
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful verification"""
        try:
            subject = 'Welcome to Carwaan - Your Account is Ready!'
            
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .logo {{ color: #2196F3; font-size: 24px; font-weight: bold; }}
                    .welcome {{ background: linear-gradient(135deg, #2196F3, #21CBF3); color: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0; }}
                    .features {{ margin: 20px 0; }}
                    .feature {{ margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-left: 4px solid #2196F3; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">🚗 Carwaan</div>
                    </div>
                    
                    <div class="welcome">
                        <h2>Welcome to Carwaan!</h2>
                        <p>Your email has been verified successfully</p>
                    </div>
                    
                    <p>Hello {user.first_name or user.username},</p>
                    
                    <p>Congratulations! Your Carwaan account is now active and ready to use.</p>
                    
                    <div class="features">
                        <h3>What you can do now:</h3>
                        <div class="feature">🚗 <strong>Find Rides:</strong> Search for rides in Karachi with real-time fare calculation</div>
                        <div class="feature">👥 <strong>Offer Rides:</strong> Share your car and earn money by offering rides</div>
                        <div class="feature">💰 <strong>Smart Pricing:</strong> Automatic fare calculation at Rs. 30/km (2x during peak hours)</div>
                        <div class="feature">🛡️ <strong>Safety First:</strong> Gender preferences and verified user ratings</div>
                        <div class="feature">📅 <strong>Schedule Rides:</strong> Book rides in advance for your convenience</div>
                    </div>
                    
                    <p>Start exploring and enjoy safe, affordable rides across Karachi!</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>The Carwaan Team</p>
                        <p>🚗 Safe rides, trusted community</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            plain_message = f"""
            Welcome to Carwaan!
            
            Hello {user.first_name or user.username},
            
            Congratulations! Your Carwaan account is now active and ready to use.
            
            What you can do now:
            - Find Rides: Search for rides in Karachi with real-time fare calculation
            - Offer Rides: Share your car and earn money by offering rides
            - Smart Pricing: Automatic fare calculation at Rs. 30/km (2x during peak hours)
            - Safety First: Gender preferences and verified user ratings
            - Schedule Rides: Book rides in advance for your convenience
            
            Start exploring and enjoy safe, affordable rides across Karachi!
            
            Best regards,
            The Carwaan Team
            """
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Welcome email sent successfully to {user.email}")
            return True, "Welcome email sent"
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
            return False, f"Failed to send welcome email: {str(e)}"
