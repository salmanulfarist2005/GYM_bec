# gyms/serializers.py - Add to existing serializers

from rest_framework import serializers
from .models import Gym, Plan, Payment, MembershipPeriod
import ast


class GymSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    
    class Meta:
        model = Gym
        fields = ['id', 'name', 'description', 'address', 'phone', 'email', 
                  'owner', 'owner_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class PlanSerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    perks_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = ['id', 'gym', 'gym_name', 'name', 'duration_days', 'price', 
                  'perks', 'perks_list', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'gym', 'created_at', 'updated_at']
    
    def get_perks_list(self, obj):
        """Convert perks string to list"""
        if obj.perks:
            # Handle case where perks is already a list (during update)
            if isinstance(obj.perks, list):
                return obj.perks
            
            perks_str = str(obj.perks).strip()
            
            # Handle stringified list format e.g. "['gym', 'spa']" or '["gym"]'
            if perks_str.startswith('[') and perks_str.endswith(']'):
                try:
                    # Safely evaluate the string literal
                    parsed = ast.literal_eval(perks_str)
                    if isinstance(parsed, list):
                        return [str(p).strip() for p in parsed]
                except (ValueError, SyntaxError):
                    # Continue to comma split if parsing fails
                    pass
            
            # Handle basic comma separation
            return [perk.strip() for perk in perks_str.split(',') if perk.strip()]
        return []
    
    def create(self, validated_data):
        if isinstance(validated_data.get('perks'), list):
            validated_data['perks'] = ', '.join(validated_data['perks'])
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        if isinstance(validated_data.get('perks'), list):
            validated_data['perks'] = ', '.join(validated_data['perks'])
        return super().update(instance, validated_data)


class CreatePlanSerializer(serializers.ModelSerializer):
    """
    Serializer for creating plans - accepts perks as list or string
    """
    perks = serializers.ListField(child=serializers.CharField(), required=True)
    
    class Meta:
        model = Plan
        fields = ['name', 'duration_days', 'price', 'perks', 'is_active']
    
    def validate_duration_days(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than 0")
        return value
    
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
    
    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Plan name cannot be empty")
        return value
    
    def create(self, validated_data):
        perks_list = validated_data.pop('perks')
        validated_data['perks'] = ', '.join(perks_list)
        return super().create(validated_data)
    







class PaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    member_email = serializers.CharField(source='member.email', read_only=True)
    membership_details = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'member', 'member_name', 'member_email',
            'applied_membership', 'membership_details',
            'amount', 'payment_method', 'payment_status',
            'receipt_no', 'transaction_id', 'payment_date',
            'notes', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'receipt_no', 'created_at', 'updated_at', 'created_by']
    
    def get_membership_details(self, obj):
        if obj.applied_membership:
            return {
                'id': str(obj.applied_membership.id),
                'start_date': obj.applied_membership.start_date,
                'end_date': obj.applied_membership.end_date,
                'status': obj.applied_membership.status
            }
        return None


class CreatePaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating payment records
    """
    class Meta:
        model = Payment
        fields = [
            'member', 'applied_membership', 'amount',
            'payment_method', 'payment_status',
            'transaction_id', 'notes', 'payment_date'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate_member(self, value):
        # 1. Basic user type validation
        if value.user_type != 'member':
            raise serializers.ValidationError("Selected user is not a member")
        
        # 2. Context-based validation (ensure member matches admin's gym)
        request = self.context.get('request')
        if request and request.user and request.user.user_type == 'admin':
            admin_gym = request.user.gym
            try:
                # Assuming simple relation or via profile
                # If member.gym is direct on User model (from accounts.models):
                member_gym = value.gym 
                
                # Double check against profile if needed, but User.gym is safer if synced
                if member_gym != admin_gym:
                    raise serializers.ValidationError("Member does not belong to your gym")
            except AttributeError:
                 # Fallback if structure varies
                 pass
        
        return value
    
    def validate_applied_membership(self, value):
        if value and value.status not in ['active', 'frozen']:
            raise serializers.ValidationError("Cannot create payment for inactive or expired membership")
        return value
    
    def validate(self, data):
        member = data.get('member')
        applied_membership = data.get('applied_membership')
        
        # Ensure membership belongs to the selected member
        if applied_membership and applied_membership.member != member:
            raise serializers.ValidationError({"applied_membership": "Membership does not belong to the selected member"})
        
        return data

    
    

class UpdatePaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for updating payment status
    """
    class Meta:
        model = Payment
        fields = ['payment_status', 'transaction_id', 'notes']
    
    def validate_payment_status(self, value):
        valid_statuses = ['pending', 'completed', 'failed', 'cancelled', 'refunded']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Choose from {valid_statuses}")
        return value



