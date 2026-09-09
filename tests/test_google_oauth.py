"""
Testes do login com Google (django-allauth).

Este fluxo já quebrou mais de uma vez, sempre no mesmo ponto: a vinculação
entre a conta Google e o usuário existente. Os testes abaixo cobrem cada
cenário de vinculação isoladamente, incluindo os casos de falha que antes
passavam despercebidos porque o login "funcionava" naquela tentativa e
quebrava na seguinte.
"""
import pytest
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse

from allauth.socialaccount.models import SocialAccount, SocialLogin


# ═══════════════════════════════════════════════════════════════════════════════
# Infraestrutura
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def request_com_sessao():
    """Request real o suficiente para o adapter — precisa de sessão e messages."""
    req = RequestFactory().get('/accounts/google/login/callback/')
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    MessageMiddleware(lambda r: None).process_request(req)
    return req


@pytest.fixture
def adapter():
    from users.adapters import CustomSocialAccountAdapter
    return CustomSocialAccountAdapter()


def _sociallogin(email, uid, first_name='Fulano', user=None):
    """
    Monta o SocialLogin como o allauth entrega ao pre_social_login quando
    ainda não encontrou vínculo pelo uid: usuário em memória, sem pk.
    """
    from users.models import CustomUser
    if user is None:
        user = CustomUser(email=email, first_name=first_name)
    conta = SocialAccount(
        provider='google',
        uid=uid,
        extra_data={'email': email, 'given_name': first_name},
    )
    return SocialLogin(user=user, account=conta)


