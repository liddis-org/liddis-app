"""
Auditoria LGPD de autenticação — registra login, logout e tentativas falhas.

Conectado via signals do Django em vez de chamado em cada view, para cobrir
uniformemente login normal e Google OAuth (allauth chama django.contrib.auth.login()
internamente, disparando o mesmo signal).
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import log_access


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    log_access(request, 'login', 'session', resource_id=str(user.pk))


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    log_access(request, 'logout', 'session', resource_id=str(user.pk), actor=user)


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    attempted = credentials.get('username') or credentials.get('email') or ''
    log_access(
        request, 'login', 'session',
        resource_id=attempted[:100],
        success=False,
        detail={'attempted_username': attempted},
    )
