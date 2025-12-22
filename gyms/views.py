# gyms/views.py - Updated with proper task integration

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from .models import Gym, Plan, Payment, MembershipPeriod
from .serializers import (
    GymSerializer, PlanSerializer, CreatePlanSerializer, 
    PaymentSerializer, CreatePaymentSerializer, UpdatePaymentSerializer,
    MembershipPeriodSerializer, CreateMembershipPeriodSerializer, 
    UpdateMembershipPeriodSerializer,
    ExtendMembershipSerializer, FreezeMembershipSerializer, 
    UnfreezeMembershipSerializer, ExpiringMembershipSerializer,

)
from accounts.permissions import IsSuperUser, IsGymAdmin, IsSuperUserOrAdmin

# Import all tasks at the top
from .tasks import (
    
    send_membership_expiry_email,
    send_membership_extended_email,
    send_membership_frozen_email,
    send_membership_unfrozen_email,
    send_membership_expired_email,
    send_admin_membership_expiry_alert,
    send_renewal_reminder_email
)


class GymAPIView(APIView):
    permission_classes = [IsSuperUser]
    
    def get(self, request, pk=None):
        """Get single gym by ID or list all gyms"""
        if pk:
            try:
                gym = Gym.objects.get(pk=pk)
                serializer = GymSerializer(gym)
                return Response(serializer.data)
            except Gym.DoesNotExist:
                return Response({'error': 'Gym not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            gyms = Gym.objects.all()
            serializer = GymSerializer(gyms, many=True)
            return Response(serializer.data)
    
    def post(self, request):
        """Create a new gym"""
        serializer = GymSerializer(data=request.data)
        if serializer.is_valid():
            gym = serializer.save(owner=request.user)
            return Response(GymSerializer(gym).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk):
        """Full update of a gym"""
        try:
            gym = Gym.objects.get(pk=pk)
        except Gym.DoesNotExist:
            return Response({'error': 'Gym not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = GymSerializer(gym, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """Partial update of a gym"""
        try:
            gym = Gym.objects.get(pk=pk)
        except Gym.DoesNotExist:
            return Response({'error': 'Gym not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = GymSerializer(gym, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete a gym"""
        try:
            gym = Gym.objects.get(pk=pk)
            gym.delete()
            return Response({'message': 'Gym deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Gym.DoesNotExist:
            return Response({'error': 'Gym not found'}, status=status.HTTP_404_NOT_FOUND)


class MyGymView(APIView):
    permission_classes = [IsGymAdmin]
    
    def get(self, request):
        """Get admin's assigned gym"""
        if request.user.gym:
            serializer = GymSerializer(request.user.gym)
            return Response(serializer.data)
        return Response({'error': 'No gym assigned'}, status=status.HTTP_404_NOT_FOUND)


class PlanListView(APIView):
    """Get all plans for admin's gym"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request):
        """Get all plans for the admin's gym"""
        plans = Plan.objects.filter(gym=request.user.gym)
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)


class PlanDetailView(APIView):
    """Get, update, delete specific plan"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, pk):
        """Get specific plan"""
        try:
            plan = Plan.objects.get(pk=pk, gym=request.user.gym)
            serializer = PlanSerializer(plan)
            return Response(serializer.data)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, pk):
        """Full update of plan"""
        try:
            plan = Plan.objects.get(pk=pk, gym=request.user.gym)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CreatePlanSerializer(data=request.data)
        if serializer.is_valid():
            for attr, value in serializer.validated_data.items():
                setattr(plan, attr, value)
            plan.save()
            return Response(PlanSerializer(plan).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """Partial update of plan"""
        try:
            plan = Plan.objects.get(pk=pk, gym=request.user.gym)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CreatePlanSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            for attr, value in serializer.validated_data.items():
                if value is not None:
                    setattr(plan, attr, value)
            plan.save()
            return Response(PlanSerializer(plan).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete plan"""
        try:
            plan = Plan.objects.get(pk=pk, gym=request.user.gym)
            plan.delete()
            return Response({'message': 'Plan deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)


class CreatePlanView(APIView):
    """Create new plan for admin's gym"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request):
        """Create a new plan for the admin's gym"""
        serializer = CreatePlanSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.save(gym=request.user.gym)
            return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreatePaymentView(APIView):
    """Create a payment record for a member"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request):
        """Create payment for a member"""
        serializer = CreatePaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save(created_by=request.user)
            return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentListView(APIView):
    """List payments"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, member_id=None):
        """Get payments for admin's gym"""
        if request.user.user_type != 'admin':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        if member_id:
            payments = Payment.objects.filter(
                member__gym=request.user.gym,
                member_id=member_id
            )
        else:
            payments = Payment.objects.filter(member__gym=request.user.gym)
        
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)


class PaymentDetailView(APIView):
    """Get, update, delete specific payment"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, payment_id):
        """Get payment detail"""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if payment.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = PaymentSerializer(payment)
        return Response(serializer.data)
    
    def patch(self, request, payment_id):
        """Partial update payment (admin only)"""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if payment.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = UpdatePaymentSerializer(payment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(PaymentSerializer(payment).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, payment_id):
        """Full update payment (admin only)"""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if payment.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = UpdatePaymentSerializer(data=request.data)
        if serializer.is_valid():
            for attr, value in serializer.validated_data.items():
                setattr(payment, attr, value)
            payment.save()
            return Response(PaymentSerializer(payment).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, payment_id):
        """Delete payment (admin only)"""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if payment.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        payment.delete()
        return Response({'message': 'Payment deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class PaymentAnalyticsView(APIView):
    """Get payment analytics and reports"""
    permission_classes = [IsSuperUserOrAdmin]
    
    def get(self, request):
        """Get payment analytics"""
        if request.user.user_type == 'superuser':
            payments = Payment.objects.filter(payment_status='completed')
            gyms = "All Gyms"
        elif request.user.user_type == 'admin':
            payments = Payment.objects.filter(
                member__gym=request.user.gym,
                payment_status='completed'
            )
            gyms = request.user.gym.name
        else:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        total_revenue = payments.aggregate(Sum('amount'))['amount__sum'] or 0
        total_payments = payments.count()
        
        revenue_by_method = {}
        for method, label in Payment.PAYMENT_METHOD_CHOICES:
            revenue = payments.filter(payment_method=method).aggregate(Sum('amount'))['amount__sum'] or 0
            revenue_by_method[label] = float(revenue)
        
        revenue_by_plan = {}
        for payment in payments:
            plan_name = payment.applied_plan.name if payment.applied_plan else 'No Plan'
            if plan_name not in revenue_by_plan:
                revenue_by_plan[plan_name] = 0
            revenue_by_plan[plan_name] += float(payment.amount)
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_payments = payments.filter(payment_date__gte=thirty_days_ago)
        last_30_days_revenue = recent_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        
        if request.user.user_type == 'superuser':
            all_payments = Payment.objects.all()
        else:
            all_payments = Payment.objects.filter(member__gym=request.user.gym)
        
        status_breakdown = {}
        for status_code, label in Payment.PAYMENT_STATUS_CHOICES:
            count = all_payments.filter(payment_status=status_code).count()
            status_breakdown[label] = count
        
        analytics = {
            'gym': gyms,
            'total_revenue': float(total_revenue),
            'total_payments': total_payments,
            'last_30_days_revenue': float(last_30_days_revenue),
            'revenue_by_payment_method': revenue_by_method,
            'revenue_by_plan': revenue_by_plan,
            'payment_status_breakdown': status_breakdown,
        }
        
        return Response(analytics)


class CreateMembershipPeriodView(APIView):
    """Create a new membership period for a member"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request):
        """Create membership period after payment"""
        serializer = CreateMembershipPeriodSerializer(data=request.data)
        if serializer.is_valid():
            membership = serializer.save(created_by=request.user)
            
            return Response(
                MembershipPeriodSerializer(membership).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MembershipPeriodListView(APIView):
    """List membership periods for admin's gym"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, member_id=None):
        """Get membership periods"""
        if member_id:
            memberships = MembershipPeriod.objects.filter(
                member__gym=request.user.gym,
                member_id=member_id
            )
        else:
            memberships = MembershipPeriod.objects.filter(
                member__gym=request.user.gym
            )
        
        serializer = MembershipPeriodSerializer(memberships, many=True)
        return Response(serializer.data)


class MembershipPeriodDetailView(APIView):
    """Get, update, delete specific membership"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, membership_id):
        """Get membership detail"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = MembershipPeriodSerializer(membership)
        return Response(serializer.data)
    
    def patch(self, request, membership_id):
        """Partial update membership (admin only)"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = UpdateMembershipPeriodSerializer(membership, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(MembershipPeriodSerializer(membership).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, membership_id):
        """Full update membership (admin only)"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = UpdateMembershipPeriodSerializer(data=request.data)
        if serializer.is_valid():
            for attr, value in serializer.validated_data.items():
                setattr(membership, attr, value)
            membership.save()
            return Response(MembershipPeriodSerializer(membership).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, membership_id):
        """Delete membership (admin only)"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        membership.delete()
        return Response({'message': 'Membership deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class ExtendMembershipView(APIView):
    """Extend member's membership by additional days"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request, membership_id):
        """Extend membership"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ExtendMembershipSerializer(data=request.data)
        if serializer.is_valid():
            additional_days = serializer.validated_data['additional_days']
            notes = serializer.validated_data.get('notes', '')
            
            try:
                old_end_date = membership.end_date
                membership.extend(additional_days)
                membership.notes = f"Extended by {additional_days} days. {notes}"
                membership.save()
                
                # Send extension email asynchronously
                send_membership_extended_email.delay(
                    membership.member.email,
                    membership.member.get_full_name(),
                    additional_days,
                    membership.days_remaining
                )
                
                return Response({
                    'message': f'Membership extended by {additional_days} days',
                    'old_end_date': old_end_date.strftime('%Y-%m-%d'),
                    'new_end_date': membership.end_date.strftime('%Y-%m-%d'),
                    'days_remaining': membership.days_remaining,
                    'membership': MembershipPeriodSerializer(membership).data
                }, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FreezeMembershipView(APIView):
    """Freeze member's membership"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request, membership_id):
        """Freeze membership"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = FreezeMembershipSerializer(data=request.data)
        if serializer.is_valid():
            freeze_reason = serializer.validated_data.get('freeze_reason', '')
            
            membership.freeze(freeze_reason=freeze_reason)
            
            # Send freeze email asynchronously
            send_membership_frozen_email.delay(
                membership.member.email,
                membership.member.get_full_name(),
                freeze_reason
            )
            
            return Response({
                'message': 'Membership frozen',
                'freeze_reason': freeze_reason,
                'frozen_date': timezone.now().strftime('%Y-%m-%d'),
                'membership': MembershipPeriodSerializer(membership).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UnfreezeMembershipView(APIView):
    """Unfreeze member's membership"""
    permission_classes = [IsGymAdmin]
    
    def post(self, request, membership_id):
        """Unfreeze membership"""
        try:
            membership = MembershipPeriod.objects.get(id=membership_id)
        except MembershipPeriod.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if membership.member.gym != request.user.gym:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        if membership.status != 'frozen':
            return Response(
                {'error': 'Only frozen memberships can be unfrozen'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = UnfreezeMembershipSerializer(data=request.data)
        if serializer.is_valid():
            old_end_date = membership.end_date
            membership.unfreeze()
            
            # Send unfreeze email asynchronously
            send_membership_unfrozen_email.delay(
                membership.member.email,
                membership.member.get_full_name(),
                membership.days_remaining
            )
            
            return Response({
                'message': 'Membership unfrozen and extended',
                'freeze_duration_days': (membership.end_date - old_end_date).days,
                'old_end_date': old_end_date.strftime('%Y-%m-%d'),
                'new_end_date': membership.end_date.strftime('%Y-%m-%d'),
                'days_remaining': membership.days_remaining,
                'membership': MembershipPeriodSerializer(membership).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpiringMembershipsView(APIView):
    """Get memberships expiring within 7 days"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request):
        """Get all memberships expiring within 7 days"""
        memberships = MembershipPeriod.objects.filter(
            member__gym=request.user.gym,
            status='active'
        )
        
        expiring = [m for m in memberships if m.is_expiring_soon]
        
        serializer = ExpiringMembershipSerializer(expiring, many=True)
        
        return Response({
            'count': len(expiring),
            'gym': request.user.gym.name,
            'message': f'{len(expiring)} memberships expiring within 7 days',
            'memberships': serializer.data
        })
    
    def post(self, request):
        """Manually send expiry alerts"""
        memberships = MembershipPeriod.objects.filter(
            member__gym=request.user.gym,
            status='active',
            expiry_alert_sent=False
        )
        
        expiring = [m for m in memberships if m.is_expiring_soon]
        
        sent_count = 0
        for membership in expiring:
            # Send member email
            send_membership_expiry_email.delay(
                membership.member.email,
                membership.member.get_full_name(),
                membership.days_remaining,
                membership.member.id
            )
            
            # Send admin alert
            send_admin_membership_expiry_alert.delay(
                membership.member.gym.id,
                membership.member.get_full_name(),
                membership.days_remaining
            )
            
            membership.mark_expiry_alert_sent()
            sent_count += 1
        
        return Response({
            'message': f'Sent expiry alerts for {sent_count} memberships',
            'count': sent_count,
            'gym': request.user.gym.name
        }, status=status.HTTP_200_OK)


class MembershipHistoryView(APIView):
    """Get complete membership history for a member"""
    permission_classes = [IsGymAdmin]
    
    def get(self, request, member_id):
        """Get all membership periods for a member"""
        memberships = MembershipPeriod.objects.filter(
            member__gym=request.user.gym,
            member_id=member_id
        ).order_by('-start_date')
        
        if not memberships.exists():
            return Response(
                {'error': 'No memberships found for this member'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MembershipPeriodSerializer(memberships, many=True)
        
        return Response({
            'member_id': member_id,
            'member_name': memberships.first().member.get_full_name(),
            'member_email': memberships.first().member.email,
            'total_memberships': memberships.count(),
            'active_memberships': memberships.filter(status='active').count(),
            'expired_memberships': memberships.filter(status='expired').count(),
            'frozen_memberships': memberships.filter(status='frozen').count(),
            'total_spent': sum(
                m.source_payment.amount for m in memberships if m.source_payment
            ),
            'history': serializer.data
        })