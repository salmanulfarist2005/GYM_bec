from time import timezone
from django.db import models
from django.utils import timezone
from django.db import models
import uuid
from datetime import datetime
from django.conf import settings
from datetime import timedelta

class Gym(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.TextField()
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_gyms')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Gyms'



class Plan(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=200)
    duration_days = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    perks = models.TextField(help_text="Comma-separated list of perks or benefits")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.gym.name}"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('gym', 'name')



class MembershipPeriod(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('frozen', 'Frozen'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership_periods',
        limit_choices_to={'user_type': 'member'}
    )
    source_payment = models.ForeignKey(
        'Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='membership_periods'
    )
    
    start_date = models.DateField()
    end_date = models.DateField()
    
    expiry_alert_sent = models.BooleanField(
        default=False,
        help_text="Whether expiry alert email has been sent"
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    frozen_date = models.DateTimeField(null=True, blank=True)
    freeze_reason = models.TextField(blank=True)
    freeze_days_accumulated = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_memberships',
        limit_choices_to={'user_type': 'admin'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.member.get_full_name()} - {self.start_date} to {self.end_date}"
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Membership Period'
        verbose_name_plural = 'Membership Periods'
        indexes = [
            models.Index(fields=['member', '-start_date']),
            models.Index(fields=['status', '-end_date']),
        ]
    
    @property
    def days_remaining(self):
        """Calculate remaining days in membership"""
        if not self.end_date:
            return None
        
        if self.status == 'frozen':
            if self.frozen_date:
                return (self.end_date - self.frozen_date.date()).days
            return None
        
        if self.status == 'expired':
            return 0
        
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        
        remaining = (self.end_date - today).days
        return max(0, remaining)
    
    @property
    def is_expiring_soon(self):
        """Check if membership expires within 7 days"""
        if self.status in ['expired', 'frozen', 'inactive']:
            return False
        
        if not self.end_date:
            return False
        
        days_left = self.days_remaining
        return days_left is not None and 0 < days_left <= 7
    
    @property
    def is_active_membership(self):
        """Check if membership is currently active"""
        if not self.start_date or not self.end_date:
            return False
        
        now = timezone.now().date()
        return (
            self.status == 'active' and
            self.start_date <= now <= self.end_date
        )
    
    def freeze(self, freeze_reason=""):
        """Freeze the membership"""
        if self.status == 'frozen':
            raise ValueError("Membership is already frozen")
        
        self.status = 'frozen'
        self.frozen_date = timezone.now()
        self.freeze_reason = freeze_reason
        self.save()
    
    def unfreeze(self):
        """Unfreeze the membership and extend end_date by freeze duration"""
        if self.status != 'frozen':
            raise ValueError("Membership is not frozen")
        
        if self.frozen_date:
            freeze_duration = (timezone.now() - self.frozen_date).days
            self.freeze_days_accumulated += freeze_duration
            
            if self.end_date:
                self.end_date = self.end_date + timedelta(days=freeze_duration)
        
        self.status = 'active'
        self.frozen_date = None
        self.expiry_alert_sent = False
        self.save()
    
    def extend(self, additional_days):
        """Extend membership by additional days"""
        if additional_days <= 0:
            raise ValueError("Extension days must be positive")
        
        if self.status in ['expired', 'inactive']:
            raise ValueError("Cannot extend expired or inactive membership")
        
        if self.end_date:
            self.end_date = self.end_date + timedelta(days=additional_days)
        
        self.status = 'active'
        self.expiry_alert_sent = False
        self.save()
        return self.end_date
    
    def mark_expiry_alert_sent(self):
        """Mark that expiry alert has been sent"""
        self.expiry_alert_sent = True
        self.save(update_fields=['expiry_alert_sent'])
    
    def mark_expired(self):
        """Mark membership as expired"""
        self.status = 'expired'
        self.save(update_fields=['status'])
        
        from gyms.tasks import send_membership_expired_email
        send_membership_expired_email.delay(
            self.member.email,
            self.member.get_full_name(),
            self.member.gym.name
        )
    
    def save(self, *args, **kwargs):
        """Auto-update status on save"""
        if self.status != 'frozen' and self.end_date:
            today = timezone.now().date()
            if self.end_date < today:
                self.status = 'expired'
        
        super().save(*args, **kwargs)
        
        


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('wallet', 'Digital Wallet'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    # Basic Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        limit_choices_to={'user_type':'member'}
    )
    applied_membership = models.ForeignKey(
        'MembershipPeriod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    receipt_no = models.CharField(max_length=100, unique=True, blank=True)
    
    # Status and Dates
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')
    payment_date = models.DateTimeField()
    
    # Additional Fields
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    notes = models.TextField(blank=True)
    
   
    # Audit Fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payments',
        limit_choices_to={'user_type': 'admin'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Payment {self.receipt_no} - {self.member.username} - {self.amount}"
    
    # class Meta:
    #     ordering = ['-payment_date']
    #     indexes = [
    #         models.Index(fields=['member', '-payment_date']),
    #         models.Index(fields=['applied_plan', '-payment_date']),
    #         models.Index(fields=['receipt_no']),
    #     ]
    
    def save(self, *args, **kwargs):
        if not self.receipt_no:
            # Example: REC-550e8400-20240115
            date_str = datetime.now().strftime('%Y%m%d')
            uuid_str = str(self.id)[:8].upper()
            self.receipt_no = f"REC-{uuid_str}-{date_str}"
        
        super().save(*args, **kwargs)
