# accounts/urls.py
from django.urls import path
from .views import (
    RegisterView, 
    LoginView, 
    CreateAdminView, 
    CreateMemberView, 
    UserListView,
    AdminListView,
    AdminDetailView,
    SendOTPView,
    MemberLoginView, 
    MemberVerifyOTPView,
    SetPasswordView,
    ForgotPasswordView, 
    VerifyResetOTPView, 
    ResetPasswordView,
    MemberProfileView,
    MemberListView
)

urlpatterns = [
    # Registration
    path('register/', RegisterView.as_view(), name='register'),
    
    path('login/', LoginView.as_view(), name='login'),
    
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    path('member-login/', MemberLoginView.as_view(), name='member-login'),
    path('member-verify-otp/', MemberVerifyOTPView.as_view(), name='member-verify-otp'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    
    # User Management
    path('create-admin/', CreateAdminView.as_view(), name='create-admin'),
    path('create-member/', CreateMemberView.as_view(), name='create-member'),
    path('admins/<int:pk>/', AdminDetailView.as_view(), name='admin-detail'),
    path('admins/', AdminListView.as_view(), name='admin-list'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('member-profile/', MemberProfileView.as_view(), name='member-profile'),
    path('member-profile/<int:pk>/', MemberProfileView.as_view(), name='member-profile-detail'),
    
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('members/', MemberListView.as_view(), name='member-list'),
]