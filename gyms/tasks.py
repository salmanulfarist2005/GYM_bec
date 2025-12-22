from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import MembershipPeriod, Gym


@shared_task
def send_expiring_membership_alerts():
    """
    Find all memberships expiring within 7 days and send alerts
    Runs daily at 8 AM
    """
    now = timezone.now()
    seven_days_later = now + timedelta(days=7)
    
    memberships = MembershipPeriod.objects.filter(
        status='active',
        end_date__lte=seven_days_later,
        end_date__gte=now,
        expiry_alert_sent=False
    )
    
    for membership in memberships:
        days_remaining = membership.days_remaining
        
        # Send email to member
        send_membership_expiry_email.delay(
            membership.member.email,
            membership.member.get_full_name(),
            days_remaining,
            membership.member.id
        )
        
        # Send notification to admin
        send_admin_membership_expiry_alert.delay(
            membership.member.gym.id,
            membership.member.get_full_name(),
            days_remaining
        )
        
        membership.mark_expiry_alert_sent()
    
    return f"Sent expiry alerts for {memberships.count()} memberships"


@shared_task
def send_renewal_reminders():
    """Send renewal reminders - Monday 9 AM"""
    expired_memberships = MembershipPeriod.objects.filter(
        status='expired'
    ).order_by('-end_date')[:100]
    
    for membership in expired_memberships:
        send_renewal_reminder_email.delay(
            membership.member.email,
            membership.member.get_full_name(),
            membership.member.id,
            membership.end_date.strftime('%Y-%m-%d')
        )
    
    return f"Sent renewal reminders for {expired_memberships.count()} members"


@shared_task
def send_membership_expiry_email(member_email, member_name, days_remaining, member_id):
    """Send membership expiry email - Uses template"""
    html_message = render_to_string('emails/membership_expiry.html', {
        'member_name': member_name,
        'days_remaining': days_remaining,
    })
    
    send_mail(
        subject=f'⏰ Your Gym Membership Expiring in {days_remaining} Days!',
        message=f'Your membership will expire in {days_remaining} days.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent expiry email to {member_email}"


@shared_task
def send_membership_extended_email(member_email, member_name, additional_days, new_days_remaining):
    """Send extension email - Uses template"""
    html_message = render_to_string('emails/membership_extended.html', {
        'member_name': member_name,
        'additional_days': additional_days,
        'new_days_remaining': new_days_remaining,
    })
    
    send_mail(
        subject=f'✓ Your Membership Extended by {additional_days} Days',
        message=f'Your membership extended by {additional_days} days.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent extension email to {member_email}"


@shared_task
def send_membership_frozen_email(member_email, member_name, freeze_reason):
    """Send freeze email - Uses template"""
    html_message = render_to_string('emails/membership_frozen.html', {
        'member_name': member_name,
        'freeze_reason': freeze_reason or 'Personal reasons',
    })
    
    send_mail(
        subject='❄️ Your Membership Has Been Frozen',
        message=f'Your membership frozen for: {freeze_reason}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent freeze email to {member_email}"


@shared_task
def send_membership_unfrozen_email(member_email, member_name, new_days_remaining):
    """Send unfreeze email - Uses template"""
    html_message = render_to_string('emails/membership_unfrozen.html', {
        'member_name': member_name,
        'new_days_remaining': new_days_remaining,
    })
    
    send_mail(
        subject='✓ Your Membership Has Been Unfrozen',
        message=f'Your membership unfrozen! {new_days_remaining} days remaining.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent unfreeze email to {member_email}"


@shared_task
def send_membership_expired_email(member_email, member_name, gym_name):
    """Send expired email - Uses template"""
    html_message = render_to_string('emails/membership_expired.html', {
        'member_name': member_name,
        'gym_name': gym_name,
    })
    
    send_mail(
        subject='⏸️ Your Membership Has Expired',
        message=f'Your membership at {gym_name} has expired.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent expired email to {member_email}"


@shared_task
def send_admin_membership_expiry_alert(gym_id, member_name, days_remaining):
    """Send admin alert - Uses template"""
    try:
        gym = Gym.objects.get(id=gym_id)
        admin_email = gym.owner.email
    except Gym.DoesNotExist:
        return "Gym not found"
    
    html_message = render_to_string('emails/admin_expiry_alert.html', {
        'member_name': member_name,
        'days_remaining': days_remaining,
        'gym_name': gym.name,
    })
    
    send_mail(
        subject=f'⚠️ ALERT: {member_name} - Membership Expiring in {days_remaining} Days',
        message=f'Member {member_name} has {days_remaining} days left.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[admin_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent alert to admin {admin_email}"


@shared_task
def send_renewal_reminder_email(member_email, member_name, member_id, expired_date):
    """Send renewal reminder - Uses template"""
    html_message = render_to_string('emails/renewal_reminder.html', {
        'member_name': member_name,
        'expired_date': expired_date,
    })
    
    send_mail(
        subject='Come Back! Special Renewal Offers for You',
        message=f'Your membership expired on {expired_date}. Special offers available!',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    return f"Sent renewal reminder to {member_email}"

