"""
Funções de e-mail para o módulo de agendamentos.
Compatível com o sistema multi-provider existente (EMAIL_PROVIDER env var).
"""
import logging
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@liddis.com.br')


def send_appointment_confirmation(appointment):
    """Envia e-mail de confirmação ao paciente após agendamento."""
    try:
        patient = appointment.patient
        if not patient.email:
            return False

        subject = f'Consulta agendada — {appointment.scheduled_date.strftime("%d/%m/%Y")} às {appointment.scheduled_time.strftime("%H:%M")}'
        context = {'appointment': appointment}
        html_body = render_to_string('emails/appointment_confirmation.html', context)
        text_body = render_to_string('emails/appointment_confirmation.txt', context)

        send_mail(
            subject     = subject,
            message     = text_body,
            from_email  = _get_from_email(),
            recipient_list = [patient.email],
            html_message   = html_body,
            fail_silently  = False,
        )
        appointment.confirmation_sent_at = timezone.now()
        appointment.save(update_fields=['confirmation_sent_at'])
        logger.info('Confirmation email sent for appointment %s', appointment.pk)
        return True
    except Exception:
        logger.exception('Failed to send confirmation email for appointment %s', appointment.pk)
        return False


def send_appointment_reminder(appointment):
    """Envia lembrete ao paciente no dia da consulta."""
    try:
        patient = appointment.patient
        if not patient.email:
            return False

        subject = f'Lembrete: consulta hoje às {appointment.scheduled_time.strftime("%H:%M")}'
        context = {'appointment': appointment}
        html_body = render_to_string('emails/appointment_reminder.html', context)
        text_body = render_to_string('emails/appointment_reminder.txt', context)

        send_mail(
            subject        = subject,
            message        = text_body,
            from_email     = _get_from_email(),
            recipient_list = [patient.email],
            html_message   = html_body,
            fail_silently  = False,
        )
        appointment.reminder_sent_at = timezone.now()
        appointment.save(update_fields=['reminder_sent_at'])
        logger.info('Reminder email sent for appointment %s', appointment.pk)
        return True
    except Exception:
        logger.exception('Failed to send reminder email for appointment %s', appointment.pk)
        return False


def send_daily_agenda_digest(professional, appointments):
    """Envia o resumo diário da agenda ao profissional."""
    try:
        if not professional.email or not appointments:
            return False

        date = appointments[0].scheduled_date if appointments else timezone.localdate()
        subject = f'Sua agenda de hoje — {date.strftime("%d/%m/%Y")} ({len(appointments)} consulta(s))'
        context = {'professional': professional, 'appointments': appointments, 'date': date}
        html_body = render_to_string('emails/daily_agenda.html', context)
        text_body = render_to_string('emails/daily_agenda.txt', context)

        send_mail(
            subject        = subject,
            message        = text_body,
            from_email     = _get_from_email(),
            recipient_list = [professional.email],
            html_message   = html_body,
            fail_silently  = False,
        )
        logger.info('Daily agenda digest sent to professional %s (%d appointments)', professional.pk, len(appointments))
        return True
    except Exception:
        logger.exception('Failed to send daily agenda digest to professional %s', professional.pk)
        return False
