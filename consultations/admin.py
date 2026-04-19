from django.contrib import admin
from .models import Consultation, VitalSign, Anamnese, ExameLaboratorial, ConsultationImage


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'professional_name', 'specialty')
    list_filter = ('specialty',)
    search_fields = ('patient__username', 'professional_name', 'diagnosis')


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'blood_pressure', 'heart_rate', 'weight')


@admin.register(Anamnese)
class AnamneseAdmin(admin.ModelAdmin):
    list_display = ('consultation',)
    raw_id_fields = ('consultation',)


@admin.register(ExameLaboratorial)
class ExameLaboratorialAdmin(admin.ModelAdmin):
    list_display = ('consultation',)
    raw_id_fields = ('consultation',)


@admin.register(ConsultationImage)
class ConsultationImageAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'tab', 'caption', 'uploaded_at')
    list_filter = ('tab',)
    raw_id_fields = ('consultation',)
