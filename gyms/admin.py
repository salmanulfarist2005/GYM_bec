from django.contrib import admin
from .models import Gym, Plan, Payment, MembershipPeriod

# Register your models here.
admin.site.register(Gym)
admin.site.register(Plan)
admin.site.register(Payment)
admin.site.register(MembershipPeriod)