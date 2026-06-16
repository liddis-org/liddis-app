"""
Utilitário de auditoria LGPD.
Registra acessos e ações sensíveis no modelo AuditLog.
"""
import logging

_log = logging.getLogger('liddis')


def _get_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_access(
    request,
    action: str,
    resource_type: str,
    resource_id: str = '',
    patient=None,
    success: bool = True,
    detail: dict | None = None,
    actor=None,
):
    """
    Grava um registro de auditoria de forma não-bloqueante.
    Falhas de gravação são logadas mas não propagadas.

    `actor` é opcional — por padrão é derivado de `request.user`. Necessário
    informar explicitamente no logout, pois `request.user` já foi resetado
    para AnonymousUser quando o signal `user_logged_out` é disparado.
    """
    try:
        from users.models import AuditLog

        if actor is None:
            actor = request.user if request.user.is_authenticated else None

        AuditLog.objects.create(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            patient=patient,
            ip_address=_get_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
            success=success,
            detail=detail or {},
        )
    except Exception as exc:
        _log.error('audit_log_failed | action=%s | resource=%s | erro=%s', action, resource_type, exc)
