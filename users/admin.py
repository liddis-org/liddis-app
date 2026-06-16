from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, VerificationCode, Organization, OrganizationMember,
    PatientProfile, PatientProfessionalAccess, AuditLog, PlatformFeedback,
)


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
    list_display  = ('username', 'email', 'role', 'is_email_verified', 'is_active', 'date_joined', 'last_login')
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


@admin.register(PatientProfessionalAccess)
class PatientProfessionalAccessAdmin(admin.ModelAdmin):
    list_display   = ('professional', 'patient', 'is_active', 'granted_at', 'revoked_at')
    list_filter    = ('is_active',)
    search_fields  = (
        'professional__email', 'professional__username',
        'patient__email', 'patient__username',
    )
    readonly_fields = ('id', 'granted_at', 'revoked_at')
    actions         = ['revoke_access']

    @admin.action(description='Revogar vínculo selecionado')
    def revoke_access(self, request, queryset):
        for obj in queryset.filter(is_active=True):
            obj.revoke()
        self.message_user(request, f'{queryset.count()} vínculo(s) revogado(s).')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display   = ('timestamp', 'actor', 'action', 'resource_type', 'resource_id', 'patient', 'success', 'ip_address')
    list_filter    = ('action', 'success', 'resource_type')
    search_fields  = (
        'actor__email', 'actor__username',
        'patient__email', 'patient__username',
        'resource_type', 'resource_id', 'ip_address',
    )
    readonly_fields = (
        'id', 'actor', 'action', 'resource_type', 'resource_id',
        'patient', 'ip_address', 'user_agent', 'success', 'detail', 'timestamp',
    )
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PlatformFeedback)
class PlatformFeedbackAdmin(admin.ModelAdmin):
    list_display   = ('user', 'role_at_time', 'score_usability', 'score_performance', 'score_care_quality', 'created_at')
    list_filter    = ('role_at_time',)
    search_fields  = ('user__email', 'user__username')
    readonly_fields = ('id', 'created_at')
    raw_id_fields  = ('user',)
    date_hierarchy = 'created_at'
