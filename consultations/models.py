import os
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


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


class Consultation(models.Model):
    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Rascunho'
        ACTIVE    = 'active',    'Ativa'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    class Severity(models.TextChoices):
        LOW      = 'low',      'Leve'
        MODERATE = 'moderate', 'Moderada'
        HIGH     = 'high',     'Grave'
        CRITICAL = 'critical', 'Crítica'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultations',
        verbose_name='Paciente',
    )
    organization = models.ForeignKey(
        'users.Organization',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='consultations',
        verbose_name='Organização',
    )

    date = models.DateField(verbose_name='Data da consulta')
    professional_name   = models.CharField(max_length=150, verbose_name='Nome do profissional')
    profession          = models.CharField(max_length=100, blank=True, verbose_name='Profissão do profissional')
    clinic_name         = models.CharField(max_length=200, blank=True, verbose_name='Nome do local')
    clinic_neighborhood = models.CharField(max_length=100, blank=True, verbose_name='Bairro')
    clinic_city         = models.CharField(max_length=100, blank=True, verbose_name='Cidade')
    clinic_address      = models.CharField(max_length=300, blank=True, verbose_name='Endereço completo')
    specialty       = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, verbose_name='Especialidade')
    specialty_other = models.CharField(max_length=100, blank=True, verbose_name='Especialidade (Outro)')
    diagnosis    = models.TextField(blank=True, verbose_name='Diagnóstico')
    notes        = models.TextField(blank=True, verbose_name='Anotações / Evolução')
    prescription = models.TextField(blank=True, verbose_name='Prescrição / Medicamentos')

    # Status e triagem
    status   = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, verbose_name='Status')
    severity = models.CharField(max_length=10, choices=Severity.choices, blank=True, verbose_name='Gravidade')

    # Codificação clínica (CID-10)
    icd_code = models.CharField(max_length=10, blank=True, verbose_name='CID-10')

    # Campos semânticos para IA
    ai_summary      = models.TextField(blank=True, verbose_name='Resumo gerado por IA')
    ai_last_analysis = models.DateTimeField(null=True, blank=True, verbose_name='Última análise IA')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'consultations'
        ordering            = ['-date']
        verbose_name        = 'Consulta'
        verbose_name_plural = 'Consultas'
        indexes = [
            models.Index(fields=['patient', 'date']),
            models.Index(fields=['organization']),
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
            models.Index(fields=['icd_code']),
        ]

    def __str__(self):
        return f'{self.date} — {self.professional_name} ({self.get_specialty_display()})'

    @property
    def specialty_label(self):
        if self.specialty == 'outro' and self.specialty_other:
            return self.specialty_other
        return self.get_specialty_display()


class Anamnese(models.Model):
    """Anamnese vinculada a uma consulta (relação 1-para-1)."""
    consultation = models.OneToOneField(
        Consultation,
        on_delete=models.CASCADE,
        related_name='anamnese'
    )
    chief_complaint = models.TextField(blank=True, verbose_name='Queixa principal')
    history = models.TextField(blank=True, verbose_name='História da doença atual')
    past_history = models.TextField(blank=True, verbose_name='Antecedentes pessoais')
    family_history = models.TextField(blank=True, verbose_name='Antecedentes familiares')
    medications = models.TextField(blank=True, verbose_name='Medicamentos em uso')
    allergies = models.TextField(blank=True, verbose_name='Alergias')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'anamneses'
        verbose_name        = 'Anamnese'
        verbose_name_plural = 'Anamneses'

    def __str__(self):
        return f'Anamnese — {self.consultation}'


class ExameLaboratorial(models.Model):
    """Exames laboratoriais vinculados a uma consulta (relação 1-para-1)."""
    consultation = models.OneToOneField(
        Consultation,
        on_delete=models.CASCADE,
        related_name='exames'
    )
    hemograma = models.TextField(blank=True, verbose_name='Hemograma')
    glicemia = models.TextField(blank=True, verbose_name='Glicemia')
    colesterol = models.TextField(blank=True, verbose_name='Colesterol e triglicerídeos')
    funcao_renal = models.TextField(blank=True, verbose_name='Função renal (creatinina, ureia)')
    funcao_hepatica = models.TextField(blank=True, verbose_name='Função hepática')
    hormonal = models.TextField(blank=True, verbose_name='Exames hormonais')
    urina = models.TextField(blank=True, verbose_name='Urina (EAS)')
    outros = models.TextField(blank=True, verbose_name='Outros exames')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'exames_laboratoriais'
        verbose_name        = 'Exame Laboratorial'
        verbose_name_plural = 'Exames Laboratoriais'

    def __str__(self):
        return f'Exames — {self.consultation}'


def consultation_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    new_name = f'{uuid.uuid4().hex}{ext}'
    return f'consultations/{instance.consultation.patient_id}/{instance.consultation_id}/{instance.tab}/{new_name}'


class ConsultationImage(models.Model):
    """Imagens anexadas a uma consulta, organizadas por aba."""
    TAB_CHOICES = [
        ('anamnese',   'Anamnese'),
        ('exames',     'Exames Laboratoriais'),
        ('diagnostico','Diagnóstico'),
        ('prescricao', 'Prescrição'),
    ]

    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name='images'
    )
    tab = models.CharField(max_length=20, choices=TAB_CHOICES, verbose_name='Aba')
    image = models.ImageField(upload_to=consultation_image_path, verbose_name='Imagem')
    caption = models.CharField(max_length=255, blank=True, verbose_name='Legenda')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'consultation_images'
        ordering            = ['-uploaded_at']
        verbose_name        = 'Imagem da Consulta'
        verbose_name_plural = 'Imagens das Consultas'

    def __str__(self):
        return f'Imagem [{self.get_tab_display()}] — Consulta #{self.consultation_id}'


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
        db_table            = 'vital_signs'
        ordering            = ['-date']
        verbose_name        = 'Sinal Vital'
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
        db_table            = 'consultation_sessions'
        ordering            = ['-created_at']
        verbose_name        = 'Sessão de Atendimento'
        verbose_name_plural = 'Sessões de Atendimento'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=24)
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
