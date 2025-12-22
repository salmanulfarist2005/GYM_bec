# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('superuser', 'Super User'),
        ('admin', 'Gym Admin'),
        ('member', 'Member'),
)       
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='member')
    phone = models.CharField(max_length=15, blank=True, null=True)
    gym = models.ForeignKey('gyms.Gym', on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    is_email_verified = models.BooleanField(default=False)
    password_set = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):

        return f"{self.username} - {self.user_type}"
    
    class Meta:
        ordering = ['-created_at']
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class MemberProfile(models.Model):
    MEMBERSHIP_STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
    )
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile')
    gym = models.ForeignKey('gyms.Gym', on_delete=models.CASCADE, related_name='member_profiles')
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, blank=True,null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True,null=True)
    
    # Membership Details
    membership_status = models.CharField(
        max_length=20, 
        choices=MEMBERSHIP_STATUS_CHOICES, 
        default='active'
    )
    membership_start_date = models.DateField(auto_now_add=True)
    membership_end_date = models.DateField(null=True, blank=True)
    
    # Health Information
    height = models.FloatField(null=True, blank=True, help_text="Height in cm")
    weight = models.FloatField(null=True, blank=True, help_text="Weight in kg")
    
    # Preferences & Notes
    preferred_schedule = models.CharField(max_length=200, blank=True,null=True)
    fitness_goals = models.TextField(blank=True,null=True)
    notes = models.TextField(blank=True,null=True)
    
    # System Fields
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.gym.name}"
    
    class Meta:
        ordering = ['-created_at']


class OTP(models.Model):
    OTP_TYPE_CHOICES = (
        ('login', 'Login OTP'),
        ('password_reset', 'Password Reset OTP'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES, default='login')
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"{self.otp_type} OTP for {self.email} - {self.otp_code}"
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return str(random.randint(100000, 999999))
    
    def is_valid(self):
        """Check if OTP is still valid"""
        return timezone.now() < self.expires_at and not self.is_verified
    
    def save(self, *args, **kwargs):
        if not self.pk: 
            self.otp_code = self.generate_otp()
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']