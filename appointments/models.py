import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


SPECIALTY_CHOICES = [
    ('clinico_geral',   'Clínico Geral'),
    ('cardiologia',     'Cardiologia'),
    ('neurologia',      'Neurologia'),
    ('ortopedia',       'Ortopedia'),
    ('nutricao',        'Nutrição'),
    ('fisioterapia',    'Fisioterapia'),
    ('enfermagem',      'Enfermagem'),
    ('psicologia',      'Psicologia'),
    ('dermatologia',    'Dermatologia'),
    ('ginecologia',     'Ginecologia'),
    ('pediatria',       'Pediatria'),
    ('outro',           'Outro'),
]

WEEKDAY_CHOICES = [
    (0, 'Segunda-feira'),
    (1, 'Terça-feira'),
    (2, 'Quarta-feira'),
    (3, 'Quinta-feira'),
    (4, 'Sexta-feira'),
    (5, 'Sábado'),
    (6, 'Domingo'),
]


class ProfessionalAvailability(models.Model):
    """Grade horária semanal do profissional — define os slots disponíveis para agendamento."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availabilities',
        verbose_name='Profissional',
    )
    weekday               = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name='Dia da semana')
    start_time            = models.TimeField(verbose_name='Início')
    end_time              = models.TimeField(verbose_name='Fim')
    slot_duration_minutes = models.PositiveIntegerField(default=30, verbose_name='Duração do slot (min)')
    is_active             = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        db_table            = 'professional_availability'
        ordering            = ['weekday', 'start_time']
        verbose_name        = 'Disponibilidade'
        verbose_name_plural = 'Disponibilidades'
        unique_together     = [('professional', 'weekday', 'start_time')]

    def __str__(self):
        return f'{self.get_weekday_display()} {self.start_time}–{self.end_time} ({self.professional})'


class Appointment(models.Model):
    """Agendamento clínico com rastreabilidade completa."""

    class Status(models.TextChoices):
        SCHEDULED   = 'scheduled',   'Agendado'
        CONFIRMED   = 'confirmed',   'Confirmado'
        CANCELLED   = 'cancelled',   'Cancelado'
        COMPLETED   = 'completed',   'Realizado'
        NO_SHOW     = 'no_show',     'Não compareceu'
        RESCHEDULED = 'rescheduled', 'Remarcado'

    class AppointmentType(models.TextChoices):
        FIRST_VISIT = 'first_visit', 'Primeira consulta'
        FOLLOW_UP   = 'follow_up',   'Retorno'
        PROCEDURE   = 'procedure',   'Procedimento'
        EXAM        = 'exam',        'Exame'
        EMERGENCY   = 'emergency',   'Urgência'
        OTHER       = 'other',       'Outro'

    class BookedBy(models.TextChoices):
        PATIENT      = 'patient',      'Paciente'
        PROFESSIONAL = 'professional', 'Profissional'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointments_as_patient',
        verbose_name='Paciente',
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appointments_as_professional',
        verbose_name='Profissional',
    )

    scheduled_date   = models.DateField(verbose_name='Data')
    scheduled_time   = models.TimeField(verbose_name='Horário')
    duration_minutes = models.PositiveIntegerField(default=30, verbose_name='Duração (min)')

    appointment_type = models.CharField(
        max_length=15,
        choices=AppointmentType.choices,
        default=AppointmentType.FOLLOW_UP,
        verbose_name='Tipo',
    )
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, blank=True, verbose_name='Especialidade')
    status    = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
        verbose_name='Status',
    )
    location = models.CharField(max_length=200, blank=True, verbose_name='Local')
    notes    = models.TextField(blank=True, verbose_name='Observações')

    # ── Rastreabilidade (auditoria e origem) ──────────────────────────────────
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appointments_booked',
        verbose_name='Agendado por',
    )
    booked_by_role = models.CharField(
        max_length=15,
        choices=BookedBy.choices,
        verbose_name='Origem do agendamento',
    )

    # ── Cancelamento ──────────────────────────────────────────────────────────
    cancelled_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appointments_cancelled',
        verbose_name='Cancelado por',
    )
    cancelled_at        = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, verbose_name='Motivo do cancelamento')

    # ── Remarcação (cadeia de histórico) ─────────────────────────────────────
    rescheduled_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rescheduled_to',
        verbose_name='Remarcado de',
    )

    # ── Vínculo com consulta realizada ────────────────────────────────────────
    consultation = models.OneToOneField(
        'consultations.Consultation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appointment',
        verbose_name='Consulta realizada',
    )

    # ── Controle de e-mails enviados ─────────────────────────────────────────
    confirmation_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Confirmação enviada em')
    reminder_sent_at     = models.DateTimeField(null=True, blank=True, verbose_name='Lembrete enviado em')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'appointments'
        ordering            = ['scheduled_date', 'scheduled_time']
        verbose_name        = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        constraints = [
            # Previne conflito de horário: dois agendamentos ativos no mesmo slot
            models.UniqueConstraint(
                fields=['professional', 'scheduled_date', 'scheduled_time'],
                condition=models.Q(status__in=['scheduled', 'confirmed']),
                name='unique_active_appointment_slot',
            )
        ]
        indexes = [
            models.Index(fields=['patient', 'scheduled_date'],      name='appt_patient_date_idx'),
            models.Index(fields=['professional', 'scheduled_date'], name='appt_prof_date_idx'),
            models.Index(fields=['status', 'scheduled_date'],       name='appt_status_date_idx'),
            models.Index(fields=['scheduled_date'],                 name='appt_date_idx'),
        ]

    def __str__(self):
        prof = self.professional.get_full_name() if self.professional else '—'
        return f'{self.scheduled_date} {self.scheduled_time} — {self.patient} / {prof}'

    # ── Properties de negócio ─────────────────────────────────────────────────

    @property
    def is_upcoming(self):
        from datetime import datetime
        dt = datetime.combine(self.scheduled_date, self.scheduled_time)
        dt_aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        return dt_aware > timezone.now()

    @property
    def is_cancellable(self):
        return self.status in ('scheduled', 'confirmed') and self.is_upcoming

    @property
    def is_reschedulable(self):
        return self.is_cancellable

    @property
    def booked_by_label(self):
        if not self.booked_by:
            return ''
        if self.booked_by_role == self.BookedBy.PATIENT:
            return 'Agendado pelo paciente'
        name = self.booked_by.get_full_name() or self.booked_by.username
        role_label = getattr(self.booked_by, 'get_role_display', lambda: '')()
        return f'Agendado por {role_label} {name}'.strip()

    @property
    def status_color(self):
        return {
            'scheduled':   'blue',
            'confirmed':   'teal',
            'cancelled':   'red',
            'completed':   'green',
            'no_show':     'orange',
            'rescheduled': 'gray',
        }.get(self.status, 'gray')


class AppointmentHistory(models.Model):
    """Audit trail imutável de todas as alterações em agendamentos — LGPD."""

    class Action(models.TextChoices):
        CREATED     = 'created',     'Criado'
        CONFIRMED   = 'confirmed',   'Confirmado'
        CANCELLED   = 'cancelled',   'Cancelado'
        RESCHEDULED = 'rescheduled', 'Remarcado'
        COMPLETED   = 'completed',   'Marcado como realizado'
        NO_SHOW     = 'no_show',     'Não compareceu'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Agendamento',
    )
    changed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appointment_changes',
        verbose_name='Alterado por',
    )
    action          = models.CharField(max_length=15, choices=Action.choices, verbose_name='Ação')
    previous_date   = models.DateField(null=True, blank=True,  verbose_name='Data anterior')
    previous_time   = models.TimeField(null=True, blank=True,  verbose_name='Horário anterior')
    previous_status = models.CharField(max_length=15, blank=True, verbose_name='Status anterior')
    notes           = models.TextField(blank=True, verbose_name='Observações')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'appointment_history'
        ordering            = ['-created_at']
        verbose_name        = 'Histórico de Agendamento'
        verbose_name_plural = 'Histórico de Agendamentos'

    def __str__(self):
        return f'{self.get_action_display()} — {self.appointment}'
