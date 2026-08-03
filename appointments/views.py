import json
import logging
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from users.permissions import has_permission
from .emails import send_appointment_confirmation, send_daily_agenda_digest
from .forms import (
    AppointmentCancelForm,
    AppointmentCreateForm,
    AppointmentRescheduleForm,
    ProfessionalAvailabilityForm,
)
from .models import Appointment, AppointmentHistory, ProfessionalAvailability

logger = logging.getLogger(__name__)
User = get_user_model()

PROFESSIONAL_ROLES = {
    'ADMIN', 'DOCTOR', 'NURSE', 'PHYSIO', 'NUTRITIONIST', 'BIOMEDICO',
    'SPEECH_THERAPIST', 'PHYSICAL_EDUCATOR', 'PSYCHOLOGIST', 'DENTIST',
    'OCC_THERAPIST', 'PHARMACIST',
}


def _is_professional(user):
    return user.role != 'PATIENT'


def _record_history(appointment, changed_by, action, previous_date=None, previous_time=None, previous_status=None, notes=''):
    AppointmentHistory.objects.create(
        appointment     = appointment,
        changed_by      = changed_by,
        action          = action,
        previous_date   = previous_date,
        previous_time   = previous_time,
        previous_status = previous_status or '',
        notes           = notes,
    )


# ── Lista de agendamentos (paciente) ─────────────────────────────────────────

class PatientAppointmentListView(LoginRequiredMixin, ListView):
    template_name  = 'appointments/patient_list.html'
    context_object_name = 'appointments'
    paginate_by    = 20

    def get_queryset(self):
        qs = Appointment.objects.filter(
            patient=self.request.user,
        ).select_related('professional').order_by('-scheduled_date', '-scheduled_time')

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Appointment.Status.choices
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['today'] = timezone.localdate()
        return ctx


# ── Agenda do profissional ────────────────────────────────────────────────────

@login_required
def professional_agenda(request):
    if not _is_professional(request.user):
        messages.error(request, 'Acesso restrito a profissionais.')
        return redirect('appointment_list')

    date_str = request.GET.get('date')
    view_type = request.GET.get('view', 'day')  # day | week | month

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    appointments = (
        Appointment.objects
        .filter(professional=request.user, scheduled_date=selected_date)
        .select_related('patient')
        .order_by('scheduled_time')
        if view_type == 'day'
        else Appointment.objects
        .filter(
            professional=request.user,
            scheduled_date__range=_week_range(selected_date) if view_type == 'week' else _month_range(selected_date),
        )
        .select_related('patient')
        .order_by('scheduled_date', 'scheduled_time')
    )

    return render(request, 'appointments/agenda.html', {
        'appointments': appointments,
        'selected_date': selected_date,
        'view_type': view_type,
        'prev_date': _navigate(selected_date, -1, view_type).isoformat(),
        'next_date': _navigate(selected_date, +1, view_type).isoformat(),
        'today': timezone.localdate().isoformat(),
        'status_choices': Appointment.Status.choices,
    })


def _week_range(date):
    monday = date - timedelta(days=date.weekday())
    return monday, monday + timedelta(days=6)


def _month_range(date):
    from calendar import monthrange
    _, last = monthrange(date.year, date.month)
    from datetime import date as date_type
    return date_type(date.year, date.month, 1), date_type(date.year, date.month, last)


def _navigate(date, direction, view_type):
    if view_type == 'week':
        return date + timedelta(weeks=direction)
    if view_type == 'month':
        if direction > 0:
            if date.month == 12:
                return date.replace(year=date.year + 1, month=1, day=1)
            return date.replace(month=date.month + 1, day=1)
        else:
            if date.month == 1:
                return date.replace(year=date.year - 1, month=12, day=1)
            return date.replace(month=date.month - 1, day=1)
    return date + timedelta(days=direction)


# ── Criar agendamento ─────────────────────────────────────────────────────────

@login_required
def appointment_create(request):
    professionals_qs = User.objects.filter(role__in=PROFESSIONAL_ROLES, is_active=True).order_by('first_name')

    if request.method == 'POST':
        form = AppointmentCreateForm(request.POST, requester=request.user, professionals_qs=professionals_qs)
        if form.is_valid():
            apt = form.save(commit=False)
            apt.booked_by      = request.user
            apt.booked_by_role = (
                Appointment.BookedBy.PATIENT if not _is_professional(request.user)
                else Appointment.BookedBy.PROFESSIONAL
            )
            if not _is_professional(request.user):
                apt.patient = request.user

            apt.save()
            _record_history(apt, request.user, AppointmentHistory.Action.CREATED)

            try:
                send_appointment_confirmation(apt)
            except Exception:
                logger.exception('Failed to queue confirmation email')

            messages.success(request, 'Agendamento criado com sucesso.')
            if _is_professional(request.user):
                return redirect('professional_agenda')
            return redirect('appointment_list')
    else:
        form = AppointmentCreateForm(requester=request.user, professionals_qs=professionals_qs)
        if not _is_professional(request.user):
            form.fields.pop('patient', None)

    return render(request, 'appointments/create.html', {
        'form': form,
        'is_professional': _is_professional(request.user),
    })


