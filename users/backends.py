from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import CustomUser


class TestModeBackend(ModelBackend):
    """
    Backend de teste: aceita qualquer senha quando TEST_MODE=True E DEBUG=True.

    Ative em .env com:
        TEST_MODE=True

    NUNCA disponível em produção (DEBUG=False sempre o desativa).
    Remove TEST_MODE=True do .env antes de subir para produção.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        from django.conf import settings
        if not (getattr(settings, 'TEST_MODE', False) and settings.DEBUG):
            return None
        if not username:
            return None
        try:
            user = CustomUser.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )
        except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
            return None
        if self.user_can_authenticate(user):
            return user
        return None


class EmailOrUsernameBackend(ModelBackend):
    """
    Permite login usando e-mail OU username.
    Compatível com o LoginView padrão do Django (campo 'username' do formulário).
    Se o valor digitado contiver '@', busca por e-mail; senão, por username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            user = CustomUser.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )
        except CustomUser.DoesNotExist:
            # Executa hash dummy para evitar timing attack
            CustomUser().set_password(password)
            return None
        except CustomUser.MultipleObjectsReturned:
            # Situação improvável (email é unique), mas tratada com segurança
            user = CustomUser.objects.filter(email__iexact=username).first()
            if not user:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
