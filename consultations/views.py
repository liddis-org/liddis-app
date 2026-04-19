import uuid as _uuid_module
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.utils import timezone

_log = logging.getLogger('liddis')

from .models import Consultation, VitalSign, ConsultationSession, Anamnese, ExameLaboratorial, ConsultationImage
from .forms import ConsultationForm, VitalSignForm, AnamneseForm, ExameLaboratorialForm, AtendimentoForm


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_professional(user):
    return user.role != 'PATIENT'


def _accessible_consultations(user):
    """
    Retorna queryset de Consultation acessível ao usuário:
    - Pacientes: consultas onde são o paciente.
    - Profissionais: consultas que realizaram via sessão.
    """
    if _is_professional(user):
        return Consultation.objects.filter(session__professional=user)
    return Consultation.objects.filter(patient=user)


def _get_or_init_sub_models(consultation):
    """Retorna (anamnese, exames) da consulta — None se ainda não existirem."""
    try:
        anamnese = consultation.anamnese
    except Anamnese.DoesNotExist:
        anamnese = None
    try:
        exames = consultation.exames
    except ExameLaboratorial.DoesNotExist:
        exames = None
    return anamnese, exames


def _save_sub_forms(request, consultation, anamnese_form, exames_form):
    if anamnese_form.is_valid():
        a = anamnese_form.save(commit=False)
        a.consultation = consultation
        a.save()
    if exames_form.is_valid():
        e = exames_form.save(commit=False)
        e.consultation = consultation
        e.save()


def _handle_image_uploads(request, consultation):
    for tab, _ in ConsultationImage.TAB_CHOICES:
        for f in request.FILES.getlist(f'images_{tab}'):
            try:
                ConsultationImage.objects.create(
                    consultation=consultation,
                    tab=tab,
                    image=f,
                    caption=request.POST.get(f'caption_{tab}', ''),
                )
            except Exception as exc:
                _log.error(
                    'Falha ao salvar imagem | consulta=#%s | aba=%s | arquivo=%s | erro=%s',
                    consultation.pk, tab, f.name, exc,
                )


# ── Consultas ──────────────────────────────────────────────────────────────────

VALID_SORTS = {'-date', 'date', 'professional_name', '-professional_name'}


