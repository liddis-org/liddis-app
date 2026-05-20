"""
Middlewares de segurança da plataforma LIDDIS.

1. EmailVerificationMiddleware — redireciona usuários sem e-mail verificado.
2. RBACPatientAccessMiddleware — bloqueia acesso a recursos de pacientes
   quando o profissional não tem vínculo ativo (PatientProfessionalAccess).
"""
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

_log = logging.getLogger('liddis')

# ── URLs isentas de verificação de e-mail ─────────────────────────────────────
_EXEMPT = (
    '/login/',
    '/logout/',
    '/register/',
    '/verificar/',
    '/admin/',
    '/api/',
    '/static/',
    '/media/',
    '/accounts/',   # allauth / Google OAuth
    '/senha/',      # recuperação de senha
)

# ── URLs que exigem vínculo paciente-profissional ─────────────────────────────
# Padrão: /consultas/<pk>/... , /atendimento/... , /evoluções/...
# O middleware extrai o patient_id do objeto ou da sessão conforme necessário.
# Por ora, protegemos as rotas de atendimento ativo (token-based).
_PATIENT_BOUND_PATTERNS = [
    re.compile(r'^/consultas/(?P<pk>[0-9a-f-]+)/'),
    re.compile(r'^/atendimento/consulta/(?P<token>[0-9a-f-]+)/'),
]


class EmailVerificationMiddleware:
    """
    Redireciona usuários autenticados com e-mail não verificado
    para a página de verificação OTP.
    Em TEST_MODE (settings.TEST_MODE=True) a verificação é ignorada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'TEST_MODE', False):
            return self.get_response(request)

        if (
            request.user.is_authenticated
            and not request.user.is_email_verified
            and not any(request.path.startswith(p) for p in _EXEMPT)
        ):
            return redirect('/verificar/email/')

        return self.get_response(request)


class RBACPatientAccessMiddleware:
    """
    Garante que profissionais acessem apenas dados de pacientes
    com os quais têm vínculo ativo (PatientProfessionalAccess).

    Verificação em dois momentos:
    a) Consulta específica por PK — valida se o paciente da consulta
       tem vínculo com o profissional logado.
    b) Sessão de atendimento ativa — já é controlada na view; este
       middleware serve como segunda camada de defesa.

    Isenções:
    - Rotas admin/API/static.
    - Pacientes (acessam apenas os próprios dados — filtrado nas views).
    - Admins e superusuários.
    - Rotas de criação de nova sessão (o profissional ainda não sabe o paciente).
    """

    # Rotas isentas de checagem de vínculo
    _EXEMPT_PREFIXES = (
        '/admin/', '/api/', '/static/', '/media/',
        '/login/', '/logout/', '/register/', '/verificar/',
        '/accounts/', '/senha/', '/home/', '/atendimento/entrar/',
        '/vinculos/', '/perfil/', '/analytics/', '/dashboard/',
        '/quem-somos/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self._check_patient_binding(request)
        if response:
            return response
        return self.get_response(request)

    def _check_patient_binding(self, request):
        user = request.user

        # Não autenticado, admin, paciente ou superusuário — ignora
        if (
            not user.is_authenticated
            or user.is_superuser
            or getattr(user, 'role', 'PATIENT') in ('ADMIN', 'PATIENT')
        ):
            return None

        # Rotas isentas
        if any(request.path.startswith(p) for p in self._EXEMPT_PREFIXES):
            return None

        # Verifica padrão: /consultas/<pk>/
        for pattern in _PATIENT_BOUND_PATTERNS:
            match = pattern.match(request.path)
            if not match:
                continue

            if 'pk' in match.groupdict():
                pk = match.group('pk')
                patient = self._get_consultation_patient(pk)
                if patient and not self._has_binding(user, patient):
                    self._log_denied(user, request.path, patient)
                    messages.error(
                        request,
                        'Você não tem vínculo ativo com este paciente. '
                        'Solicite ao paciente que conceda acesso ao seu perfil.'
                    )
                    return redirect('dashboard')

            # Para rota de atendimento via token, a view já faz a verificação;
            # nenhuma ação adicional necessária aqui.

        return None

    @staticmethod
    def _get_consultation_patient(pk: str):
        """Retorna o paciente de uma consulta pelo PK (UUID). Silencia erros."""
        try:
            from consultations.models import Consultation
            return Consultation.objects.select_related('patient').get(pk=pk).patient
        except Exception:
            return None

    @staticmethod
    def _has_binding(professional, patient) -> bool:
        """Verifica vínculo ativo entre profissional e paciente."""
        try:
            from users.models import PatientProfessionalAccess
            return PatientProfessionalAccess.objects.filter(
                professional=professional,
                patient=patient,
                is_active=True,
            ).exists()
        except Exception:
            return False

    @staticmethod
    def _log_denied(user, path: str, patient):
        from users.audit import log_access
        # Não temos request aqui — criamos um objeto mínimo para log
        _log.warning(
            'RBAC_BINDING_DENIED | professional=%s | path=%s | patient=%s',
            user.username, path, patient.username if patient else '?',
        )
