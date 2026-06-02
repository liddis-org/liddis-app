import os
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.validators import FileExtensionValidator

ALLOWED_ATTACHMENT_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'pdf']


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

    class RecordOrigin(models.TextChoices):
        PLATFORM       = 'platform',        'Consulta realizada na plataforma'
        PATIENT_MANUAL = 'patient_manual',  'Consulta cadastrada pelo paciente'

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

    # Origem do registro — rastreabilidade e auditoria
    record_origin = models.CharField(
        max_length=20,
        choices=RecordOrigin.choices,
        default=RecordOrigin.PLATFORM,
        verbose_name='Origem do Registro',
        db_index=True,
    )

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

    @property
    def is_patient_record(self):
        return self.record_origin == self.RecordOrigin.PATIENT_MANUAL


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
    """Anexos (imagens e PDFs) de uma consulta, organizados por aba."""
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
    image = models.FileField(
        upload_to=consultation_image_path,
        verbose_name='Arquivo',
        validators=[FileExtensionValidator(ALLOWED_ATTACHMENT_EXTENSIONS)],
    )
    caption = models.CharField(max_length=255, blank=True, verbose_name='Legenda')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'consultation_images'
        ordering            = ['-uploaded_at']
        verbose_name        = 'Anexo da Consulta'
        verbose_name_plural = 'Anexos das Consultas'

    def __str__(self):
        return f'Anexo [{self.get_tab_display()}] — Consulta #{self.consultation_id}'

    @property
    def is_pdf(self):
        name = self.image.name or ''
        return name.lower().endswith('.pdf')

    @property
    def filename(self):
        return os.path.basename(self.image.name) if self.image.name else 'arquivo'


class VitalSign(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vitals'
    )
    # Vínculo opcional com consulta — preenchido quando profissional registra durante atendimento
    consultation = models.ForeignKey(
        'Consultation',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vitals',
        verbose_name='Consulta',
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vitals_recorded',
        verbose_name='Registrado por',
    )
    date = models.DateField(verbose_name='Data da medição')
    blood_pressure = models.CharField(max_length=20, blank=True, verbose_name='Pressão arterial (ex: 120/80)')
    heart_rate = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frequência cardíaca (bpm)')
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frequência respiratória (irpm)')
    weight = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    height = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Altura (cm)')
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Temperatura (°C)')
    oxygen_saturation = models.PositiveIntegerField(null=True, blank=True, verbose_name='Saturação O₂ (%)')
    glucose = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Glicemia (mg/dL)')
    notes       = models.CharField(max_length=255, blank=True, verbose_name='Observações')
    other_signs = models.TextField(blank=True, verbose_name='Outros Sinais')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'vital_signs'
        ordering            = ['-date', '-created_at']
        verbose_name        = 'Sinal Vital'
        verbose_name_plural = 'Sinais Vitais'
        indexes = [
            models.Index(fields=['patient', 'date']),
            models.Index(fields=['consultation']),
        ]

    @property
    def bmi(self):
        if self.weight and self.height and self.height > 0:
            h_m = float(self.height) / 100
            return round(float(self.weight) / (h_m ** 2), 1)
        return None

    def __str__(self):
        return f'{self.date} — {self.patient.username}'


