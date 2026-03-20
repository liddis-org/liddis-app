import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Consultation(models.Model):
    SPECIALTY_CHOICES = [
        ('clinico_geral', 'Clínico Geral'),
        ('cardiologia', 'Cardiologia'),
        ('neurologia', 'Neurologia'),
        ('ortopedia', 'Ortopedia'),
        ('nutricao', 'Nutrição'),
        ('fisioterapia', 'Fisioterapia'),
        ('enfermagem', 'Enfermagem'),
        ('psicologia', 'Psicologia'),
        ('dermatologia', 'Dermatologia'),
        ('ginecologia', 'Ginecologia'),
        ('pediatria', 'Pediatria'),
        ('outro', 'Outro'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultations'
    )
    date = models.DateField(verbose_name='Data da consulta')
    professional_name = models.CharField(max_length=150, verbose_name='Nome do profissional')
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, verbose_name='Especialidade')
    diagnosis = models.TextField(blank=True, verbose_name='Diagnóstico')
    notes = models.TextField(blank=True, verbose_name='Anotações / Evolução')
    prescription = models.TextField(blank=True, verbose_name='Prescrição / Medicamentos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Consulta'
        verbose_name_plural = 'Consultas'

    def __str__(self):
        return f'{self.date} — {self.professional_name} ({self.get_specialty_display()})'


class VitalSign(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vitals'
    )
    date = models.DateField(verbose_name='Data da medição')
    blood_pressure = models.CharField(max_length=20, blank=True, verbose_name='Pressão arterial (ex: 120/80)')
    heart_rate = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frequência cardíaca (bpm)')
    weight = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Temperatura (°C)')
    oxygen_saturation = models.PositiveIntegerField(null=True, blank=True, verbose_name='Saturação O₂ (%)')
    notes = models.CharField(max_length=255, blank=True, verbose_name='Observações')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Sinal Vital'
        verbose_name_plural = 'Sinais Vitais'

    def __str__(self):
        return f'{self.date} — {self.patient.username}'


class ConsultationSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Aguardando profissional'),
        ('active', 'Em atendimento'),
        ('closed', 'Encerrado'),
        ('expired', 'Expirado'),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_sessions'
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='professional_sessions'
    )
    consultation = models.OneToOneField(
        Consultation,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='session'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sessão de Atendimento'
        verbose_name_plural = 'Sessões de Atendimento'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=2)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.status == 'pending' and not self.is_expired

    @property
    def token_display(self):
        return str(self.token).upper()[:8]

    def __str__(self):
        return f'Sessão {self.token_display} — {self.patient.username} ({self.get_status_display()})'
