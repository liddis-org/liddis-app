from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, VerificationCode


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_email_verified', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_email_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        ('LIDDIS', {'fields': (
            'role',
            'phone',
            'date_of_birth',
            'bio',
            'profession',
            'professional_specialty',
            'is_email_verified',
            'is_phone_verified',
        )}),
    )


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'is_used', 'is_expired', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('code', 'created_at', 'expires_at')