@pytest.fixture
def usuario_por_email(db):
    """Usuário que se cadastrou por e-mail e senha, sem Google."""
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='maria_email', email='maria@exemplo.com', password='Senha@1234',
        first_name='Maria', last_name='Souza', role='PATIENT',
        is_email_verified=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Vinculação de conta Google a usuário que já existe por e-mail
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVinculacaoPorEmail:

    def test_vincula_google_a_conta_existente(self, adapter, request_com_sessao, usuario_por_email):
        sl = _sociallogin(usuario_por_email.email, uid='900000000000000000001')
        adapter.pre_social_login(request_com_sessao, sl)

        assert sl.user.pk == usuario_por_email.pk, \
            'Deveria reaproveitar a conta existente em vez de criar outra'
        assert SocialAccount.objects.filter(
            user=usuario_por_email, provider='google'
        ).exists(), 'Vínculo Google não foi persistido'

    def test_email_com_caixa_diferente_encontra_a_mesma_conta(
        self, adapter, request_com_sessao, usuario_por_email
    ):
        sl = _sociallogin('MARIA@Exemplo.COM', uid='900000000000000000002')
        adapter.pre_social_login(request_com_sessao, sl)
        assert sl.user.pk == usuario_por_email.pk

    def test_google_marca_email_como_verificado(
        self, adapter, request_com_sessao, usuario_por_email
    ):
        assert usuario_por_email.is_email_verified is False
        sl = _sociallogin(usuario_por_email.email, uid='900000000000000000003')
        adapter.pre_social_login(request_com_sessao, sl)
        usuario_por_email.refresh_from_db()
        assert usuario_por_email.is_email_verified is True

    def test_falha_ao_notificar_nao_impede_a_vinculacao(
        self, adapter, request_com_sessao, usuario_por_email, monkeypatch
    ):
        """
        connect() dispara e-mail de notificação. Se o envio falha, a exceção
        não pode custar o vínculo: sem o SocialAccount gravado, o login
        seguinte repete o mesmo caminho frágil indefinidamente — foi assim
        que o problema voltou depois de "corrigido".
        """
        def connect_quebrado(self, request, user):
            raise RuntimeError('SMTP indisponível')

        monkeypatch.setattr(SocialLogin, 'connect', connect_quebrado)

        sl = _sociallogin(usuario_por_email.email, uid='900000000000000000004')
        adapter.pre_social_login(request_com_sessao, sl)

        assert sl.user.pk == usuario_por_email.pk, 'Login deveria prosseguir'
        assert SocialAccount.objects.filter(
            user=usuario_por_email, provider='google', uid='900000000000000000004'
        ).exists(), (
            'Vínculo perdido por causa da notificação. No próximo login o allauth '
            'não encontrará o uid e repetirá o mesmo caminho.'
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Re-login — o cenário que quebrou em produção
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRelogin:

    def test_uid_dessincronizado_e_corrigido(self, adapter, request_com_sessao, usuario_por_email):
        SocialAccount.objects.create(
            user=usuario_por_email, provider='google',
            uid='111111111111111111111', extra_data={},
        )
        sl = _sociallogin(usuario_por_email.email, uid='222222222222222222222')
        adapter.pre_social_login(request_com_sessao, sl)

        contas = SocialAccount.objects.filter(user=usuario_por_email, provider='google')
        assert contas.count() == 1, 'Não pode duplicar SocialAccount ao ressincronizar'
        assert contas.first().uid == '222222222222222222222', 'uid não foi atualizado'
        assert sl.user.pk == usuario_por_email.pk

    def test_logins_consecutivos_nao_duplicam_vinculo(
        self, adapter, request_com_sessao, usuario_por_email
    ):
        for _ in range(3):
            sl = _sociallogin(usuario_por_email.email, uid='900000000000000000005')
            adapter.pre_social_login(request_com_sessao, sl)

        assert SocialAccount.objects.filter(
            user=usuario_por_email, provider='google'
        ).count() == 1
        from users.models import CustomUser
        assert CustomUser.objects.filter(email__iexact=usuario_por_email.email).count() == 1

    def test_conta_ja_vinculada_prossegue_sem_alteracao(
        self, adapter, request_com_sessao, usuario_por_email
    ):
        SocialAccount.objects.create(
            user=usuario_por_email, provider='google',
            uid='333333333333333333333', extra_data={},
        )
        sl = _sociallogin(usuario_por_email.email, uid='333333333333333333333',
                          user=usuario_por_email)
        adapter.pre_social_login(request_com_sessao, sl)
        assert SocialAccount.objects.filter(user=usuario_por_email).count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Casos de borda que derrubavam o login com erro 500
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCasosDeBorda:

    def test_conta_google_totalmente_nova_segue_o_fluxo_padrao(self, adapter, request_com_sessao):
        sl = _sociallogin('novo@exemplo.com', uid='900000000000000000006')
        adapter.pre_social_login(request_com_sessao, sl)
        assert sl.user.pk is None, 'Usuário novo deve ser criado pelo allauth, não aqui'

    def test_login_sem_email_nao_quebra(self, adapter, request_com_sessao):
        sl = _sociallogin('', uid='900000000000000000007')
        adapter.pre_social_login(request_com_sessao, sl)  # não deve levantar

    def test_emails_duplicados_no_banco_nao_derrubam_o_login(
        self, adapter, request_com_sessao, usuario_por_email
    ):
        """
        Duas contas com o mesmo e-mail em caixas diferentes fazem o get()
        levantar MultipleObjectsReturned. Sem tratamento, o usuário recebe
        erro 500 no meio do OAuth.
        """
        from users.models import CustomUser
        CustomUser.objects.create_user(
            username='maria_dup', email='MARIA@exemplo.com', password='Senha@1234',
            role='PATIENT',
        )
        sl = _sociallogin('maria@exemplo.com', uid='900000000000000000008')
        adapter.pre_social_login(request_com_sessao, sl)  # não deve levantar
        assert sl.user.pk is not None, 'Deveria escolher uma das contas e prosseguir'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Geração de username
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUsername:

    def test_username_derivado_do_email_e_unico(self):
        from users.adapters import CustomAccountAdapter
        from users.models import CustomUser

        CustomUser.objects.create_user(username='joao_silva', email='outro@x.com',
                                       password='Senha@1234')
        ad = CustomAccountAdapter()
        u = CustomUser(email='joao.silva@gmail.com')
        ad.populate_username(None, u)

        assert u.username, 'username não foi gerado'
        assert u.username != 'joao_silva', 'colidiu com username já existente'
        assert not CustomUser.objects.filter(username=u.username).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Rotas do fluxo OAuth
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRotasOAuth:

    def test_pagina_de_login_oferece_entrada_com_google(self, client):
        resp = client.get(reverse('login'))
        assert resp.status_code == 200
        assert b'google' in resp.content.lower(), \
            'Página de login sem opção de entrar com Google'

    def test_post_redireciona_para_o_google(self, client):
        resp = client.post('/accounts/google/login/')
        assert resp.status_code == 302
        assert 'accounts.google.com' in resp['Location']

    def test_redirect_uri_aponta_para_o_dominio_do_site(self, client, settings):
        from urllib.parse import urlparse, parse_qs
        resp = client.post('/accounts/google/login/')
        q = parse_qs(urlparse(resp['Location']).query)
        uri = q['redirect_uri'][0]
        assert uri.endswith('/accounts/google/login/callback/'), f'redirect_uri inesperado: {uri}'
        assert 'run.app' not in uri, \
            'redirect_uri aponta para o Cloud Run — o Google recusa por não estar registrado'