class PaymentReportSerializer(serializers.ModelSerializer):
    """
    Serializer for payment reports and analytics
    """
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    plan_name = serializers.CharField(source='applied_plan.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'member', 'member_name',
            'applied_plan', 'plan_name', 'amount',
            'payment_method', 'payment_status', 'payment_date'
        ]




class MembershipPeriodSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    member_email = serializers.CharField(source='member.email', read_only=True)
    payment_receipt = serializers.CharField(source='source_payment.receipt_no', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    is_expiring_soon = serializers.SerializerMethodField()
    is_active_membership = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = MembershipPeriod
        fields = [
            'id', 'member', 'member_name', 'member_email',
            'source_payment', 'payment_receipt',
            'start_date', 'end_date', 'days_remaining',
            'status', 'is_expiring_soon', 'is_active_membership',
            'frozen_date', 'freeze_reason',  
            'expiry_alert_sent',  
            'notes', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'days_remaining', 'is_expiring_soon', 
            'is_active_membership', 'created_by', 'created_at', 'updated_at',
            'expiry_alert_sent'  
        ]
    
    def get_days_remaining(self, obj):
        return obj.days_remaining
    
    def get_is_expiring_soon(self, obj):
        return obj.is_expiring_soon
    
    def get_is_active_membership(self, obj):
        return obj.is_active_membership


class CreateMembershipPeriodSerializer(serializers.ModelSerializer):
    """Create a new membership period"""
    class Meta:
        model = MembershipPeriod
        fields = ['member', 'source_payment', 'start_date', 'end_date', 'notes']
    
    def validate_member(self, value):
        if value.user_type != 'member':
            raise serializers.ValidationError("Selected user is not a member")
        return value
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError("End date must be after start date")
        
        return data


class UpdateMembershipPeriodSerializer(serializers.ModelSerializer):
    """Update membership period details"""
    class Meta:
        model = MembershipPeriod
        fields = ['start_date', 'end_date', 'status', 'notes']
    
    def validate(self, data):
        start_date = data.get('start_date') or self.instance.start_date
        end_date = data.get('end_date') or self.instance.end_date
        
        if end_date <= start_date:
            raise serializers.ValidationError("End date must be after start date")
        
        return data


class ExtendMembershipSerializer(serializers.Serializer):
    """Extend membership by additional days"""
    additional_days = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_additional_days(self, value):
        if value < 1:
            raise serializers.ValidationError("Additional days must be at least 1")
        return value


class FreezeMembershipSerializer(serializers.Serializer):
    """Freeze membership"""
    freeze_reason = serializers.CharField(required=False, allow_blank=True)


class UnfreezeMembershipSerializer(serializers.Serializer):
    """Unfreeze membership"""
    notes = serializers.CharField(required=False, allow_blank=True)


class ExpiringMembershipSerializer(serializers.ModelSerializer):
    """Serializer for memberships expiring soon"""
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    member_email = serializers.CharField(source='member.email', read_only=True)
    member_phone = serializers.CharField(source='member.phone', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    alert_sent = serializers.BooleanField(source='expiry_alert_sent', read_only=True)
    
    class Meta:
        model = MembershipPeriod
        fields = [
            'id',
            'member',
            'member_name',
            'member_email',
            'member_phone',
            'start_date',
            'end_date',
            'days_remaining',
            'status',
            'alert_sent',
        ]
    
    def get_days_remaining(self, obj):
        return obj.days_remaining