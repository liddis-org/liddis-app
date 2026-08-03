"""
Management command: envia lembretes de consulta do dia.
Deve ser chamado via Cloud Scheduler às 07:00 America/Sao_Paulo.

  python manage.py send_appointment_reminders
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from appointments.models import Appointment
from appointments.emails import send_appointment_reminder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envia e-mails de lembrete para consultas agendadas hoje'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Lista os agendamentos sem enviar e-mails',
        )

    def handle(self, *args, **options):
        today    = timezone.localdate()
        dry_run  = options['dry_run']

        appointments = Appointment.objects.filter(
            scheduled_date=today,
            status__in=['scheduled', 'confirmed'],
            reminder_sent_at__isnull=True,
        ).select_related('patient', 'professional')

        count = appointments.count()
        self.stdout.write(f'Agendamentos elegíveis para lembrete: {count}')

        sent = 0
        for apt in appointments:
            if dry_run:
                self.stdout.write(f'  [dry-run] {apt.patient.email} — {apt.scheduled_time}')
                continue
            if send_appointment_reminder(apt):
                sent += 1
                self.stdout.write(f'  Lembrete enviado: {apt.patient.email} — {apt.scheduled_time}')
            else:
                self.stderr.write(f'  Falha ao enviar para: {apt.patient.email}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Lembretes enviados: {sent}/{count}'))
