# accounts/serializers.py
from rest_framework import serializers
from .models import User, OTP, MemberProfile
from gyms.models import Gym
from django.core.mail import send_mail
from django.conf import settings

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 
                  'phone', 'user_type', 'gym', 'gym_name', 'is_email_verified', 
                  'password_set', 'created_at', 'is_superuser']
        read_only_fields = ['id', 'created_at', 'is_email_verified', 'password_set']
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
            user.password_set = True
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
            instance.password_set = True
        
        instance.save()
        return instance


class MemberProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    
    class Meta:
        model = MemberProfile
        fields = [
            'id', 'user', 'gym', 'gym_name',
            'date_of_birth', 'gender', 'address', 'city',
            'emergency_contact_name', 'emergency_contact_phone',
            'membership_status', 'membership_start_date', 'membership_end_date',
            'height', 'weight',
            'preferred_schedule', 'fitness_goals', 'notes',
            'is_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'gym', 'membership_start_date', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        
        # Update User fields
        for attr, value in user_data.items():
            if attr not in ['password', 'username', 'id', 'gym', 'user_type']: # Protect certain fields
                setattr(user, attr, value)
        user.save()
        
        # Update MemberProfile fields
        return super().update(instance, validated_data)


class AdminCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    gym = serializers.PrimaryKeyRelatedField(queryset=Gym.objects.all())
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'phone', 'gym']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['user_type'] = 'admin'
        validated_data['password_set'] = True
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class MemberCreateSerializer(serializers.Serializer):
    """
    Member creation WITHOUT password
    First login requires OTP, then member sets password
    """
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False)
    
    # Member Profile fields
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.CharField(max_length=1, required=False)
    address = serializers.CharField(required=False)
    city = serializers.CharField(max_length=100, required=False)
    emergency_contact_name = serializers.CharField(max_length=200, required=False)
    emergency_contact_phone = serializers.CharField(max_length=15, required=False)
    height = serializers.FloatField(required=False)
    weight = serializers.FloatField(required=False)
    preferred_schedule = serializers.CharField(required=False)
    fitness_goals = serializers.CharField(required=False)
    notes = serializers.CharField(required=False)
    
    def validate_email(self, value):
        """Check if email already exists"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def create(self, validated_data, gym=None, created_by=None):
        # Extract member profile fields
        member_profile_fields = {
            'date_of_birth', 'gender', 'address', 'city', 
            'emergency_contact_name', 'emergency_contact_phone',
            'height', 'weight',
            'preferred_schedule', 'fitness_goals', 'notes'
        }
        
        member_data = {k: v for k, v in validated_data.items() if k in member_profile_fields}
        user_data = {k: v for k, v in validated_data.items() if k not in member_profile_fields}
        
        # Create User
        email = user_data.pop('email')
        base_username = email.split('@')[0]
        username = base_username
        
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User(
            username=username,
            email=email,
            user_type='member',
            gym=gym,
            created_by=created_by,
            **user_data
        )
        user.set_unusable_password()
        user.password_set = False
        user.save()
        
        # Create Member Profile
        member_profile = MemberProfile(
            user=user,
            gym=gym,
            **member_data
        )
        member_profile.save()
        
        return user


class SetPasswordSerializer(serializers.Serializer):
    """
    Serializer for member to set password after first OTP login
    """
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
    
    def save(self, user):
        user.set_password(self.validated_data['password'])
        user.password_set = True
        user.save()
        return user


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value, user_type='member')
        except User.DoesNotExist:
            raise serializers.ValidationError("No member account found with this email.")
        return value
    
    def send_otp(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email, user_type='member')
        
        OTP.objects.filter(user=user, is_verified=False, otp_type='login').update(is_verified=True)
        
        otp = OTP.objects.create(user=user, email=email, otp_type='login')
        
        subject = 'Your Login OTP'
        message = f'''
Hello {user.first_name or user.username},

Your OTP for login is: {otp.otp_code}

This OTP will expire in 5 minutes.

If you didn't request this, please ignore this email.

Best regards,
Gym Management Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return otp


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        email = data.get('email')
        otp_code = data.get('otp_code')
        
        try:
            user = User.objects.get(email=email, user_type='member')
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email.")
        
        try:
            otp = OTP.objects.filter(
                user=user,
                email=email,
                otp_code=otp_code,
                is_verified=False,
                otp_type='login'
            ).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        if not otp.is_valid():
            raise serializers.ValidationError("OTP has expired or already used.")
        
        data['user'] = user
        data['otp'] = otp
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    """
    Send OTP for password reset to Admin/Superuser email
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value, user_type__in=['admin', 'superuser'])
        except User.DoesNotExist:
            raise serializers.ValidationError("No admin/superuser account found with this email.")
        return value
    
    def send_reset_otp(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email, user_type__in=['admin', 'superuser'])
        
        OTP.objects.filter(user=user, is_verified=False, otp_type='password_reset').update(is_verified=True)
        
        otp = OTP.objects.create(user=user, email=email, otp_type='password_reset')
        
        subject = 'Password Reset OTP'
        message = f'''
Hello {user.first_name or user.username},

You have requested to reset your password.

Your password reset OTP is: {otp.otp_code}

This OTP will expire in 5 minutes.

If you didn't request this, please ignore this email and your password will remain unchanged.

Best regards,
Gym Management Team
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return otp


class VerifyResetOTPSerializer(serializers.Serializer):
    """
    Verify OTP for password reset
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        email = data.get('email')
        otp_code = data.get('otp_code')
        
        try:
            user = User.objects.get(email=email, user_type__in=['admin', 'superuser'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email.")
        
        try:
            otp = OTP.objects.filter(
                user=user,
                email=email,
                otp_code=otp_code,
                is_verified=False,
                otp_type='password_reset'
            ).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        if not otp.is_valid():
            raise serializers.ValidationError("OTP has expired or already used.")
        
        data['user'] = user
        data['otp'] = otp
        return data


class ResetPasswordSerializer(serializers.Serializer):
    """
    Reset password after OTP verification
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        email = data.get('email')
        otp_code = data.get('otp_code')
        
        try:
            user = User.objects.get(email=email, user_type__in=['admin', 'superuser'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email.")
        
        try:
            otp = OTP.objects.filter(
                user=user,
                email=email,
                otp_code=otp_code,
                is_verified=False,
                otp_type='password_reset'
            ).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        if not otp.is_valid():
            raise serializers.ValidationError("OTP has expired or already used.")
        
        data['user'] = user
        data['otp'] = otp
        return data
    
    def save(self):
        user = self.validated_data['user']
        otp = self.validated_data['otp']
        new_password = self.validated_data['new_password']
        
        otp.is_verified = True
        otp.save()
        
        user.set_password(new_password)
        user.save()
        
        return user