class Evolution(models.Model):
    """
    Evolução multiprofissional.
    Cada profissional escreve a sua própria evolução vinculada à consulta.
    A visibilidade entre categorias é controlada em nível de permissão.
    """
    CATEGORY_MEDICAL      = 'medical'
    CATEGORY_NURSING      = 'nursing'
    CATEGORY_PHYSIO       = 'physio'
    CATEGORY_NUTRITION    = 'nutrition'
    CATEGORY_SPEECH       = 'speech'
    CATEGORY_PSYCHOLOGY   = 'psychology'
    CATEGORY_OCCUPATIONAL = 'occupational'
    CATEGORY_DENTAL       = 'dental'
    CATEGORY_PHARMACY     = 'pharmacy'
    CATEGORY_PHYSICAL_ED  = 'physical_ed'
    CATEGORY_OTHER        = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_MEDICAL,      'Médica'),
        (CATEGORY_NURSING,      'Enfermagem'),
        (CATEGORY_PHYSIO,       'Fisioterapia'),
        (CATEGORY_NUTRITION,    'Nutrição'),
        (CATEGORY_SPEECH,       'Fonoaudiologia'),
        (CATEGORY_PSYCHOLOGY,   'Psicologia'),
        (CATEGORY_OCCUPATIONAL, 'Terapia Ocupacional'),
        (CATEGORY_DENTAL,       'Odontologia'),
        (CATEGORY_PHARMACY,     'Farmácia'),
        (CATEGORY_PHYSICAL_ED,  'Educação Física'),
        (CATEGORY_OTHER,        'Outro'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='evolutions')
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='evolutions_written',
        verbose_name='Profissional',
    )
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Categoria')
    content      = models.TextField(verbose_name='Conteúdo da evolução')
    is_visible_to_patient = models.BooleanField(default=True, verbose_name='Visível ao paciente')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'evolutions'
        ordering            = ['-created_at']
        verbose_name        = 'Evolução'
        verbose_name_plural = 'Evoluções'
        indexes = [
            models.Index(fields=['consultation', 'category']),
            models.Index(fields=['professional']),
        ]

    def __str__(self):
        return f'Evolução {self.get_category_display()} — {self.consultation}'


class Prescription(models.Model):
    """Prescrição formal (médica, odontológica, nutricional ou de enfermagem)."""
    TYPE_MEDICAL    = 'medical'
    TYPE_NURSING    = 'nursing'
    TYPE_DENTAL     = 'dental'
    TYPE_DIETARY    = 'dietary'
    TYPE_PHARMACY   = 'pharmacy'

    TYPE_CHOICES = [
        (TYPE_MEDICAL,  'Médica'),
        (TYPE_NURSING,  'Enfermagem'),
        (TYPE_DENTAL,   'Odontológica'),
        (TYPE_DIETARY,  'Dietética'),
        (TYPE_PHARMACY, 'Farmacêutica'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation    = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='prescriptions')
    prescriber      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='prescriptions_written',
        verbose_name='Prescritor',
    )
    prescription_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name='Tipo')
    medication_name   = models.CharField(max_length=200, blank=True, verbose_name='Medicamento / Item')
    dosage            = models.CharField(max_length=100, blank=True, verbose_name='Dose')
    frequency         = models.CharField(max_length=100, blank=True, verbose_name='Frequência')
    duration          = models.CharField(max_length=100, blank=True, verbose_name='Duração')
    route             = models.CharField(max_length=50, blank=True, verbose_name='Via de administração')
    content           = models.TextField(blank=True, verbose_name='Prescrição completa')
    is_active         = models.BooleanField(default=True, verbose_name='Ativa')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'prescriptions'
        ordering            = ['-created_at']
        verbose_name        = 'Prescrição'
        verbose_name_plural = 'Prescrições'
        indexes = [
            models.Index(fields=['consultation', 'is_active']),
            models.Index(fields=['prescriber']),
            models.Index(fields=['prescription_type']),
        ]

    def __str__(self):
        return f'Prescrição {self.get_prescription_type_display()} — {self.medication_name or "sem medicamento"}'


class DiagnosisCID(models.Model):
    """Diagnóstico estruturado com código CID-10."""
    CERTAINTY_CONFIRMED = 'confirmed'
    CERTAINTY_PRESUMED  = 'presumed'
    CERTAINTY_RULED_OUT = 'ruled_out'

    CERTAINTY_CHOICES = [
        (CERTAINTY_CONFIRMED, 'Confirmado'),
        (CERTAINTY_PRESUMED,  'Presumido'),
        (CERTAINTY_RULED_OUT, 'Descartado'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='diagnoses')
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='diagnoses_written',
        verbose_name='Profissional',
    )
    icd_code     = models.CharField(max_length=10, verbose_name='Código CID-10')
    description  = models.CharField(max_length=300, blank=True, verbose_name='Descrição')
    notes        = models.TextField(blank=True, verbose_name='Observações clínicas')
    is_primary   = models.BooleanField(default=False, verbose_name='Diagnóstico principal')
    certainty    = models.CharField(max_length=10, choices=CERTAINTY_CHOICES, default=CERTAINTY_CONFIRMED, verbose_name='Certeza')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'diagnoses_cid'
        ordering            = ['-created_at', '-is_primary']
        verbose_name        = 'Diagnóstico CID'
        verbose_name_plural = 'Diagnósticos CID'
        indexes = [
            models.Index(fields=['consultation']),
            models.Index(fields=['icd_code']),
        ]

    def __str__(self):
        return f'{self.icd_code} — {self.description or "sem descrição"} ({self.get_certainty_display()})'


