import uuid as _uuid_module
import logging
import mimetypes
import os

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, Http404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.utils import timezone

_ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'pdf'}
_MAX_UPLOAD_BYTES   = 20 * 1024 * 1024  # 20 MB

_log = logging.getLogger('liddis')

from .models import (
    Consultation, VitalSign, ConsultationSession, Anamnese, ExameLaboratorial,
    ConsultationImage, Evolution, Prescription, DiagnosisCID, PhysicalExam, LabRequest,
    PatientClinicalSummary, ClinicalIntervention, ExpectedEvolution,
)
from .forms import (
    ConsultationForm, VitalSignForm, AnamneseForm, ExameLaboratorialForm, AtendimentoForm,
    EvolutionForm, PrescriptionForm, DiagnosisCIDForm, PhysicalExamForm,
    LabRequestForm, LabResultForm, VitalSignProfessionalForm, PatientClinicalSummaryForm,
    ClinicalInterventionForm, ExpectedEvolutionForm,
)
from users.permissions import (
    has_permission, can_access_patient,
    filter_evolutions_for_user, get_evolution_create_category,
    get_prescription_allowed_types,
)
from users.audit import log_access


# ── Helpers ────────────────────────────────────────────────────────────────────

# Mapeamento de perfil profissional → nome clínico da avaliação
_EVALUATION_LABEL = {
    'DOCTOR':            'Avaliação Médica',
    'NURSE':             'Avaliação de Enfermagem',
    'PHYSIO':            'Avaliação Fisioterapêutica',
    'NUTRITIONIST':      'Avaliação Nutricional',
    'SPEECH_THERAPIST':  'Avaliação Fonoaudiológica',
    'PHYSICAL_EDUCATOR': 'Avaliação de Educação Física',
    'PSYCHOLOGIST':      'Avaliação Psicológica',
    'DENTIST':           'Avaliação Odontológica',
    'OCC_THERAPIST':     'Avaliação de Terapia Ocupacional',
    'PHARMACIST':        'Avaliação Farmacêutica',
    'BIOMEDICO':         'Avaliação Biomédica',
    'ADMIN':             'Avaliação Clínica',
    'PATIENT':           'Avaliação',
}

_DIAGNOSIS_LABEL = {
    'DOCTOR':            'DIAGNÓSTICO MÉDICO',
    'NURSE':             'DIAGNÓSTICO DE ENFERMAGEM',
    'PHYSIO':            'DIAGNÓSTICO FISIOTERAPÊUTICO',
    'NUTRITIONIST':      'DIAGNÓSTICO NUTRICIONAL',
    'SPEECH_THERAPIST':  'DIAGNÓSTICO FONOAUDIOLÓGICO',
    'PHYSICAL_EDUCATOR': 'AVALIAÇÃO FÍSICA',
    'PSYCHOLOGIST':      'DIAGNÓSTICO PSICOLÓGICO',
    'DENTIST':           'DIAGNÓSTICO ODONTOLÓGICO',
    'OCC_THERAPIST':     'DIAGNÓSTICO OCUPACIONAL',
    'PHARMACIST':        'AVALIAÇÃO FARMACÊUTICA',
    'BIOMEDICO':         'DIAGNÓSTICO BIOMÉDICO',
    'ADMIN':             'DIAGNÓSTICO CLÍNICO',
    'PATIENT':           'AVALIAÇÃO CLÍNICA',
}

_CLASSIFICATION_HINT = {
    'DOCTOR':            'CID-11 / CIAP-2',
    'NURSE':             'NANDA',
    'PHYSIO':            'CIF',
    'NUTRITIONIST':      'CID-10 / TUSS',
    'SPEECH_THERAPIST':  'CID-10',
    'PHYSICAL_EDUCATOR': 'CID-10',
    'PSYCHOLOGIST':      'DSM-5-TR',
    'DENTIST':           'CID-10 / TUSS',
    'OCC_THERAPIST':     'CIF / CID-10',
    'PHARMACIST':        'CID-10',
    'BIOMEDICO':         'CID-10',
    'ADMIN':             'CID-10',
}

# Rótulo do Bloco 1 completo (inclui sistema de classificação)
_BLOCK1_LABEL = {
    'DOCTOR':            'Diagnóstico Médico (CID-11 / CIAP-2)',
    'NURSE':             'Diagnóstico de Enfermagem (NANDA)',
    'PHYSIO':            'Diagnóstico Cinesiológico-Funcional (CIF)',
    'NUTRITIONIST':      'Diagnóstico Nutricional (CID-10)',
    'SPEECH_THERAPIST':  'Diagnóstico Fonoaudiológico (CID-10)',
    'PHYSICAL_EDUCATOR': 'Avaliação Física (CID-10)',
    'PSYCHOLOGIST':      'Hipótese Diagnóstica (DSM-5-TR)',
    'DENTIST':           'Diagnóstico Odontológico (CID-10)',
    'OCC_THERAPIST':     'Diagnóstico Ocupacional (CIF / CID-10)',
    'PHARMACIST':        'Avaliação Farmacêutica (CID-10)',
    'BIOMEDICO':         'Diagnóstico Biomédico (CID-10)',
    'ADMIN':             'Diagnóstico Clínico',
    'PATIENT':           'Avaliação Clínica',
}

