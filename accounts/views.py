# accounts/views.py
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP, MemberProfile
from .serializers import (
    UserSerializer, AdminCreateSerializer, MemberCreateSerializer,
    SendOTPSerializer, VerifyOTPSerializer, SetPasswordSerializer,
    ForgotPasswordSerializer, VerifyResetOTPSerializer, ResetPasswordSerializer,
    MemberProfileSerializer
)
from .permissions import IsSuperUser, IsGymAdmin, IsCustomer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Admin & Superuser Login
class LoginView(APIView):
    """
    Login for Superuser and Admin only
    Uses username/password with JWT tokens
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'error': 'Username/Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to fetch by username, then by email
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.filter(email=username).first()
        
        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                 return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)


# Member Login
class MemberLoginView(APIView):
    """
    Smart Member Login:
    - If password not set (first time) → Send OTP
    - If password already set → Allow username/password OR OTP
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        username = request.data.get('username')
        
        if email and not password:
            try:
                user = User.objects.get(email=email, user_type='member')
            except User.DoesNotExist:
                return Response({
                    'error': 'No member account found with this email'
                }, status=status.HTTP_404_NOT_FOUND)
            
            if not user.password_set:
                serializer = SendOTPSerializer(data={'email': email})
                if serializer.is_valid():
                    try:
                        otp = serializer.send_otp()
                        return Response({
                            'message': 'First time login. OTP sent to your email',
                            'email': otp.email,
                            'expires_in': '5 minutes',
                            'next_step': 'Verify OTP and set password',
                            'password_set': False
                        }, status=status.HTTP_200_OK)
                    except Exception as e:
                        return Response({
                            'error': 'Failed to send OTP',
                            'detail': str(e)
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                serializer = SendOTPSerializer(data={'email': email})
                if serializer.is_valid():
                    try:
                        otp = serializer.send_otp()
                        return Response({
                            'message': 'OTP sent to your email',
                            'email': otp.email,
                            'expires_in': '5 minutes',
                            'note': 'You can also login with username and password',
                            'username': user.username,
                            'password_set': True
                        }, status=status.HTTP_200_OK)
                    except Exception as e:
                        return Response({
                            'error': 'Failed to send OTP',
                            'detail': str(e)
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Case 2: Username + Password login (for returning members)
        elif (username or email) and password:
            user = None
            if username:
                user = User.objects.filter(username=username, user_type='member').first()
            elif email:
                user = User.objects.filter(email=email, user_type='member').first()
            
            if user and user.check_password(password):
                if user.password_set:
                    refresh = RefreshToken.for_user(user)
                    return Response({
                        'message': 'Login successful',
                        'user': UserSerializer(user).data,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'error': 'Please complete first-time setup with OTP'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        else:
            return Response({
                'error': 'Please provide email (for OTP) or username/email with password'
            }, status=status.HTTP_400_BAD_REQUEST)





class MemberVerifyOTPView(APIView):
    """
    Verify OTP and complete login for members
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']
            
            if user.user_type != 'member':
                return Response({
                    'error': 'This endpoint is for members only'
                }, status=status.HTTP_403_FORBIDDEN)
            
            otp.is_verified = True
            otp.save()
            
            user.is_email_verified = True
            user.save()
            
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                'message': 'OTP verified successfully',
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            
            if not user.password_set:
                response_data['next_step'] = 'Please set your password'
                response_data['set_password_url'] = '/api/accounts/set-password/'
            else:
                response_data['message'] = 'Login successful'
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SetPasswordView(APIView):
    """
    Member sets password after first OTP login
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.user_type != 'member':
            return Response({
                'error': 'This endpoint is for members only'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if user.password_set:
            return Response({
                'error': 'Password already set. Use change password endpoint instead.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user)
            return Response({
                'message': 'Password set successfully. You can now login with username and password.',
                'username': user.username,
                'note': 'You can also continue using OTP login'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Forgot Password Views for Admin/Superuser
class ForgotPasswordView(APIView):
    """
    Step 1: Admin/Superuser forgot password - Send OTP to email
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                otp = serializer.send_reset_otp()
                return Response({
                    'message': 'Password reset OTP sent to your email',
                    'email': otp.email,
                    'expires_in': '5 minutes',
                    'next_step': 'Verify OTP and reset password'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': 'Failed to send OTP. Please try again.',
                    'detail': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyResetOTPView(APIView):
    """
    Step 2: Verify password reset OTP
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyResetOTPSerializer(data=request.data)
        if serializer.is_valid():
            return Response({
                'message': 'OTP verified successfully',
                'next_step': 'You can now reset your password',
                'email': serializer.validated_data['user'].email
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """
    Step 3: Reset password with OTP
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Password reset successfully',
                'username': user.username,
                'note': 'You can now login with your new password'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendOTPView(APIView):
    """
    General OTP sending endpoint
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            try:
                otp = serializer.send_otp()
                return Response({
                    'message': 'OTP sent successfully to your email',
                    'email': otp.email,
                    'expires_in': '5 minutes'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'error': 'Failed to send OTP. Please try again.',
                    'detail': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateAdminView(APIView):
    permission_classes = [IsSuperUser]
    
    def post(self, request):
        serializer = AdminCreateSerializer(data=request.data)
        if serializer.is_valid():
            admin = serializer.save(created_by=request.user)
            return Response(UserSerializer(admin).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateMemberView(APIView):
    """
    Create a new member with extended profile
    """
    permission_classes = [IsGymAdmin]
    
    def post(self, request):
        serializer = MemberCreateSerializer(data=request.data)
        if serializer.is_valid():
           
            member_user = serializer.create(
                validated_data=serializer.validated_data,
                gym=request.user.gym,
                created_by=request.user
            )
            
            member_profile = MemberProfile.objects.get(user=member_user)
            
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                
                subject = 'Welcome to Our Gym!'
                message = f'''
Hello {member_user.first_name or member_user.email},

Welcome to {request.user.gym.name}!

Your member account has been created successfully.

Email: {member_user.email}
Username: {member_user.username}

For your first login, please:
1. Go to member login page
2. Enter your email: {member_user.email}
3. You'll receive an OTP via email
4. Verify OTP and set your password

After setting your password, you can login with:
- Username: {member_user.username} + Password
- OR continue using Email + OTP

Best regards,
{request.user.gym.name} Team
                '''
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [member_user.email],
                    fail_silently=True,
                )
            except Exception as e:
                pass
            
            return Response({
                'message': 'Member created successfully',
                'member': MemberProfileSerializer(member_profile).data,
                'note': 'Member should login with email for first-time setup'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class MemberProfileView(APIView):
    """
    Get and update member profile
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk=None):
        """Get member profile"""
        if pk:
            try:
                member_profile = MemberProfile.objects.get(pk=pk, gym=request.user.gym)
                serializer = MemberProfileSerializer(member_profile)
                return Response(serializer.data)
            except MemberProfile.DoesNotExist:
                return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            
            if request.user.user_type == 'member':
                try:
                    member_profile = MemberProfile.objects.get(user=request.user)
                    serializer = MemberProfileSerializer(member_profile)
                    return Response(serializer.data)
                except MemberProfile.DoesNotExist:
                    return Response({'error': 'Member profile not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({'error': 'Only members can access this'}, status=status.HTTP_403_FORBIDDEN)
    
    def put(self, request, pk=None):
        """Update member profile"""
        if not pk:
            return Response({'error': 'Member ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            member_profile = MemberProfile.objects.get(pk=pk, gym=request.user.gym)
        except MemberProfile.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MemberProfileSerializer(member_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Delete member and associated user"""
        if not pk:
            return Response({'error': 'Member ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            member_profile = MemberProfile.objects.get(pk=pk, gym=request.user.gym)
            user = member_profile.user
            user.delete() # This will cascade delete member_profile
            return Response({'message': 'Member deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except MemberProfile.DoesNotExist:
            return Response({'error': 'Member not found'}, status=status.HTTP_404_NOT_FOUND)
    


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'superuser':
            return User.objects.all()
        elif user.user_type == 'admin':
            return User.objects.filter(gym=user.gym)
        else:
            return User.objects.filter(id=user.id)

class AdminListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsSuperUser]
    queryset = User.objects.filter(user_type='admin')

class AdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsSuperUser]
    queryset = User.objects.filter(user_type='admin')
    
    
class MemberListView(generics.ListAPIView):
    serializer_class = MemberProfileSerializer
    permission_classes = [IsGymAdmin]
    
    def get_queryset(self):
        return MemberProfile.objects.filter(gym=self.request.user.gym)
