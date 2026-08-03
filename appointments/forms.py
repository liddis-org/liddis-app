from django import forms
from django.utils import timezone
from .models import Appointment, ProfessionalAvailability, SPECIALTY_CHOICES


class AppointmentCreateForm(forms.ModelForm):
    """Formulário de agendamento — usado por pacientes e profissionais."""

    class Meta:
        model  = Appointment
        fields = ['professional', 'scheduled_date', 'scheduled_time', 'appointment_type', 'specialty', 'location', 'notes']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'professional':   forms.Select(attrs={'class': 'form-control'}),
            'appointment_type': forms.Select(attrs={'class': 'form-control'}),
            'specialty':      forms.Select(attrs={'class': 'form-control'}),
            'location':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Local da consulta (opcional)'}),
            'notes':          forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observações (opcional)'}),
        }
        labels = {
            'professional':    'Profissional',
            'scheduled_date':  'Data',
            'scheduled_time':  'Horário',
            'appointment_type':'Tipo de consulta',
            'specialty':       'Especialidade',
            'location':        'Local',
            'notes':           'Observações',
        }

    def __init__(self, *args, **kwargs):
        self.requester = kwargs.pop('requester', None)
        professionals_qs = kwargs.pop('professionals_qs', None)
        super().__init__(*args, **kwargs)

        if professionals_qs is not None:
            self.fields['professional'].queryset = professionals_qs

        self.fields['scheduled_date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean(self):
        cleaned = super().clean()
        date  = cleaned.get('scheduled_date')
        time  = cleaned.get('scheduled_time')
        prof  = cleaned.get('professional')

        if date and date < timezone.localdate():
            raise forms.ValidationError('A data do agendamento não pode ser no passado.')

        if date and time and prof:
            conflict = Appointment.objects.filter(
                professional=prof,
                scheduled_date=date,
                scheduled_time=time,
                status__in=['scheduled', 'confirmed'],
            )
            if self.instance.pk:
                conflict = conflict.exclude(pk=self.instance.pk)
            if conflict.exists():
                raise forms.ValidationError('Este horário já está reservado para o profissional selecionado.')

        return cleaned


class AppointmentRescheduleForm(forms.Form):
    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Nova data',
    )
    scheduled_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label='Novo horário',
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Motivo da remarcação (opcional)'}),
        required=False,
        label='Observações',
    )

    def __init__(self, *args, appointment=None, **kwargs):
        self.appointment = appointment
        super().__init__(*args, **kwargs)
        self.fields['scheduled_date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('scheduled_date')
        time = cleaned.get('scheduled_time')

        if date and date < timezone.localdate():
            raise forms.ValidationError('A nova data não pode ser no passado.')

        if date and time and self.appointment:
            conflict = Appointment.objects.filter(
                professional=self.appointment.professional,
                scheduled_date=date,
                scheduled_time=time,
                status__in=['scheduled', 'confirmed'],
            ).exclude(pk=self.appointment.pk)
            if conflict.exists():
                raise forms.ValidationError('Este horário já está reservado para o profissional.')

        return cleaned


class AppointmentCancelForm(forms.Form):
    cancellation_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Informe o motivo do cancelamento'}),
        label='Motivo do cancelamento',
        required=True,
    )


class ProfessionalAvailabilityForm(forms.ModelForm):
    class Meta:
        model  = ProfessionalAvailability
        fields = ['weekday', 'start_time', 'end_time', 'slot_duration_minutes', 'is_active']
        widgets = {
            'weekday':               forms.Select(attrs={'class': 'form-control'}),
            'start_time':            forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time':              forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'slot_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'max': 120, 'step': 5}),
        }
        labels = {
            'weekday':               'Dia da semana',
            'start_time':            'Início',
            'end_time':              'Fim',
            'slot_duration_minutes': 'Duração do slot (min)',
            'is_active':             'Ativo',
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end   = cleaned.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('O horário de fim deve ser posterior ao de início.')
        return cleaned