# Sub-rótulo do Bloco 1 (natureza dos fatores relacionados)
_BLOCK1_SUBLABEL = {
    'DOCTOR':            'Etiologia / Fisiopatologia',
    'NURSE':             'Fatores Relacionados e Características Definidoras',
    'PHYSIO':            'Limitações de Atividade e Restrições de Mobilidade',
    'NUTRITIONIST':      'Fatores Nutricionais e Metabólicos',
    'SPEECH_THERAPIST':  'Alterações de Comunicação e Deglutição',
    'PHYSICAL_EDUCATOR': 'Capacidade Funcional e Condicionamento',
    'PSYCHOLOGIST':      'Fatores Psicossociais e Gatilhos',
    'DENTIST':           'Comprometimentos Dentários e Periodontais',
    'OCC_THERAPIST':     'Barreiras Ocupacionais e Ambientais',
    'PHARMACIST':        'Interações e Adesão Farmacológica',
    'BIOMEDICO':         'Alterações Laboratoriais e Moleculares',
    'ADMIN':             'Fatores Clínicos',
    'PATIENT':           'Informações do Diagnóstico',
}

# Rótulo do Bloco 2 (intervenções)
_BLOCK2_LABEL = {
    'DOCTOR':            'Prescrição e Conduta Médica',
    'NURSE':             'Intervenções de Enfermagem (NIC)',
    'PHYSIO':            'Plano de Tratamento Cinesioterapêutico',
    'NUTRITIONIST':      'Plano Alimentar e Conduta Nutricional',
    'SPEECH_THERAPIST':  'Plano Terapêutico Fonoaudiológico',
    'PHYSICAL_EDUCATOR': 'Programa de Exercícios e Atividade Física',
    'PSYCHOLOGIST':      'Manejo e Abordagem Terapêutica',
    'DENTIST':           'Plano de Tratamento Odontológico',
    'OCC_THERAPIST':     'Plano de Intervenção Ocupacional',
    'PHARMACIST':        'Orientação e Acompanhamento Farmacoterapêutico',
    'BIOMEDICO':         'Condutas e Análises Recomendadas',
    'ADMIN':             'Condutas e Intervenções',
    'PATIENT':           'Condutas Registradas',
}

# Rótulo do Bloco 3 (evolução esperada)
_BLOCK3_LABEL = {
    'DOCTOR':            'Prognóstico Clínico e Critérios de Alta / Retorno',
    'NURSE':             'Resultados Esperados (NOC) e Metas de Cuidado',
    'PHYSIO':            'Ganho Funcional, Escala de Dor e Sessões Estimadas',
    'NUTRITIONIST':      'Metas Nutricionais e Indicadores Antropométricos',
    'SPEECH_THERAPIST':  'Progressão da Terapia e Indicadores de Alta',
    'PHYSICAL_EDUCATOR': 'Metas de Condicionamento e Progressão do Treino',
    'PSYCHOLOGIST':      'Metas de Regulação Emocional e Frequência das Sessões',
    'DENTIST':           'Prognóstico Odontológico e Plano de Manutenção',
    'OCC_THERAPIST':     'Ganho Ocupacional e Critérios de Alta',
    'PHARMACIST':        'Adesão Esperada e Monitoramento Terapêutico',
    'BIOMEDICO':         'Resultados Esperados dos Exames e Monitoramento',
    'ADMIN':             'Evolução Esperada e Metas Clínicas',
    'PATIENT':           'Evolução Esperada',
}


def _evaluation_label(user):
    return _EVALUATION_LABEL.get(user.role, 'Avaliação Clínica')


def _diagnosis_label(user):
    return _DIAGNOSIS_LABEL.get(user.role, 'DIAGNÓSTICO CLÍNICO')


def _classification_hint(user):
    return _CLASSIFICATION_HINT.get(user.role, 'CID-10')


def _block1_label(user):
    return _BLOCK1_LABEL.get(user.role, 'Diagnóstico Clínico')


def _block1_sublabel(user):
    return _BLOCK1_SUBLABEL.get(user.role, 'Fatores Relacionados')


def _block2_label(user):
    return _BLOCK2_LABEL.get(user.role, 'Condutas e Intervenções')


def _block3_label(user):
    return _BLOCK3_LABEL.get(user.role, 'Evolução Esperada e Metas Clínicas')


def _is_professional(user):
    return user.role != 'PATIENT'


def _accessible_consultations(user):
    """
    Retorna queryset de Consultation acessível ao usuário:
    - Pacientes: consultas onde são o paciente.
    - Superusuário / ADMIN: todas as consultas do sistema.
    - Profissionais: consultas que realizaram via sessão ou com pacientes vinculados.
    """
    if _is_professional(user):
        if user.is_superuser or user.role == 'ADMIN':
            return Consultation.objects.all()
        from users.models import PatientProfessionalAccess
        linked_patients = PatientProfessionalAccess.objects.filter(
            professional=user, is_active=True
        ).values_list('patient_id', flat=True)
        return Consultation.objects.filter(
            Q(session__professional=user) | Q(patient__in=linked_patients)
        )
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