class PhysicalExam(models.Model):
    """Exame físico segmentado por sistemas corporais."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='physical_exams')
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='physical_exams_written',
        verbose_name='Profissional',
    )
    general_state     = models.TextField(blank=True, verbose_name='Estado geral')
    cardiovascular    = models.TextField(blank=True, verbose_name='Cardiovascular')
    respiratory       = models.TextField(blank=True, verbose_name='Respiratório')
    abdomen           = models.TextField(blank=True, verbose_name='Abdome')
    neurological      = models.TextField(blank=True, verbose_name='Neurológico')
    musculoskeletal   = models.TextField(blank=True, verbose_name='Musculoesquelético')
    skin              = models.TextField(blank=True, verbose_name='Pele e mucosas')
    orl               = models.TextField(blank=True, verbose_name='ORL / Cabeça e pescoço')
    other_systems     = models.TextField(blank=True, verbose_name='Outros sistemas')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'physical_exams'
        ordering            = ['-created_at']
        verbose_name        = 'Exame Físico'
        verbose_name_plural = 'Exames Físicos'

    def __str__(self):
        return f'Exame Físico — {self.consultation}'


class LabRequest(models.Model):
    """
    Solicitação de exame laboratorial.
    Médico cria a solicitação; Biomédico/profissional de lab. registra o resultado.
    """
    STATUS_PENDING   = 'pending'
    STATUS_COLLECTED = 'collected'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pendente'),
        (STATUS_COLLECTED, 'Coletado'),
        (STATUS_COMPLETED, 'Resultado disponível'),
        (STATUS_CANCELLED, 'Cancelado'),
    ]

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation          = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='lab_requests')
    requesting_professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='lab_requests_created',
        verbose_name='Solicitante',
    )
    result_registered_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lab_results_entered',
        verbose_name='Quem registrou o resultado',
    )
    exam_type        = models.CharField(max_length=100, verbose_name='Tipo de exame')
    exam_description = models.TextField(blank=True, verbose_name='Descrição / parâmetros')
    urgency          = models.BooleanField(default=False, verbose_name='Urgência')
    result           = models.TextField(blank=True, verbose_name='Resultado')
    result_date      = models.DateField(null=True, blank=True, verbose_name='Data do resultado')
    reference_values = models.TextField(blank=True, verbose_name='Valores de referência')
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='Status')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'lab_requests'
        ordering            = ['-created_at']
        verbose_name        = 'Solicitação de Exame'
        verbose_name_plural = 'Solicitações de Exame'
        indexes = [
            models.Index(fields=['consultation', 'status']),
            models.Index(fields=['requesting_professional']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.exam_type} — {self.get_status_display()}'


class PatientClinicalSummary(models.Model):
    """
    Perfil clínico permanente do paciente — atualizado pelos profissionais durante consultas.
    Diferente da Anamnese (snapshot de cada consulta), este modelo armazena dados
    persistentes de saúde do paciente: alergias, comorbidades e hábitos de vida.
    """
    SMOKE_NO      = 'no'
    SMOKE_YES     = 'yes'
    SMOKE_FORMER  = 'former'
    SMOKE_CHOICES = [
        (SMOKE_NO,     'Não'),
        (SMOKE_YES,    'Sim'),
        (SMOKE_FORMER, 'Ex-fumante'),
    ]

    DRINK_NO           = 'no'
    DRINK_YES          = 'yes'
    DRINK_OCCASIONALLY = 'occasionally'
    DRINK_CHOICES = [
        (DRINK_NO,           'Não'),
        (DRINK_YES,          'Sim'),
        (DRINK_OCCASIONALLY, 'Ocasionalmente'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clinical_summary',
        verbose_name='Paciente',
    )
    allergies              = models.TextField(blank=True, verbose_name='Alergias conhecidas')
    continuous_medications = models.TextField(blank=True, verbose_name='Medicamentos de uso contínuo')
    comorbidities          = models.TextField(blank=True, verbose_name='Comorbidades / Condições crônicas')
    smokes                 = models.CharField(max_length=10, choices=SMOKE_CHOICES, blank=True, verbose_name='Tabagismo')
    drinks                 = models.CharField(max_length=15, choices=DRINK_CHOICES, blank=True, verbose_name='Etilismo')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clinical_summaries_updated',
        verbose_name='Última atualização por',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'patient_clinical_summaries'
        verbose_name        = 'Perfil Clínico do Paciente'
        verbose_name_plural = 'Perfis Clínicos dos Pacientes'
        indexes = [
            models.Index(fields=['updated_at'], name='clinical_updated_at_idx'),
            models.Index(fields=['smokes', 'drinks'], name='clinical_habits_idx'),
        ]

    def __str__(self):
        return f'Perfil Clínico — {self.patient.display_name}'


class ClinicalIntervention(models.Model):
    """
    Intervenção clínica registrada pelo profissional durante a consulta.
    Registra condutas, procedimentos, orientações e ações executadas.
    Preparado para uso em pipelines de IA (sumarização, análise de padrões).
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name='clinical_interventions',
        verbose_name='Consulta',
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='interventions_written',
        verbose_name='Profissional',
    )
    professional_diagnosis = models.TextField(blank=True, verbose_name='Diagnóstico clínico do profissional')
    classification_code    = models.CharField(max_length=50, blank=True, verbose_name='Código de classificação (NANDA, CID-10, DSM…)')
    related_factors        = models.TextField(blank=True, verbose_name='Fatores relacionados / etiologia')
    conducts               = models.TextField(blank=True, verbose_name='Condutas clínicas (uma por linha)')
    procedures             = models.TextField(blank=True, verbose_name='Procedimentos realizados')
    guidelines             = models.TextField(blank=True, verbose_name='Orientações ao paciente')
    clinical_actions       = models.TextField(blank=True, verbose_name='Outras ações clínicas')
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    @property
    def conducts_list(self):
        return [c.strip() for c in self.conducts.split('\n') if c.strip()]

    @property
    def conducts_count(self):
        return len(self.conducts_list)

    class Meta:
        db_table            = 'clinical_interventions'
        ordering            = ['-created_at']
        verbose_name        = 'Intervenção Clínica'
        verbose_name_plural = 'Intervenções Clínicas'
        indexes = [
            models.Index(fields=['consultation'], name='intervention_consultation_idx'),
            models.Index(fields=['professional'], name='intervention_professional_idx'),
            models.Index(fields=['created_at'],   name='intervention_created_at_idx'),
        ]

    def __str__(self):
        return f'Intervenção — {self.consultation}'