class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/list.html'
    context_object_name = 'consultations'

    def get_queryset(self):
        qs = _accessible_consultations(self.request.user)
        q = self.request.GET.get('q', '').strip()
        if q:
            filters = (
                Q(professional_name__icontains=q) |
                Q(specialty__icontains=q) |
                Q(specialty_other__icontains=q) |
                Q(diagnosis__icontains=q) |
                Q(date__icontains=q)
            )
            if _is_professional(self.request.user):
                # Profissional: busca também por nome do paciente
                filters |= (
                    Q(patient__first_name__icontains=q) |
                    Q(patient__last_name__icontains=q) |
                    Q(patient__username__icontains=q)
                )
            qs = qs.filter(filters)
        sort = self.request.GET.get('sort', '-date')
        return qs.order_by(sort if sort in VALID_SORTS else '-date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['sort'] = self.request.GET.get('sort', '-date')
        ctx['is_professional'] = _is_professional(self.request.user)
        return ctx


class ConsultationDetailView(LoginRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/detail.html'
    context_object_name = 'consultation'

    def get_queryset(self):
        return _accessible_consultations(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anamnese, exames = _get_or_init_sub_models(self.object)
        ctx['anamnese'] = anamnese
        ctx['exames'] = exames
        ctx['images_by_tab'] = {
            tab: list(self.object.images.filter(tab=tab))
            for tab, _ in ConsultationImage.TAB_CHOICES
        }
        ctx['tab_choices'] = ConsultationImage.TAB_CHOICES
        ctx['active_tab'] = self.request.GET.get('tab', 'geral')
        ctx['is_professional'] = _is_professional(self.request.user)
        return ctx


class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def dispatch(self, request, *args, **kwargs):
        # Profissionais devem criar consultas via fluxo de token
        if request.user.is_authenticated and _is_professional(request.user):
            messages.info(request, 'Profissionais devem iniciar consultas pelo fluxo de atendimento com token.')
            return redirect('entrar_atendimento')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Consulta'
        ctx['btn_label'] = 'Salvar Consulta'
        data = self.request.POST if self.request.POST else None
        ctx['anamnese_form'] = AnamneseForm(data, prefix='anamnese')
        ctx['exames_form'] = ExameLaboratorialForm(data, prefix='exames')
        ctx['active_tab'] = (self.request.POST or {}).get('active_tab', 'geral')
        ctx['tab_choices'] = ConsultationImage.TAB_CHOICES
        return ctx

    def form_valid(self, form):
        form.instance.patient = self.request.user
        response = super().form_valid(form)
        anamnese_form = AnamneseForm(self.request.POST, prefix='anamnese')
        exames_form = ExameLaboratorialForm(self.request.POST, prefix='exames')
        _save_sub_forms(self.request, self.object, anamnese_form, exames_form)
        _handle_image_uploads(self.request, self.object)
        messages.success(self.request, 'Consulta registrada com sucesso!')
        return response


class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def get_queryset(self):
        return _accessible_consultations(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Consulta'
        ctx['btn_label'] = 'Salvar Alterações'
        consultation = self.object
        anamnese, exames = _get_or_init_sub_models(consultation)
        data = self.request.POST if self.request.POST else None
        ctx['anamnese_form'] = AnamneseForm(data, prefix='anamnese', instance=anamnese)
        ctx['exames_form'] = ExameLaboratorialForm(data, prefix='exames', instance=exames)
        ctx['images_by_tab'] = {
            tab: list(consultation.images.filter(tab=tab))
            for tab, _ in ConsultationImage.TAB_CHOICES
        }
        ctx['tab_choices'] = ConsultationImage.TAB_CHOICES
        ctx['active_tab'] = (self.request.POST or {}).get('active_tab', 'geral')
        ctx['is_professional'] = _is_professional(self.request.user)
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        consultation = self.object
        anamnese, exames = _get_or_init_sub_models(consultation)
        anamnese_form = AnamneseForm(self.request.POST, prefix='anamnese', instance=anamnese)
        exames_form = ExameLaboratorialForm(self.request.POST, prefix='exames', instance=exames)
        _save_sub_forms(self.request, consultation, anamnese_form, exames_form)
        _handle_image_uploads(self.request, consultation)
        messages.success(self.request, 'Consulta atualizada com sucesso!')
        return response


class ConsultationDeleteView(LoginRequiredMixin, DeleteView):
    model = Consultation
    template_name = 'consultations/confirm_delete.html'
    success_url = reverse_lazy('consultation_list')

    def get_queryset(self):
        return _accessible_consultations(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Consulta excluída.')
        return super().form_valid(form)


# ── Upload / Delete de Imagens ─────────────────────────────────────────────────

@login_required
def upload_image(request, pk):
    consultation = get_object_or_404(
        _accessible_consultations(request.user), pk=pk
    )
    tab = request.POST.get('tab', 'anamnese')
    if request.method == 'POST':
        file = request.FILES.get('image')
        valid_tabs = [t for t, _ in ConsultationImage.TAB_CHOICES]
        if file and tab in valid_tabs:
            ConsultationImage.objects.create(
                consultation=consultation,
                tab=tab,
                image=file,
                caption=request.POST.get('caption', ''),
            )
            messages.success(request, 'Imagem anexada com sucesso!')
        else:
            messages.error(request, 'Arquivo inválido.')
    return redirect(f'/consultas/{pk}/?tab={tab}')


@login_required
def delete_image(request, pk, img_pk):
    consultation = get_object_or_404(
        _accessible_consultations(request.user), pk=pk
    )
    image = get_object_or_404(ConsultationImage, pk=img_pk, consultation=consultation)
    tab = image.tab
    image.image.delete(save=False)
    image.delete()
    messages.success(request, 'Imagem removida.')
    return redirect(f'/consultas/{pk}/?tab={tab}')


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

@login_required
def iniciar_atendimento(request):
    if _is_professional(request.user):
        return redirect('entrar_atendimento')
    if request.method == 'POST':
        ConsultationSession.objects.filter(
            patient=request.user, status='pending'
        ).update(status='expired')
        session = ConsultationSession.objects.create(patient=request.user)

        # ── Log de desenvolvimento (visível nos logs do servidor) ─────────────
        from django.utils.timezone import localtime
        expires_local = localtime(session.expires_at)
        _log.info(
            'NOVO ATENDIMENTO | paciente=%s | código=%s | token=%s | expira=%s',
            request.user.get_full_name() or request.user.username,
            session.token_display,
            session.token,
            expires_local.strftime('%d/%m/%Y %H:%M'),
        )

        return render(request, 'atendimento/token_gerado.html', {'session': session})
    return render(request, 'atendimento/iniciar.html')


def entrar_atendimento(request):
    """
    Tela de entrada do profissional.
    - Se já autenticado como profissional: mostra apenas o campo de token.
    - Se não autenticado: mostra login + token em uma única etapa.
    """
    # Paciente logado tentando acessar → redireciona
    if request.user.is_authenticated and not _is_professional(request.user):
        return redirect('iniciar_atendimento')

    test_mode = getattr(settings, 'TEST_MODE', False)
    short_code_allowed = test_mode or settings.DEBUG   # código curto liberado em qualquer ambiente de dev
    already_logged = request.user.is_authenticated
    ctx = {'test_mode': short_code_allowed, 'already_logged': already_logged}

    if request.method == 'POST':
        token_raw = request.POST.get('token', '').strip()
        professional = request.user if already_logged else None

        # ── Autenticar profissional se ainda não estiver logado ───────────────
        if not already_logged:
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            professional = authenticate(request, username=username, password=password)

            if professional is None:
                messages.error(request, 'Credenciais inválidas. Verifique seu e-mail/usuário e senha.')
                return render(request, 'atendimento/entrar.html', ctx)

            if not _is_professional(professional):
                messages.error(request, 'Esta conta não tem permissão de profissional.')
                return render(request, 'atendimento/entrar.html', ctx)

            login(request, professional)

        # ── Verificar perfil completo (só para profissional logado) ───────────
        prof = request.user
        if not prof.profession or not prof.professional_specialty:
            messages.warning(
                request,
                'Complete seu perfil antes de iniciar um atendimento: '
                'informe sua Profissão e Especialidade.'
            )
            return redirect('profile')

        # ── Buscar sessão pelo token ──────────────────────────────────────────
        session = None
        pending_sessions = list(ConsultationSession.objects.filter(status='pending'))
        _log.debug(
            'ENTRAR_ATENDIMENTO | token_raw=%r len=%d short_code_allowed=%s | sessões pendentes: %s',
            token_raw, len(token_raw), short_code_allowed,
            [(str(s.token_display), str(s.token)) for s in pending_sessions],
        )

        if short_code_allowed and len(token_raw) <= 8:
            # código curto: compara com os primeiros 8 chars do token
            token_upper = token_raw.upper()
            for s in pending_sessions:
                if s.token_display == token_upper:
                    session = s
                    break
            if session is None:
                messages.error(
                    request,
                    'Código curto não encontrado entre os atendimentos pendentes. '
                    'Peça ao paciente que gere um novo código.',
                )
                return render(request, 'atendimento/entrar.html', {**ctx, 'already_logged': True})
        else:
            try:
                uuid_obj = _uuid_module.UUID(token_raw)
            except (ValueError, AttributeError):
                messages.error(
                    request,
                    'Formato de token inválido. '
                    'Insira o código UUID completo fornecido pelo paciente '
                    '(ex: a1b2c3d4-e5f6-7890-abcd-ef1234567890).',
                )
                return render(request, 'atendimento/entrar.html', {**ctx, 'already_logged': True})

            try:
                session = ConsultationSession.objects.get(token=uuid_obj, status='pending')
            except ConsultationSession.DoesNotExist:
                messages.error(request, 'Token inválido ou já utilizado.')
                return render(request, 'atendimento/entrar.html', {**ctx, 'already_logged': True})

        # ── Verifica expiração e ativa sessão ─────────────────────────────────
        _log.debug(
            'EXPIRAÇÃO | agora(UTC)=%s | expires_at(UTC)=%s | is_expired=%s',
            timezone.now().strftime('%d/%m/%Y %H:%M:%S UTC'),
            session.expires_at.strftime('%d/%m/%Y %H:%M:%S UTC'),
            session.is_expired,
        )
        if session.is_expired:
            session.status = 'expired'
            session.save()
            messages.error(request, 'Este token expirou. Peça ao paciente que gere um novo.')
            return render(request, 'atendimento/entrar.html', {**ctx, 'already_logged': True})

        session.professional = request.user
        session.status = 'active'
        session.save()
        return redirect('atendimento_consulta', token=str(session.token))

    return render(request, 'atendimento/entrar.html', ctx)


@login_required
def atendimento_consulta(request, token):
    if not _is_professional(request.user):
        return redirect('iniciar_atendimento')

    session = get_object_or_404(
        ConsultationSession, token=token,
        professional=request.user, status='active'
    )
    patient = session.patient

    if request.method == 'POST':
        form = AtendimentoForm(request.POST)
        anamnese_form = AnamneseForm(request.POST, prefix='anamnese')
        exames_form = ExameLaboratorialForm(request.POST, prefix='exames')
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.patient = patient
            consultation.professional_name = request.user.get_full_name() or request.user.username
            consultation.profession = request.user.profession
            consultation.specialty = request.user.professional_specialty or 'outro'
            consultation.save()
            _save_sub_forms(request, consultation, anamnese_form, exames_form)
            _handle_image_uploads(request, consultation)
            session.consultation = consultation
            session.status = 'closed'
            session.closed_at = timezone.now()
            session.save()
            messages.success(request, f'Consulta de {patient.display_name} registrada!')
            return redirect('dashboard')
    else:
        form = AtendimentoForm()
        anamnese_form = AnamneseForm(prefix='anamnese')
        exames_form = ExameLaboratorialForm(prefix='exames')

    return render(request, 'atendimento/consulta.html', {
        'session': session,
        'patient': patient,
        'form': form,
        'anamnese_form': anamnese_form,
        'exames_form': exames_form,
        'tab_choices': ConsultationImage.TAB_CHOICES,
        'active_tab': request.POST.get('active_tab', 'geral'),
        'professional': request.user,
    })


@login_required
def cancelar_sessao(request, token):
    session = get_object_or_404(
        ConsultationSession, token=token,
        patient=request.user, status='pending'
    )
    session.status = 'expired'
    session.save()
    messages.info(request, 'Atendimento cancelado.')
    return redirect('dashboard')