def _valid_attachment(f) -> bool:
    ext = os.path.splitext(f.name)[1].lstrip('.').lower()
    return ext in _ALLOWED_EXTENSIONS and f.size <= _MAX_UPLOAD_BYTES


def _handle_image_uploads(request, consultation):
    for tab, _ in ConsultationImage.TAB_CHOICES:
        for f in request.FILES.getlist(f'images_{tab}'):
            if not _valid_attachment(f):
                _log.warning(
                    'Anexo rejeitado | consulta=#%s | aba=%s | arquivo=%s | tamanho=%s',
                    consultation.pk, tab, f.name, f.size,
                )
                continue
            try:
                ConsultationImage.objects.create(
                    consultation=consultation,
                    tab=tab,
                    image=f,
                    caption=request.POST.get(f'caption_{tab}', ''),
                )
            except Exception as exc:
                _log.error(
                    'Falha ao salvar anexo | consulta=#%s | aba=%s | arquivo=%s | erro=%s',
                    consultation.pk, tab, f.name, exc,
                )


# ── Consultas ──────────────────────────────────────────────────────────────────

VALID_SORTS = {'-date', 'date', 'professional_name', '-professional_name'}


class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/list.html'
    context_object_name = 'consultations'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_permission(request.user, 'consultation', 'view'):
            log_access(request, 'access_denied', 'consultation', success=False)
            messages.error(request, 'Você não tem permissão para visualizar consultas.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

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
        ctx['allowed_actions'] = {
            'create': has_permission(self.request.user, 'consultation', 'create'),
            'edit':   has_permission(self.request.user, 'consultation', 'edit'),
            'delete': has_permission(self.request.user, 'consultation', 'delete'),
        }
        return ctx


class ConsultationDetailView(LoginRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/detail.html'
    context_object_name = 'consultation'

    def get_queryset(self):
        return _accessible_consultations(self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        log_access(
            self.request, 'view', 'consultation',
            resource_id=obj.pk,
            patient=obj.patient if hasattr(obj, 'patient') else None,
        )
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anamnese, exames = _get_or_init_sub_models(self.object)
        user = self.request.user
        patient = self.object.patient
        ctx['anamnese'] = anamnese if has_permission(user, 'anamnese', 'view') else None
        ctx['exames']   = exames   if has_permission(user, 'exams',    'view') else None
        ctx['images_by_tab'] = (
            {
                tab: list(self.object.images.filter(tab=tab))
                for tab, _ in ConsultationImage.TAB_CHOICES
            }
            if has_permission(user, 'images', 'view') else {}
        )
        ctx['tab_choices']   = ConsultationImage.TAB_CHOICES
        ctx['active_tab']    = self.request.GET.get('tab', 'geral')
        ctx['is_professional']     = _is_professional(user)
        ctx['evaluation_label']    = _evaluation_label(user)
        ctx['diagnosis_label']     = _diagnosis_label(user)
        ctx['classification_hint'] = _classification_hint(user)
        ctx['block1_label']        = _block1_label(user)
        ctx['block1_sublabel']     = _block1_sublabel(user)
        ctx['block2_label']        = _block2_label(user)
        ctx['block3_label']        = _block3_label(user)

        # Perfil clínico permanente do paciente (Descrição do Paciente)
        try:
            ctx['clinical_summary'] = patient.clinical_summary
        except PatientClinicalSummary.DoesNotExist:
            ctx['clinical_summary'] = None
        ctx['can_edit_clinical_summary'] = _is_professional(user)

        # Dados demográficos do paciente (carregados automaticamente do banco)
        try:
            ctx['patient_profile'] = patient.patient_profile
        except Exception:
            ctx['patient_profile'] = None

        # Intervenção clínica registrada nesta consulta
        ctx['clinical_intervention'] = ClinicalIntervention.objects.filter(
            consultation=self.object
        ).select_related('professional').first()

        # Evolução esperada registrada nesta consulta
        ctx['expected_evolution'] = ExpectedEvolution.objects.filter(
            consultation=self.object
        ).select_related('professional').first()

        # Sinais vitais recentes do paciente
        ctx['vitals_recentes'] = VitalSign.objects.filter(
            patient=patient
        ).order_by('-date', '-created_at')[:5]

        # Paciente que criou a consulta manualmente pode gerir seus próprios anexos
        consultation = self.object
        is_owner_patient = (
            not _is_professional(user)
            and consultation.patient_id == user.pk
            and consultation.is_patient_record
        )
        ctx['allowed_actions'] = {
            'edit':             has_permission(user, 'consultation', 'edit') or is_owner_patient,
            'delete':           has_permission(user, 'consultation', 'delete') or is_owner_patient,
            'view_anamnese':    has_permission(user, 'anamnese',     'view'),
            'edit_anamnese':    has_permission(user, 'anamnese',     'edit') or is_owner_patient,
            'view_exams':       has_permission(user, 'exams',        'view'),
            'view_prescription':has_permission(user, 'prescription', 'view'),
            'view_diagnosis':   has_permission(user, 'diagnosis',    'view'),
            'view_images':      has_permission(user, 'images',       'view'),
            'upload_images':    has_permission(user, 'images',       'create') or is_owner_patient,
            'delete_images':    has_permission(user, 'images',       'delete') or is_owner_patient,
        }
        return ctx


class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and _is_professional(request.user):
            messages.info(request, 'Profissionais devem iniciar consultas pelo fluxo de atendimento com token.')
            return redirect('entrar_atendimento')
        if request.user.is_authenticated and not has_permission(request.user, 'consultation', 'create'):
            log_access(request, 'access_denied', 'consultation', success=False)
            messages.error(request, 'Você não tem permissão para criar consultas.')
            return redirect('consultation_list')
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
        # Paciente cria consultas manuais; profissional usa fluxo de atendimento
        form.instance.record_origin = (
            Consultation.RecordOrigin.PATIENT_MANUAL
            if not _is_professional(self.request.user)
            else Consultation.RecordOrigin.PLATFORM
        )
        response = super().form_valid(form)
        anamnese_form = AnamneseForm(self.request.POST, prefix='anamnese')
        exames_form = ExameLaboratorialForm(self.request.POST, prefix='exames')
        _save_sub_forms(self.request, self.object, anamnese_form, exames_form)
        _handle_image_uploads(self.request, self.object)
        log_access(self.request, 'create', 'consultation', resource_id=self.object.pk)
        messages.success(self.request, 'Consulta registrada com sucesso!')
        return response


class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/form.html'
    success_url = reverse_lazy('consultation_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_permission(request.user, 'consultation', 'edit'):
            log_access(request, 'access_denied', 'consultation', success=False)
            messages.error(request, 'Você não tem permissão para editar consultas.')
            return redirect('consultation_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = _accessible_consultations(self.request.user)
        # Segurança: pacientes só editam registros que eles mesmos cadastraram
        if not _is_professional(self.request.user):
            qs = qs.filter(record_origin=Consultation.RecordOrigin.PATIENT_MANUAL)
        return qs

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
        log_access(self.request, 'edit', 'consultation', resource_id=consultation.pk)
        messages.success(self.request, 'Consulta atualizada com sucesso!')
        return response


class ConsultationDeleteView(LoginRequiredMixin, DeleteView):
    model = Consultation
    template_name = 'consultations/confirm_delete.html'
    success_url = reverse_lazy('consultation_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_permission(request.user, 'consultation', 'delete'):
            log_access(request, 'access_denied', 'consultation', success=False)
            messages.error(request, 'Você não tem permissão para excluir consultas.')
            return redirect('consultation_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = _accessible_consultations(self.request.user)
        # Segurança: pacientes só excluem registros que eles mesmos cadastraram
        if not _is_professional(self.request.user):
            qs = qs.filter(record_origin=Consultation.RecordOrigin.PATIENT_MANUAL)
        return qs

    def form_valid(self, form):
        log_access(self.request, 'delete', 'consultation', resource_id=self.object.pk)
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
        if file and tab in valid_tabs and _valid_attachment(file):
            try:
                ConsultationImage.objects.create(
                    consultation=consultation,
                    tab=tab,
                    image=file,
                    caption=request.POST.get('caption', ''),
                )
                messages.success(request, 'Arquivo anexado com sucesso!')
            except Exception as exc:
                _log.error(
                    'upload_image falhou | consulta=%s | tab=%s | arquivo=%s | erro=%s',
                    pk, tab, file.name, exc,
                )
                messages.error(request, 'Falha ao armazenar o arquivo. Verifique o storage e tente novamente.')
        else:
            messages.error(request, 'Arquivo inválido. Use JPG, PNG, WEBP ou PDF (máx. 20 MB).')
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
    messages.success(request, 'Anexo removido.')
    return redirect(f'/consultas/{pk}/?tab={tab}')


@login_required
def attachment_proxy(request, pk, img_pk):
    """
    Serve anexos da consulta com controle de acesso e auditoria LGPD.
    Em produção (GCS): faz streaming via SDK do GCS.
    Em desenvolvimento: serve do filesystem local.
    """
    consultation = get_object_or_404(_accessible_consultations(request.user), pk=pk)
    attachment = get_object_or_404(ConsultationImage, pk=img_pk, consultation=consultation)

    log_access(
        request, 'view', 'attachment',
        resource_id=str(img_pk),
        patient=consultation.patient,
    )

    filename = attachment.filename
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = 'application/octet-stream'

    gcs_bucket = getattr(settings, 'GCS_BUCKET_NAME', '')
    if gcs_bucket and not settings.DEBUG:
        try:
            from google.cloud import storage as gcs_storage
            client = gcs_storage.Client()
            blob = client.bucket(gcs_bucket).blob(attachment.image.name)

            if not blob.exists():
                _log.error(
                    'attachment_proxy blob inexistente | bucket=%s | blob=%s | img=%s',
                    gcs_bucket, attachment.image.name, img_pk,
                )
                raise Http404

            data = blob.download_as_bytes()
            response = HttpResponse(data, content_type=content_type)
        except Http404:
            raise
        except Exception as exc:
            _log.error(
                'attachment_proxy GCS error | pk=%s | img=%s | blob=%s | erro=%s',
                pk, img_pk, attachment.image.name, exc,
            )
            raise Http404
    else:
        from django.http import FileResponse
        try:
            response = FileResponse(open(attachment.image.path, 'rb'), content_type=content_type)
        except (FileNotFoundError, ValueError) as exc:
            _log.warning(
                'attachment_proxy arquivo local ausente | pk=%s | img=%s | path=%s | %s',
                pk, img_pk, getattr(attachment.image, 'path', 'N/A'), exc,
            )
            raise Http404

    disposition = 'inline' if content_type.startswith(('image/', 'application/pdf')) else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-cache, no-store'
    return response


# ── Sinais Vitais ──────────────────────────────────────────────────────────────

class VitalSignListView(LoginRequiredMixin, ListView):
    model = VitalSign
    template_name = 'consultations/vitals.html'
    context_object_name = 'vitals'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_permission(request.user, 'vitals', 'view'):
            log_access(request, 'access_denied', 'vitals', success=False)
            messages.error(request, 'Você não tem permissão para visualizar sinais vitais.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return VitalSign.objects.filter(patient=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = VitalSignForm()
        ctx['can_create'] = has_permission(self.request.user, 'vitals', 'create')
        return ctx


class VitalSignCreateView(LoginRequiredMixin, CreateView):
    model = VitalSign
    form_class = VitalSignForm
    success_url = reverse_lazy('vitals')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_permission(request.user, 'vitals', 'create'):
            log_access(request, 'access_denied', 'vitals', success=False)
            messages.error(request, 'Você não tem permissão para registrar sinais vitais.')
            return redirect('vitals')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.patient = self.request.user
        log_access(self.request, 'create', 'vitals')
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

    already_logged = request.user.is_authenticated
    ctx = {'already_logged': already_logged}

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

        if len(token_raw) <= 8:
            # código curto (8 chars exibidos ao paciente): compara com token_display
            token_upper = token_raw.upper()
            pending_sessions = list(ConsultationSession.objects.filter(status='pending'))
            _log.debug(
                'ENTRAR_ATENDIMENTO (código curto) | token=%r | sessões pendentes: %s',
                token_upper,
                [s.token_display for s in pending_sessions],
            )
            for s in pending_sessions:
                if s.token_display == token_upper:
                    session = s
                    break
            if session is None:
                messages.error(
                    request,
                    'Código não encontrado. Verifique o código na tela do paciente e tente novamente.',
                )
                return render(request, 'atendimento/entrar.html', {**ctx, 'already_logged': True})
        else:
            # UUID completo (fallback para quem copiar o código longo)
            try:
                uuid_obj = _uuid_module.UUID(token_raw)
            except (ValueError, AttributeError):
                messages.error(
                    request,
                    'Código inválido. Digite os 8 caracteres exibidos na tela do paciente.',
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

    # Histórico clínico anterior (somente leitura) — últimas 10 consultas
    historico_anterior = Consultation.objects.filter(
        patient=patient
    ).select_related('session').order_by('-date')[:10]

    # Perfil clínico permanente do paciente
    try:
        clinical_summary = patient.clinical_summary
    except PatientClinicalSummary.DoesNotExist:
        clinical_summary = None

    # Último sinal vital registrado
    ultimo_vital = VitalSign.objects.filter(patient=patient).order_by('-date', '-created_at').first()

    if request.method == 'POST':
        form = AtendimentoForm(request.POST)
        anamnese_form      = AnamneseForm(request.POST, prefix='anamnese')
        exames_form        = ExameLaboratorialForm(request.POST, prefix='exames')
        vitals_form        = VitalSignProfessionalForm(request.POST, prefix='vitais')
        intervention_form  = ClinicalInterventionForm(request.POST, prefix='interv')
        evolution_form     = ExpectedEvolutionForm(request.POST, prefix='evolucao')

        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.patient = patient
            consultation.professional_name = request.user.get_full_name() or request.user.username
            consultation.profession = request.user.profession
            consultation.specialty = request.user.professional_specialty or 'outro'
            consultation.save()
            _save_sub_forms(request, consultation, anamnese_form, exames_form)
            _handle_image_uploads(request, consultation)

            # Salva intervenção clínica se algum campo foi preenchido
            if intervention_form.is_valid():
                icd = intervention_form.cleaned_data
                if any(v for v in icd.values() if v):
                    interv = intervention_form.save(commit=False)
                    interv.consultation = consultation
                    interv.professional = request.user
                    interv.save()

            # Salva evolução esperada se algum campo foi preenchido
            if evolution_form.is_valid():
                ecd = evolution_form.cleaned_data
                if any(v for v in ecd.values() if v):
                    ev = evolution_form.save(commit=False)
                    ev.consultation = consultation
                    ev.professional = request.user
                    ev.save()

            # Salva sinais vitais apenas se ao menos um campo clínico foi preenchido
            if vitals_form.is_valid():
                cd = vitals_form.cleaned_data
                has_any_vital = any(
                    v is not None and v != '' and v is not False
                    for v in cd.values()
                )
                if has_any_vital:
                    vital = vitals_form.save(commit=False)
                    vital.patient = patient
                    vital.consultation = consultation
                    vital.recorded_by = request.user
                    vital.date = timezone.now().date()
                    vital.save()

            session.consultation = consultation
            session.status = 'closed'
            session.closed_at = timezone.now()
            session.save()

            # Cria vínculo clínico para RBAC
            try:
                from users.models import PatientProfessionalAccess
                ppa, _ = PatientProfessionalAccess.objects.get_or_create(
                    patient=patient,
                    professional=request.user,
                    defaults={
                        'granted_by': request.user,
                        'access_reason': 'Atendimento registrado via token',
                        'is_active': True,
                    }
                )
                if not ppa.is_active:
                    ppa.is_active = True
                    ppa.revoked_at = None
                    ppa.save(update_fields=['is_active', 'revoked_at'])
            except Exception as exc:
                _log.error('Falha ao criar vínculo clínico: professional=%s patient=%s erro=%s',
                           request.user.pk, patient.pk, exc)

            log_access(request, 'create', 'consultation', resource_id=consultation.pk, patient=patient)
            messages.success(request, f'Consulta de {patient.display_name} registrada com sucesso!')
            return redirect('consultation_detail', pk=consultation.pk)
    else:
        form               = AtendimentoForm(initial={'date': timezone.now().date()})
        anamnese_form      = AnamneseForm(prefix='anamnese')
        exames_form        = ExameLaboratorialForm(prefix='exames')
        vitals_form        = VitalSignProfessionalForm(prefix='vitais')
        intervention_form  = ClinicalInterventionForm(prefix='interv')
        evolution_form     = ExpectedEvolutionForm(prefix='evolucao')

    return render(request, 'atendimento/consulta.html', {
        'session':            session,
        'patient':            patient,
        'form':               form,
        'anamnese_form':      anamnese_form,
        'exames_form':        exames_form,
        'vitals_form':        vitals_form,
        'intervention_form':  intervention_form,
        'evolution_form':     evolution_form,
        'tab_choices':        ConsultationImage.TAB_CHOICES,
        'active_tab':         request.POST.get('active_tab', 'geral'),
        'professional':        request.user,
        'evaluation_label':    _evaluation_label(request.user),
        'diagnosis_label':     _diagnosis_label(request.user),
        'classification_hint': _classification_hint(request.user),
        'block1_label':        _block1_label(request.user),
        'block1_sublabel':     _block1_sublabel(request.user),
        'block2_label':        _block2_label(request.user),
        'block3_label':        _block3_label(request.user),
        'historico_anterior':  historico_anterior,
        'clinical_summary':   clinical_summary,
        'ultimo_vital':       ultimo_vital,
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


# ══════════════════════════════════════════════════════════════════════════════
# RECURSOS CLÍNICOS AVANÇADOS — com RBAC granular
# ══════════════════════════════════════════════════════════════════════════════

def _get_accessible_consultation(user, pk):
    """Atalho: busca consulta acessível ao usuário ou levanta 404."""
    return get_object_or_404(_accessible_consultations(user), pk=pk)


# ── Evoluções ─────────────────────────────────────────────────────────────────

@login_required
def evolution_list(request, consultation_pk):
    if not has_permission(request.user, 'evolution', 'view'):
        messages.error(request, 'Você não tem permissão para visualizar evoluções.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    qs = filter_evolutions_for_user(
        Evolution.objects.filter(consultation=consultation).select_related('professional'),
        request.user,
    )
    log_access(request, 'view', 'evolution', resource_id=consultation_pk, patient=consultation.patient)
    return render(request, 'consultations/evolution_list.html', {
        'consultation': consultation,
        'evolutions':   qs,
        'can_create':   has_permission(request.user, 'evolution', 'create') and
                        bool(get_evolution_create_category(request.user)),
    })


@login_required
def evolution_create(request, consultation_pk):
    if not has_permission(request.user, 'evolution', 'create'):
        messages.error(request, 'Você não tem permissão para registrar evoluções.')
        return redirect('consultation_list')

    cat = get_evolution_create_category(request.user)
    if not cat:
        messages.error(request, 'Seu perfil não permite criar evoluções clínicas.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)

    if request.method == 'POST':
        form = EvolutionForm(request.POST, user=request.user)
        if form.is_valid():
            ev = form.save(commit=False)
            ev.consultation = consultation
            ev.professional = request.user
            ev.category = cat   # garante a categoria correta independente do POST
            ev.save()
            log_access(request, 'create', 'evolution', resource_id=ev.pk, patient=consultation.patient)
            messages.success(request, 'Evolução registrada com sucesso.')
            return redirect('evolution_list', consultation_pk=consultation_pk)
    else:
        form = EvolutionForm(user=request.user)

    return render(request, 'consultations/evolution_form.html', {
        'form': form,
        'consultation': consultation,
        'titulo': 'Nova Evolução',
    })


@login_required
def evolution_edit(request, consultation_pk, pk):
    if not has_permission(request.user, 'evolution', 'edit'):
        messages.error(request, 'Você não tem permissão para editar evoluções.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    ev = get_object_or_404(Evolution, pk=pk, consultation=consultation, professional=request.user)

    if request.method == 'POST':
        form = EvolutionForm(request.POST, instance=ev, user=request.user)
        if form.is_valid():
            form.save()
            log_access(request, 'edit', 'evolution', resource_id=ev.pk, patient=consultation.patient)
            messages.success(request, 'Evolução atualizada.')
            return redirect('evolution_list', consultation_pk=consultation_pk)
    else:
        form = EvolutionForm(instance=ev, user=request.user)

    return render(request, 'consultations/evolution_form.html', {
        'form': form,
        'consultation': consultation,
        'titulo': 'Editar Evolução',
    })


# ── Prescrições ───────────────────────────────────────────────────────────────

@login_required
def prescription_list(request, consultation_pk):
    if not has_permission(request.user, 'prescription', 'view'):
        messages.error(request, 'Você não tem permissão para visualizar prescrições.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    prescriptions = Prescription.objects.filter(
        consultation=consultation
    ).select_related('prescriber').order_by('-created_at')

    log_access(request, 'view', 'prescription', resource_id=consultation_pk, patient=consultation.patient)
    return render(request, 'consultations/prescription_list.html', {
        'consultation': consultation,
        'prescriptions': prescriptions,
        'can_create': bool(get_prescription_allowed_types(request.user)),
    })


@login_required
def prescription_create(request, consultation_pk):
    allowed = get_prescription_allowed_types(request.user)
    if not has_permission(request.user, 'prescription', 'create') or not allowed:
        messages.error(request, 'Você não tem permissão para registrar prescrições.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST, user=request.user)
        if form.is_valid():
            pres = form.save(commit=False)
            pres.consultation = consultation
            pres.prescriber = request.user
            if pres.prescription_type not in allowed:
                messages.error(request, 'Tipo de prescrição não permitido para seu perfil.')
                return render(request, 'consultations/prescription_form.html',
                              {'form': form, 'consultation': consultation})
            pres.save()
            log_access(request, 'create', 'prescription', resource_id=pres.pk, patient=consultation.patient)
            messages.success(request, 'Prescrição registrada.')
            return redirect('prescription_list', consultation_pk=consultation_pk)
    else:
        form = PrescriptionForm(user=request.user)

    return render(request, 'consultations/prescription_form.html', {
        'form': form,
        'consultation': consultation,
        'titulo': 'Nova Prescrição',
    })


# ── Diagnósticos CID ──────────────────────────────────────────────────────────

@login_required
def diagnosis_list(request, consultation_pk):
    if not has_permission(request.user, 'diagnosis', 'view'):
        messages.error(request, 'Você não tem permissão para visualizar diagnósticos.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    diagnoses = DiagnosisCID.objects.filter(
        consultation=consultation
    ).select_related('professional').order_by('-is_primary', '-created_at')

    log_access(request, 'view', 'diagnosis', resource_id=consultation_pk, patient=consultation.patient)
    return render(request, 'consultations/diagnosis_list.html', {
        'consultation': consultation,
        'diagnoses':    diagnoses,
        'can_create':   has_permission(request.user, 'diagnosis', 'create'),
    })


@login_required
def diagnosis_create(request, consultation_pk):
    if not has_permission(request.user, 'diagnosis', 'create'):
        messages.error(request, 'Você não tem permissão para registrar diagnósticos.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)

    if request.method == 'POST':
        form = DiagnosisCIDForm(request.POST)
        if form.is_valid():
            diag = form.save(commit=False)
            diag.consultation = consultation
            diag.professional = request.user
            diag.save()
            log_access(request, 'create', 'diagnosis', resource_id=diag.pk, patient=consultation.patient)
            messages.success(request, f'Diagnóstico {diag.icd_code} registrado.')
            return redirect('diagnosis_list', consultation_pk=consultation_pk)
    else:
        form = DiagnosisCIDForm()

    return render(request, 'consultations/diagnosis_form.html', {
        'form': form,
        'consultation': consultation,
        'titulo': 'Novo Diagnóstico CID-10',
    })


# ── Exame Físico ──────────────────────────────────────────────────────────────

@login_required
def physical_exam_view(request, consultation_pk):
    if not has_permission(request.user, 'physical_exam', 'view'):
        messages.error(request, 'Você não tem permissão para visualizar o exame físico.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    exams = PhysicalExam.objects.filter(
        consultation=consultation
    ).select_related('professional').order_by('-created_at')

    can_create = has_permission(request.user, 'physical_exam', 'create')
    form = PhysicalExamForm() if can_create else None

    if request.method == 'POST' and can_create:
        form = PhysicalExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.consultation = consultation
            exam.professional = request.user
            exam.save()
            log_access(request, 'create', 'physical_exam', resource_id=exam.pk, patient=consultation.patient)
            messages.success(request, 'Exame físico registrado.')
            return redirect('physical_exam_view', consultation_pk=consultation_pk)

    log_access(request, 'view', 'physical_exam', resource_id=consultation_pk, patient=consultation.patient)
    return render(request, 'consultations/physical_exam.html', {
        'consultation': consultation,
        'exams':        exams,
        'form':         form,
        'can_create':   can_create,
    })


# ── Solicitações de Exame (Lab Requests) ──────────────────────────────────────

@login_required
def lab_request_list(request, consultation_pk):
    if not has_permission(request.user, 'lab_requests', 'view'):
        messages.error(request, 'Você não tem permissão para visualizar solicitações de exame.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    lab_reqs = LabRequest.objects.filter(
        consultation=consultation
    ).select_related('requesting_professional', 'result_registered_by').order_by('-created_at')

    log_access(request, 'view', 'lab_requests', resource_id=consultation_pk, patient=consultation.patient)
    return render(request, 'consultations/lab_request_list.html', {
        'consultation': consultation,
        'lab_requests': lab_reqs,
        'can_create':   has_permission(request.user, 'lab_requests', 'create'),
        'can_fill_result': request.user.role in ('BIOMEDICO', 'ADMIN') or request.user.is_superuser,
    })


@login_required
def lab_request_create(request, consultation_pk):
    if not has_permission(request.user, 'lab_requests', 'create'):
        messages.error(request, 'Você não tem permissão para solicitar exames.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)

    if request.method == 'POST':
        form = LabRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.consultation = consultation
            req.requesting_professional = request.user
            req.save()
            log_access(request, 'create', 'lab_requests', resource_id=req.pk, patient=consultation.patient)
            messages.success(request, f'Solicitação de "{req.exam_type}" registrada.')
            return redirect('lab_request_list', consultation_pk=consultation_pk)
    else:
        form = LabRequestForm()

    return render(request, 'consultations/lab_request_form.html', {
        'form': form,
        'consultation': consultation,
        'titulo': 'Solicitar Exame',
    })


@login_required
def meus_atendimentos(request):
    """
    Tela exclusiva do profissional — lista todas as consultas realizadas por ele,
    com filtro por paciente, data e especialidade.
    """
    if not _is_professional(request.user):
        return redirect('consultation_list')

    qs = Consultation.objects.filter(
        session__professional=request.user
    ).select_related('patient', 'session').order_by('-date')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(patient__first_name__icontains=q) |
            Q(patient__last_name__icontains=q) |
            Q(patient__username__icontains=q) |
            Q(patient__email__icontains=q) |
            Q(specialty__icontains=q) |
            Q(specialty_other__icontains=q) |
            Q(diagnosis__icontains=q)
        )

    specialty = request.GET.get('specialty', '').strip()
    if specialty:
        qs = qs.filter(specialty=specialty)

    date_from = request.GET.get('date_from', '').strip()
    date_to   = request.GET.get('date_to', '').strip()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    from .models import SPECIALTY_CHOICES
    return render(request, 'consultations/meus_atendimentos.html', {
        'consultations':   qs,
        'q':               q,
        'specialty':       specialty,
        'date_from':       date_from,
        'date_to':         date_to,
        'specialty_choices': SPECIALTY_CHOICES,
        'total':           qs.count(),
    })


@login_required
def patient_clinical_summary(request, consultation_pk):
    """Edição do perfil clínico permanente do paciente — acesso exclusivo para profissionais."""
    if not _is_professional(request.user):
        messages.error(request, 'Apenas profissionais podem editar o perfil clínico do paciente.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    patient = consultation.patient

    summary, _ = PatientClinicalSummary.objects.get_or_create(patient=patient)

    if request.method == 'POST':
        form = PatientClinicalSummaryForm(request.POST, instance=summary)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            log_access(request, 'edit', 'clinical_summary', resource_id=str(patient.pk), patient=patient)
            messages.success(request, 'Perfil clínico do paciente atualizado com sucesso.')
            return redirect('consultation_detail', pk=consultation_pk)
    else:
        form = PatientClinicalSummaryForm(instance=summary)

    return render(request, 'consultations/clinical_summary_form.html', {
        'form':         form,
        'consultation': consultation,
        'patient':      patient,
    })


@login_required
def lab_result_fill(request, consultation_pk, pk):
    """Preenchimento de resultado — exclusivo para Biomédico e Admin."""
    if request.user.role not in ('BIOMEDICO', 'ADMIN') and not request.user.is_superuser:
        log_access(request, 'access_denied', 'lab_requests', success=False)
        messages.error(request, 'Apenas biomédicos podem registrar resultados de exames.')
        return redirect('consultation_list')

    consultation = _get_accessible_consultation(request.user, consultation_pk)
    lab_req = get_object_or_404(LabRequest, pk=pk, consultation=consultation)

    if request.method == 'POST':
        form = LabResultForm(request.POST, instance=lab_req)
        if form.is_valid():
            result = form.save(commit=False)
            result.result_registered_by = request.user
            result.save()
            log_access(request, 'edit', 'lab_requests', resource_id=lab_req.pk, patient=consultation.patient)
            messages.success(request, 'Resultado registrado com sucesso.')
            return redirect('lab_request_list', consultation_pk=consultation_pk)
    else:
        form = LabResultForm(instance=lab_req)

    return render(request, 'consultations/lab_result_form.html', {
        'form': form,
        'consultation': consultation,
        'lab_request': lab_req,
        'titulo': f'Resultado — {lab_req.exam_type}',
    })
