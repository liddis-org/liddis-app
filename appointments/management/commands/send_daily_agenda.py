"""
Management command: envia resumo diário da agenda para cada profissional.
Deve ser chamado via Cloud Scheduler às 06:30 America/Sao_Paulo.

  python manage.py send_daily_agenda
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from appointments.models import Appointment
from appointments.emails import send_daily_agenda_digest

User = get_user_model()

PROFESSIONAL_ROLES = {
    'ADMIN', 'DOCTOR', 'NURSE', 'PHYSIO', 'NUTRITIONIST', 'BIOMEDICO',
    'SPEECH_THERAPIST', 'PHYSICAL_EDUCATOR', 'PSYCHOLOGIST', 'DENTIST',
    'OCC_THERAPIST', 'PHARMACIST',
}


class Command(BaseCommand):
    help = 'Envia resumo diário da agenda para profissionais com consultas hoje'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Lista os profissionais sem enviar e-mails',
        )

    def handle(self, *args, **options):
        today   = timezone.localdate()
        dry_run = options['dry_run']

        professionals = User.objects.filter(
            role__in=PROFESSIONAL_ROLES,
            is_active=True,
            appointments_as_professional__scheduled_date=today,
            appointments_as_professional__status__in=['scheduled', 'confirmed'],
        ).distinct()

        sent = 0
        for prof in professionals:
            appointments = list(
                Appointment.objects.filter(
                    professional=prof,
                    scheduled_date=today,
                    status__in=['scheduled', 'confirmed'],
                ).select_related('patient').order_by('scheduled_time')
            )

            if dry_run:
                self.stdout.write(f'  [dry-run] {prof.email} — {len(appointments)} consulta(s)')
                continue

            if send_daily_agenda_digest(prof, appointments):
                sent += 1
                self.stdout.write(f'  Agenda enviada: {prof.email} ({len(appointments)} consulta(s))')
            else:
                self.stderr.write(f'  Falha: {prof.email}')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Digestos enviados: {sent}'))
