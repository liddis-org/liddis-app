from django.contrib import admin
from .models import (
    Consultation, VitalSign, Anamnese, ExameLaboratorial, ConsultationImage,
    ConsultationSession, Evolution, Prescription, DiagnosisCID, PhysicalExam, LabRequest,
    PatientClinicalSummary, ClinicalIntervention, ExpectedEvolution,
)


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display   = ('patient', 'date', 'professional_name', 'specialty', 'status', 'severity', 'icd_code')
    list_filter    = ('specialty', 'status', 'severity')
    search_fields  = ('patient__email', 'patient__username', 'professional_name', 'diagnosis', 'icd_code')
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


@admin.register(Evolution)
class EvolutionAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'professional', 'category', 'is_visible_to_patient', 'created_at')
    list_filter    = ('category', 'is_visible_to_patient')
    search_fields  = ('professional__email', 'professional__username', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'professional')
    date_hierarchy = 'created_at'


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'prescriber', 'prescription_type', 'medication_name', 'is_active', 'created_at')
    list_filter    = ('prescription_type', 'is_active')
    search_fields  = ('prescriber__email', 'medication_name', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'prescriber')


@admin.register(DiagnosisCID)
class DiagnosisCIDAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'professional', 'icd_code', 'description', 'certainty', 'is_primary', 'created_at')
    list_filter    = ('certainty', 'is_primary')
    search_fields  = ('icd_code', 'description', 'professional__email')
    readonly_fields = ('id', 'created_at')
    raw_id_fields  = ('consultation', 'professional')


@admin.register(PhysicalExam)
class PhysicalExamAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'professional', 'created_at')
    search_fields  = ('professional__email', 'general_state')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'professional')


@admin.register(ClinicalIntervention)
class ClinicalInterventionAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'professional', 'created_at')
    search_fields  = ('professional__email', 'conducts', 'procedures')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'professional')
    date_hierarchy = 'created_at'


@admin.register(ExpectedEvolution)
class ExpectedEvolutionAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'professional', 'created_at')
    search_fields  = ('professional__email', 'clinical_evolution', 'therapeutic_goals')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'professional')
    date_hierarchy = 'created_at'


@admin.register(PatientClinicalSummary)
class PatientClinicalSummaryAdmin(admin.ModelAdmin):
    list_display   = ('patient', 'smokes', 'drinks', 'updated_by', 'updated_at')
    search_fields  = ('patient__email', 'patient__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('patient', 'updated_by')


@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display   = ('consultation', 'exam_type', 'requesting_professional',
                      'result_registered_by', 'status', 'urgency', 'created_at')
    list_filter    = ('status', 'urgency')
    search_fields  = ('exam_type', 'requesting_professional__email', 'result')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields  = ('consultation', 'requesting_professional', 'result_registered_by')
    date_hierarchy = 'created_at'