class ExpectedEvolution(models.Model):
    """
    Evolução clínica esperada — prognóstico, metas terapêuticas e plano de acompanhamento.
    Estruturado para análise longitudinal por IA: cruzamento de meta vs. evolução real.
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name='expected_evolutions',
        verbose_name='Consulta',
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expected_evolutions_written',
        verbose_name='Profissional',
    )
    PRIORITY_HIGH   = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW    = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH,   'Alta'),
        (PRIORITY_MEDIUM, 'Média'),
        (PRIORITY_LOW,    'Baixa'),
    ]

    estimated_timeframe  = models.CharField(max_length=100, blank=True, verbose_name='Prazo estimado')
    priority             = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True, verbose_name='Prioridade')
    clinical_evolution   = models.TextField(blank=True, verbose_name='Resultados esperados')
    therapeutic_goals    = models.TextField(blank=True, verbose_name='Metas terapêuticas')
    follow_up_plan       = models.TextField(blank=True, verbose_name='Plano de acompanhamento')
    treatment_response   = models.TextField(blank=True, verbose_name='Resposta esperada ao tratamento')
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'expected_evolutions'
        ordering            = ['-created_at']
        verbose_name        = 'Evolução Esperada'
        verbose_name_plural = 'Evoluções Esperadas'
        indexes = [
            models.Index(fields=['consultation'], name='exp_evolution_consultation_idx'),
            models.Index(fields=['professional'], name='exp_evolution_professional_idx'),
            models.Index(fields=['created_at'],   name='exp_evolution_created_at_idx'),
        ]

    def __str__(self):
        return f'Evolução Esperada — {self.consultation}'


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