# ── Detalhe do agendamento ────────────────────────────────────────────────────

class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model               = Appointment
    template_name       = 'appointments/detail.html'
    context_object_name = 'appointment'

    def get_queryset(self):
        user = self.request.user
        if _is_professional(user) and (user.is_superuser or user.role == 'ADMIN'):
            return Appointment.objects.all()
        if _is_professional(user):
            return Appointment.objects.filter(professional=user)
        return Appointment.objects.filter(patient=user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        apt = self.object
        user = self.request.user
        ctx['can_cancel']    = apt.is_cancellable and (apt.patient == user or apt.professional == user or user.role == 'ADMIN')
        ctx['can_reschedule']= apt.is_reschedulable and (apt.professional == user or user.role == 'ADMIN')
        ctx['history']       = apt.history.select_related('changed_by').all()
        ctx['is_professional'] = _is_professional(user)
        return ctx


# ── Cancelar agendamento ──────────────────────────────────────────────────────

@login_required
def appointment_cancel(request, pk):
    user = request.user
    apt  = _get_appointment_for_user(pk, user)

    if not apt.is_cancellable:
        messages.error(request, 'Este agendamento não pode ser cancelado.')
        return redirect('appointment_detail', pk=pk)

    if not (apt.patient == user or apt.professional == user or user.role == 'ADMIN' or user.is_superuser):
        messages.error(request, 'Você não tem permissão para cancelar este agendamento.')
        return redirect('appointment_detail', pk=pk)

    if request.method == 'POST':
        form = AppointmentCancelForm(request.POST)
        if form.is_valid():
            prev_status = apt.status
            apt.status              = Appointment.Status.CANCELLED
            apt.cancelled_by        = user
            apt.cancelled_at        = timezone.now()
            apt.cancellation_reason = form.cleaned_data['cancellation_reason']
            apt.save(update_fields=['status', 'cancelled_by', 'cancelled_at', 'cancellation_reason', 'updated_at'])
            _record_history(
                apt, user, AppointmentHistory.Action.CANCELLED,
                previous_status=prev_status,
                notes=form.cleaned_data['cancellation_reason'],
            )
            messages.success(request, 'Agendamento cancelado.')
            return redirect('appointment_list' if not _is_professional(user) else 'professional_agenda')
    else:
        form = AppointmentCancelForm()

    return render(request, 'appointments/cancel.html', {'appointment': apt, 'form': form})


# ── Remarcar agendamento ──────────────────────────────────────────────────────

@login_required
def appointment_reschedule(request, pk):
    user = request.user
    apt  = _get_appointment_for_user(pk, user)

    if not apt.is_reschedulable:
        messages.error(request, 'Este agendamento não pode ser remarcado.')
        return redirect('appointment_detail', pk=pk)

    if not (apt.professional == user or user.role == 'ADMIN' or user.is_superuser):
        messages.error(request, 'Apenas o profissional responsável pode remarcar.')
        return redirect('appointment_detail', pk=pk)

    if request.method == 'POST':
        form = AppointmentRescheduleForm(request.POST, appointment=apt)
        if form.is_valid():
            prev_date   = apt.scheduled_date
            prev_time   = apt.scheduled_time
            prev_status = apt.status

            # Marca o atual como remarcado e cria novo
            apt.status = Appointment.Status.RESCHEDULED
            apt.save(update_fields=['status', 'updated_at'])
            _record_history(
                apt, user, AppointmentHistory.Action.RESCHEDULED,
                previous_date=prev_date, previous_time=prev_time, previous_status=prev_status,
                notes=form.cleaned_data.get('notes', ''),
            )

            new_apt = Appointment.objects.create(
                patient          = apt.patient,
                professional     = apt.professional,
                scheduled_date   = form.cleaned_data['scheduled_date'],
                scheduled_time   = form.cleaned_data['scheduled_time'],
                duration_minutes = apt.duration_minutes,
                appointment_type = apt.appointment_type,
                specialty        = apt.specialty,
                location         = apt.location,
                notes            = form.cleaned_data.get('notes', ''),
                booked_by        = user,
                booked_by_role   = Appointment.BookedBy.PROFESSIONAL,
                rescheduled_from = apt,
            )
            _record_history(new_apt, user, AppointmentHistory.Action.CREATED,
                            notes=f'Remarcado de {prev_date} {prev_time}')

            messages.success(request, 'Agendamento remarcado com sucesso.')
            return redirect('appointment_detail', pk=new_apt.pk)
    else:
        form = AppointmentRescheduleForm(appointment=apt)

    return render(request, 'appointments/reschedule.html', {'appointment': apt, 'form': form})


# ── Iniciar atendimento a partir de um agendamento ───────────────────────────

@login_required
def iniciar_atendimento_agendamento(request, pk):
    if not _is_professional(request.user):
        messages.error(request, 'Acesso restrito a profissionais.')
        return redirect('appointment_list')

    apt = get_object_or_404(Appointment, pk=pk, professional=request.user, status__in=['scheduled', 'confirmed'])
    apt.status = Appointment.Status.COMPLETED
    apt.save(update_fields=['status', 'updated_at'])
    _record_history(apt, request.user, AppointmentHistory.Action.COMPLETED)

    messages.success(request, f'Iniciando atendimento de {apt.patient.get_full_name() or apt.patient.username}.')
    return redirect('iniciar_atendimento')


# ── Slots disponíveis (AJAX) ─────────────────────────────────────────────────

@login_required
def available_slots(request):
    """Retorna slots livres de um profissional em uma data."""
    professional_id = request.GET.get('professional_id')
    date_str        = request.GET.get('date')

    if not professional_id or not date_str:
        return JsonResponse({'slots': []})

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        professional = User.objects.get(pk=professional_id, role__in=PROFESSIONAL_ROLES)
    except (ValueError, User.DoesNotExist):
        return JsonResponse({'slots': []})

    weekday = date.weekday()
    availabilities = ProfessionalAvailability.objects.filter(
        professional=professional,
        weekday=weekday,
        is_active=True,
    )

    booked_times = set(
        Appointment.objects.filter(
            professional=professional,
            scheduled_date=date,
            status__in=['scheduled', 'confirmed'],
        ).values_list('scheduled_time', flat=True)
    )

    slots = []
    for av in availabilities:
        current = datetime.combine(date, av.start_time)
        end     = datetime.combine(date, av.end_time)
        delta   = timedelta(minutes=av.slot_duration_minutes)
        while current + delta <= end:
            t = current.time()
            if t not in booked_times:
                slots.append(t.strftime('%H:%M'))
            current += delta

    return JsonResponse({'slots': sorted(set(slots))})


# ── Disponibilidade do profissional (CRUD) ───────────────────────────────────

@login_required
def manage_availability(request):
    if not _is_professional(request.user):
        messages.error(request, 'Acesso restrito a profissionais.')
        return redirect('appointment_list')

    availabilities = ProfessionalAvailability.objects.filter(professional=request.user).order_by('weekday', 'start_time')

    if request.method == 'POST':
        form = ProfessionalAvailabilityForm(request.POST)
        if form.is_valid():
            av = form.save(commit=False)
            av.professional = request.user
            av.save()
            messages.success(request, 'Disponibilidade salva.')
            return redirect('manage_availability')
    else:
        form = ProfessionalAvailabilityForm()

    return render(request, 'appointments/availability.html', {
        'form': form,
        'availabilities': availabilities,
    })


@login_required
def delete_availability(request, pk):
    if not _is_professional(request.user):
        return redirect('appointment_list')
    av = get_object_or_404(ProfessionalAvailability, pk=pk, professional=request.user)
    if request.method == 'POST':
        av.delete()
        messages.success(request, 'Disponibilidade removida.')
    return redirect('manage_availability')


# ── Marcar como realizado / não compareceu (profissional) ────────────────────

@login_required
def appointment_mark_status(request, pk, new_status):
    if not _is_professional(request.user):
        return redirect('appointment_list')

    allowed = {Appointment.Status.COMPLETED, Appointment.Status.NO_SHOW}
    if new_status not in allowed:
        messages.error(request, 'Status inválido.')
        return redirect('appointment_detail', pk=pk)

    apt = get_object_or_404(
        Appointment, pk=pk, professional=request.user,
        status__in=['scheduled', 'confirmed'],
    )

    if request.method == 'POST':
        prev_status = apt.status
        action = (
            AppointmentHistory.Action.COMPLETED if new_status == Appointment.Status.COMPLETED
            else AppointmentHistory.Action.NO_SHOW
        )
        apt.status = new_status
        apt.save(update_fields=['status', 'updated_at'])
        _record_history(apt, request.user, action, previous_status=prev_status)
        messages.success(request, f'Agendamento marcado como {apt.get_status_display()}.')
        return redirect('professional_agenda')

    return redirect('appointment_detail', pk=pk)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_appointment_for_user(pk, user):
    """Retorna agendamento visível ao usuário ou 404."""
    if user.is_superuser or user.role == 'ADMIN':
        return get_object_or_404(Appointment, pk=pk)
    if _is_professional(user):
        return get_object_or_404(Appointment, pk=pk, professional=user)
    return get_object_or_404(Appointment, pk=pk, patient=user)
