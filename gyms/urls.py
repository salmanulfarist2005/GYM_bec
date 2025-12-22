# gyms/urls.py

from django.urls import path
from .views import (
    GymAPIView, 
    MyGymView,
    PaymentListView, 
    PlanListView,
    PlanDetailView,
    CreatePlanView,
    CreatePaymentView,
    PaymentDetailView,
    PaymentAnalyticsView,
    CreateMembershipPeriodView,
    MembershipPeriodListView,
    MembershipPeriodDetailView,
    FreezeMembershipView,
    UnfreezeMembershipView,
    ExpiringMembershipsView,
    MembershipHistoryView,
    ExtendMembershipView,
)

urlpatterns = [
   
    path('', GymAPIView.as_view(), name='gym-list-create'),
    path('<int:pk>/', GymAPIView.as_view(), name='gym-detail'),
    path('my-gym/', MyGymView.as_view(), name='my-gym'),
    
    # Plan Management (Admin only)
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('plans/create/', CreatePlanView.as_view(), name='plan-create'),
    path('plans/<int:pk>/', PlanDetailView.as_view(), name='plan-detail'),

    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/create/', CreatePaymentView.as_view(), name='payment-create'),
    path('payments/<uuid:payment_id>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('payments/analytics/', PaymentAnalyticsView.as_view(), name='payment-analytics'),
    path('payments/member/<int:member_id>/', PaymentListView.as_view(), name='member-payments'),


    path('memberships/create/', CreateMembershipPeriodView.as_view(), name='membership-create'),
    path('memberships/', MembershipPeriodListView.as_view(), name='membership-list'),
    path('memberships/member/<int:member_id>/', MembershipPeriodListView.as_view(), name='member-memberships'),
    path('memberships/<uuid:membership_id>/', MembershipPeriodDetailView.as_view(), name='membership-detail'),
    path('memberships/<uuid:membership_id>/extend/', ExtendMembershipView.as_view(), name='membership-extend'),
    path('memberships/<uuid:membership_id>/freeze/', FreezeMembershipView.as_view(), name='membership-freeze'),
    path('memberships/<uuid:membership_id>/unfreeze/', UnfreezeMembershipView.as_view(), name='membership-unfreeze'),
    path('memberships/expiring/soon/', ExpiringMembershipsView.as_view(), name='expiring-memberships'),
    path('memberships/history/<int:member_id>/', MembershipHistoryView.as_view(), name='membership-history'),
]