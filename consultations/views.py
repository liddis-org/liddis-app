from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Consultation, VitalSign, ConsultationSession
from .forms import ConsultationForm, VitalSignForm


# ── Consultas do Paciente ──────────────────────────────────────────────────────

class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/list.html'
    context_object_name = 'consultations'

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)


class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def form_valid(self, form):
        form.instance.patient = self.request.user
        messages.success(self.request, 'Consulta registrada com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Consulta'
        ctx['btn_label'] = 'Salvar Consulta'
        return ctx


class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Consulta atualizada com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Consulta'
        ctx['btn_label'] = 'Salvar Alterações'
        return ctx


class ConsultationDetailView(LoginRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/detail.html'
    context_object_name = 'consultation'

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)


class ConsultationDeleteView(LoginRequiredMixin, DeleteView):
    model = Consultation
    template_name = 'consultations/confirm_delete.html'
    success_url = reverse_lazy('consultation_list')

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Consulta excluída.')
        return super().form_valid(form)


# ── Sinais Vitais ──────────────────────────────────────────────────────────────

class VitalSignListView(LoginRequiredMixin, ListView):
    model = VitalSign
    template_name = 'consultations/vitals.html'
    context_object_name = 'vitals'

    def get_queryset(self):
        return VitalSign.objects.filter(patient=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = VitalSignForm()
        return ctx


class VitalSignCreateView(LoginRequiredMixin, CreateView):
    model = VitalSign
    form_class = VitalSignForm
    success_url = reverse_lazy('vitals')

    def form_valid(self, form):
        form.instance.patient = self.request.user
        messages.success(self.request, 'Sinal vital registrado!')
        return super().form_valid(form)


# ── Fluxo de Atendimento com Token ────────────────────────────────────────────

def _is_professional(user):
    """Retorna True se o usuário NÃO é paciente (ou seja, é um profissional)."""
    return user.role != 'PATIENT'


@login_required
def iniciar_atendimento(request):
    """PACIENTE: gera um token de atendimento e exibe na tela."""
    if _is_professional(request.user):
        return redirect('entrar_atendimento')

    if request.method == 'POST':
        # Cancela sessões pendentes anteriores do mesmo paciente
        ConsultationSession.objects.filter(
            patient=request.user, status='pending'
        ).update(status='expired')

        session = ConsultationSession.objects.create(patient=request.user)
        return render(request, 'atendimento/token_gerado.html', {'session': session})

    return render(request, 'atendimento/iniciar.html')


@login_required
def entrar_atendimento(request):
    """PROFISSIONAL: insere o token recebido do paciente para iniciar o atendimento."""
    if not _is_professional(request.user):
        return redirect('iniciar_atendimento')

    if request.method == 'POST':
        token_raw = request.POST.get('token', '').strip()
        try:
            session = ConsultationSession.objects.get(token=token_raw, status='pending')

            if session.is_expired:
                session.status = 'expired'
                session.save()
                messages.error(request, 'Este token expirou. Peça ao paciente que gere um novo.')
                return render(request, 'atendimento/entrar.html')

            session.professional = request.user
            session.status = 'active'
            session.save()
            return redirect('atendimento_consulta', token=str(session.token))

        except ConsultationSession.DoesNotExist:
            messages.error(request, 'Token inválido ou já utilizado. Verifique e tente novamente.')

    return render(request, 'atendimento/entrar.html')


@login_required
def atendimento_consulta(request, token):
    """PROFISSIONAL: vê dados do paciente e preenche a consulta."""
    if not _is_professional(request.user):
        return redirect('iniciar_atendimento')

    session = get_object_or_404(
        ConsultationSession,
        token=token,
        professional=request.user,
        status='active'
    )

    patient = session.patient

    if request.method == 'POST':
        form = ConsultationForm(request.POST)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.patient = patient
            consultation.professional_name = (
                request.user.get_full_name() or request.user.username
            )
            consultation.save()

            session.consultation = consultation
            session.status = 'closed'
            session.closed_at = timezone.now()
            session.save()

            messages.success(request, f'Consulta de {patient.display_name} registrada com sucesso!')
            return redirect('dashboard')
    else:
        form = ConsultationForm(initial={
            'professional_name': request.user.get_full_name() or request.user.username,
        })

    return render(request, 'atendimento/consulta.html', {
        'session': session,
        'patient': patient,
        'form': form,
    })


@login_required
def cancelar_sessao(request, token):
    """PACIENTE: cancela o token gerado antes de ser usado."""
    session = get_object_or_404(
        ConsultationSession,
        token=token,
        patient=request.user,
        status='pending'
    )
    session.status = 'expired'
    session.save()
    messages.info(request, 'Atendimento cancelado.')
    return redirect('dashboard')