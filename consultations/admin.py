from django.contrib import admin
from .models import Consultation, VitalSign


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'professional_name', 'specialty')
    list_filter = ('specialty',)
    search_fields = ('patient__username', 'professional_name', 'diagnosis')


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date', 'blood_pressure', 'heart_rate', 'weight')
