from django.contrib import admin
from .models import Consultation, VitalSign, Anamnese, ExameLaboratorial, ConsultationImage, ConsultationSession


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display  = ('patient', 'date', 'professional_name', 'specialty', 'status', 'severity', 'icd_code')
    list_filter   = ('specialty', 'status', 'severity')
    search_fields = ('patient__email', 'patient__username', 'professional_name', 'diagnosis', 'icd_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'ai_last_analysis')
    date_hierarchy = 'date'


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display  = ('patient', 'date', 'blood_pressure', 'heart_rate', 'weight', 'oxygen_saturation')
    search_fields = ('patient__email', 'patient__username')
    date_hierarchy = 'date'


@admin.register(Anamnese)
class AnamneseAdmin(admin.ModelAdmin):
    list_display  = ('consultation',)
    raw_id_fields = ('consultation',)


@admin.register(ExameLaboratorial)
class ExameLaboratorialAdmin(admin.ModelAdmin):
    list_display  = ('consultation',)
    raw_id_fields = ('consultation',)


@admin.register(ConsultationImage)
class ConsultationImageAdmin(admin.ModelAdmin):
    list_display  = ('consultation', 'tab', 'caption', 'uploaded_at')
    list_filter   = ('tab',)
    raw_id_fields = ('consultation',)


@admin.register(ConsultationSession)
class ConsultationSessionAdmin(admin.ModelAdmin):
    list_display  = ('patient', 'professional', 'status', 'expires_at', 'created_at')
    list_filter   = ('status',)
    search_fields = ('patient__email', 'patient__username')
    readonly_fields = ('token', 'created_at', 'closed_at')
