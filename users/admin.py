from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, VerificationCode, Organization, OrganizationMember, PatientProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'plan', 'is_active', 'created_at')
    list_filter   = ('plan', 'is_active')
    search_fields = ('name', 'slug', 'cnpj', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'organization', 'role', 'is_active', 'joined_at')
    list_filter   = ('role', 'is_active')
    search_fields = ('user__email', 'user__username', 'organization__name')
    readonly_fields = ('id', 'joined_at')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'blood_type', 'risk_level', 'health_insurance', 'created_at')
    list_filter   = ('blood_type', 'risk_level')
    search_fields = ('user__email', 'user__username', 'cpf')
    readonly_fields = ('id', 'created_at', 'updated_at', 'ai_last_analysis')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'role', 'is_email_verified', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active', 'is_email_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('uid',)
    fieldsets = UserAdmin.fieldsets + (
        ('LIDDIS', {'fields': (
            'uid',
            'role',
            'phone',
            'date_of_birth',
            'bio',
            'profession',
            'professional_specialty',
            'organization',
            'is_email_verified',
            'is_phone_verified',
            'deleted_at',
        )}),
    )


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display  = ('user', 'purpose', 'is_used', 'is_expired', 'expires_at', 'created_at')
    list_filter   = ('purpose', 'is_used')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('code', 'created_at', 'expires_at')
