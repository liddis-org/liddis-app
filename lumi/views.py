import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import LumiService, LumiServiceError

logger = logging.getLogger(__name__)

_lumi_service = LumiService()


@login_required
def lumi_page(request):
    """Página informativa da LUMI."""
    from users.permissions import has_lumi_access
    return render(request, 'lumi/index.html', {
        'is_professional': request.user.role != 'PATIENT',
        'has_lumi_access': has_lumi_access(request.user),
    })


@login_required
@require_POST
def lumi_report(request):
    """
    Endpoint AJAX que gera o relatório da LUMI.

    Paciente: gera relatório sobre si mesmo.
    Profissional: gera relatório sobre um paciente vinculado.

    Retorna JSON: {report, generated_at} ou {error}.
    """
    from users.permissions import has_lumi_access
    if not has_lumi_access(request.user):
        return JsonResponse({'error': 'Acesso à LUMI não disponível no seu plano atual. Entre em contato para ativar.'}, status=403)

    user = request.user
    is_professional = user.role != 'PATIENT'

    if is_professional:
        patient = _resolve_professional_patient(request, user)
        if patient is None:
            return JsonResponse({'error': 'Paciente não encontrado ou sem vínculo ativo.'}, status=403)
    else:
        patient = user

    # Consulta ativa (durante atendimento): profissional passa consultation_id
    consultation = None
    if is_professional:
        try:
            body = json.loads(request.body)
            consultation_id = body.get('consultation_id')
            if consultation_id:
                from consultations.models import Consultation
                import uuid
                consultation = Consultation.objects.filter(
                    pk=uuid.UUID(str(consultation_id)),
                    session__professional=request.user,
                ).first()
        except Exception:
            pass  # consultation permanece None

    try:
        report_text = _lumi_service.generate_report(patient, is_professional, consultation=consultation)
    except LumiServiceError as exc:
        return JsonResponse({'error': str(exc)}, status=503)

    from django.utils import timezone
    return JsonResponse({
        'report': report_text,
        'patient_name': patient.display_name,
        'generated_at': timezone.now().strftime('%d/%m/%Y às %H:%M'),
    })


def _resolve_professional_patient(request, professional):
    """
    Extrai e valida o paciente solicitado pelo profissional.
    Exige vínculo ativo em PatientProfessionalAccess.
    """
    try:
        body = json.loads(request.body)
        patient_id = body.get('patient_id', '')
    except (json.JSONDecodeError, ValueError):
        return None

    if not patient_id:
        return None

    from django.contrib.auth import get_user_model
    from users.models import PatientProfessionalAccess

    User = get_user_model()

    try:
        patient = User.objects.get(pk=patient_id, role='PATIENT')
    except (User.DoesNotExist, Exception):
        return None

    has_access = PatientProfessionalAccess.objects.filter(
        patient=patient,
        professional=professional,
        is_active=True,
    ).exists()

    return patient if has_access else None
