import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.utils import user_email, user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

logger = logging.getLogger('liddis')


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Adapter padrão do allauth com customizações mínimas:
    - Redireciona para /dashboard/ após login.
    - Gera username a partir do e-mail (para fluxos sociais).
    """

    def get_login_redirect_url(self, request):
        return settings.LOGIN_REDIRECT_URL

    def populate_username(self, request, user):
        """
        Gera username único baseado no e-mail quando o campo não é informado.
        Usado principalmente no signup via Google.
        """
        email = user_email(user)
        if email:
            base = email.split('@')[0].replace('.', '_').replace('+', '_')
            base = base[:25]  # margem para sufixo numérico
            candidate = base
            counter = 1
            from .models import CustomUser
            while CustomUser.objects.filter(username=candidate).exists():
                candidate = f'{base}{counter}'
                counter += 1
            user_username(user, candidate)
        else:
            super().populate_username(request, user)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter social com duas responsabilidades principais:
    1. Vincular conta Google a um usuário existente pelo mesmo e-mail
       (evita contas duplicadas).
    2. Marcar is_email_verified=True para usuários criados/vinculados via Google
       (Google já faz a verificação).
    """

    def pre_social_login(self, request, sociallogin):
        """
        Chamado após autenticação no Google, antes de criar/logar o usuário.
        Se já existir um usuário com aquele e-mail, vincula a conta social
        à conta existente em vez de criar uma nova.
        """
        # Conta social já associada → nada a fazer
        if sociallogin.is_existing:
            return

        email = getattr(sociallogin.user, 'email', '') or ''
        if not email:
            return

        from .models import CustomUser
        try:
            existing = CustomUser.objects.get(email__iexact=email)
            # Vincula conta Google ao usuário existente
            sociallogin.connect(request, existing)
            # Aproveita para marcar e-mail como verificado
            if not existing.is_email_verified:
                existing.is_email_verified = True
                existing.save(update_fields=['is_email_verified'])
                logger.info('E-mail verificado via Google OAuth: %s', email)
        except CustomUser.DoesNotExist:
            pass  # Usuário novo — será criado normalmente pelo allauth

    def save_user(self, request, sociallogin, form=None):
        """
        Chamado ao criar um novo usuário via login social.
        Garante que is_email_verified=True (Google já verificou).
        """
        user = super().save_user(request, sociallogin, form)
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
        logger.info('Novo usuário criado via Google OAuth: %s', user.email)
        return user
