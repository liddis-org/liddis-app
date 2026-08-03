from django.contrib import admin
from .models import Appointment, AppointmentHistory, ProfessionalAvailability


@admin.register(ProfessionalAvailability)
class ProfessionalAvailabilityAdmin(admin.ModelAdmin):
    list_display   = ('professional', 'get_weekday', 'start_time', 'end_time', 'slot_duration_minutes', 'is_active')
    list_filter    = ('weekday', 'is_active')
    search_fields  = ('professional__email', 'professional__first_name', 'professional__last_name')
    readonly_fields = ('id',)
    autocomplete_fields = ['professional']

    @admin.display(description='Dia')
    def get_weekday(self, obj):
        return obj.get_weekday_display()


class AppointmentHistoryInline(admin.TabularInline):
    model          = AppointmentHistory
    extra          = 0
    readonly_fields = ('id', 'changed_by', 'action', 'previous_date', 'previous_time', 'previous_status', 'notes', 'created_at')
    can_delete     = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display   = ('scheduled_date', 'scheduled_time', 'patient', 'professional', 'appointment_type', 'status', 'booked_by_role', 'created_at')
    list_filter    = ('status', 'appointment_type', 'specialty', 'booked_by_role', 'scheduled_date')
    search_fields  = (
        'patient__email', 'patient__first_name', 'patient__last_name',
        'professional__email', 'professional__first_name', 'professional__last_name',
    )
    readonly_fields = ('id', 'created_at', 'updated_at', 'confirmation_sent_at', 'reminder_sent_at')
    date_hierarchy = 'scheduled_date'
    inlines        = [AppointmentHistoryInline]
    autocomplete_fields = ['patient', 'professional', 'booked_by', 'cancelled_by']

    fieldsets = (
        ('Agendamento', {'fields': (
            'id', 'patient', 'professional', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'appointment_type', 'specialty', 'status', 'location', 'notes',
        )}),
        ('Rastreabilidade', {'fields': ('booked_by', 'booked_by_role', 'rescheduled_from', 'consultation')}),
        ('Cancelamento', {'fields': ('cancelled_by', 'cancelled_at', 'cancellation_reason')}),
        ('E-mails', {'fields': ('confirmation_sent_at', 'reminder_sent_at')}),
        ('Datas', {'fields': ('created_at', 'updated_at')}),
    )

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AppointmentHistory)
class AppointmentHistoryAdmin(admin.ModelAdmin):
    list_display   = ('created_at', 'appointment', 'changed_by', 'action', 'previous_status')
    list_filter    = ('action',)
    search_fields  = ('appointment__patient__email', 'changed_by__email')
    readonly_fields = ('id', 'appointment', 'changed_by', 'action', 'previous_date', 'previous_time', 'previous_status', 'notes', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
