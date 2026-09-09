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
        Chamado após a autenticação no Google, antes de criar ou logar o usuário.

        Se já existir usuário com aquele e-mail, a conta Google é vinculada a ele
        em vez de gerar uma conta duplicada. Toda consulta aqui usa `filter().first()`
        em vez de `get()`: um `MultipleObjectsReturned` no meio do OAuth derruba o
        login com erro 500, e o estado do banco não é algo que este caminho possa
        pressupor íntegro.
        """
        if sociallogin.is_existing:
            self._marcar_email_verificado(sociallogin.user)
            return

        email = (getattr(sociallogin.user, 'email', None) or '').strip()
        if not email:
            return  # sem e-mail não há como casar com conta existente

        usuario = self._usuario_por_email(email)
        if usuario is None:
            return  # usuário genuinamente novo — allauth cria normalmente

        conta = self._conta_social_do_usuario(usuario, sociallogin.account.provider)
        if conta is not None:
            self._ressincronizar(conta, sociallogin, email)
        else:
            self._vincular(request, sociallogin, usuario, email)

        self._marcar_email_verificado(usuario)

    # ── Auxiliares ────────────────────────────────────────────────────────────

    @staticmethod
    def _usuario_por_email(email):
        """Conta mais antiga com este e-mail, ou None."""
        from .models import CustomUser

        contas = CustomUser.objects.filter(email__iexact=email).order_by('pk')
        primeira = contas.first()
        if primeira is not None and contas.count() > 1:
            logger.error(
                'Google OAuth: %d contas com o e-mail %s — usando a mais antiga (id=%s). '
                'Consolidar as duplicatas.',
                contas.count(), email, primeira.pk,
            )
        return primeira

    @staticmethod
    def _conta_social_do_usuario(usuario, provider):
        """SocialAccount mais antigo deste usuário no provider, ou None."""
        from allauth.socialaccount.models import SocialAccount

        contas = SocialAccount.objects.filter(user=usuario, provider=provider).order_by('pk')
        primeira = contas.first()
        if primeira is not None and contas.count() > 1:
            logger.error(
                'Google OAuth: usuário %s tem %d contas %s vinculadas — usando id=%s.',
                usuario.pk, contas.count(), provider, primeira.pk,
            )
        return primeira

    @staticmethod
    def _ressincronizar(conta, sociallogin, email):
        """
        O vínculo existe mas o allauth não o achou pelo uid — o uid divergiu.
        Atualizá-lo faz os próximos logins caírem no caminho rápido.
        """
        campos = []
        if conta.uid != sociallogin.account.uid:
            logger.warning(
                'Google OAuth: uid dessincronizado para %s (BD=%s → Google=%s) — corrigindo',
                email, conta.uid, sociallogin.account.uid,
            )
            conta.uid = sociallogin.account.uid
            campos.append('uid')
        if conta.extra_data != sociallogin.account.extra_data:
            conta.extra_data = sociallogin.account.extra_data
            campos.append('extra_data')
        if campos:
            conta.save(update_fields=campos)

        sociallogin.account = conta
        sociallogin.user = conta.user
        logger.info('Google re-login: vínculo reaproveitado para %s', email)

    @staticmethod
    def _vincular(request, sociallogin, usuario, email):
        """
        Primeira vinculação entre a conta Google e o usuário existente.

        `connect()` também dispara e-mail de notificação, e já falhou em produção
        por indisponibilidade de SMTP. O vínculo não pode depender disso: sem o
        SocialAccount gravado, o login seguinte não encontra o uid, recai neste
        mesmo caminho e falha de novo — foi assim que o problema voltou depois de
        dado como corrigido. Por isso a gravação é garantida à parte.
        """
        from allauth.socialaccount.models import SocialAccount

        try:
            sociallogin.connect(request, usuario)
            logger.info('Google: conta vinculada ao usuário existente %s', email)
            return
        except Exception as exc:
            logger.warning(
                'Google OAuth: connect() falhou com %s (%s) — gravando o vínculo '
                'diretamente; verificar configuração de e-mail.',
                type(exc).__name__, exc,
            )

        conta, criada = SocialAccount.objects.get_or_create(
            provider=sociallogin.account.provider,
            uid=sociallogin.account.uid,
            defaults={'user': usuario, 'extra_data': sociallogin.account.extra_data},
        )
        if conta.user_id != usuario.pk:
            conta.user = usuario
            conta.save(update_fields=['user'])

        sociallogin.account = conta
        sociallogin.user = usuario
        logger.info(
            'Google: vínculo %s para %s após falha na notificação',
            'criado' if criada else 'reaproveitado', email,
        )

    @staticmethod
    def _marcar_email_verificado(usuario):
        """O Google já validou o endereço — não exigimos o OTP próprio de novo."""
        if usuario and usuario.pk and not usuario.is_email_verified:
            usuario.is_email_verified = True
            usuario.save(update_fields=['is_email_verified'])
            logger.info('is_email_verified → True via Google OAuth: %s', usuario.email)

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

    def authentication_error(self, request, provider_id, error=None,
                             exception=None, extra_context=None):
        """
        Único ponto onde uma falha de OAuth fica visível: quando ela ocorre não
        há sessão nem usuário, então nada disso aparece na auditoria de login.
        Sem este registro, o sintoma que chega é "o login com Google não
        funciona", sem indicação de qual etapa falhou.

        Registra apenas identificadores e tipos de erro — nunca o code, o state,
        o id_token ou qualquer credencial, que trafegam nesta mesma requisição.
        """
        etapa = 'callback' if 'callback' in request.path else 'authorize'
        contexto = extra_context or {}

        logger.error(
            'oauth_falha | provider=%s | etapa=%s | erro=%s | excecao=%s | '
            'motivo=%s | ambiente=%s | path=%s',
            provider_id,
            etapa,
            error or 'nao_informado',
            type(exception).__name__ if exception else 'nenhuma',
            # 'access_denied' aqui significa que a pessoa cancelou no Google —
            # esperado, e não deve ser confundido com defeito do sistema.
            contexto.get('error_reason') or contexto.get('error') or 'nao_informado',
            'desenvolvimento' if settings.DEBUG else 'producao',
            request.path,
        )

        try:
            from .audit import log_access
            log_access(
                request, 'login', 'oauth',
                resource_id=provider_id,
                success=False,
                detail={
                    'etapa': etapa,
                    'erro': str(error or 'nao_informado')[:120],
                    'excecao': type(exception).__name__ if exception else None,
                },
            )
        except Exception as exc:      # auditoria nunca pode agravar a falha
            logger.warning('oauth_falha: auditoria nao registrada (%s)', exc)

        return super().authentication_error(
            request, provider_id, error=error,
            exception=exception, extra_context=extra_context,
        )
