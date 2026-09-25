"""
Rotinas diárias de retenção.

Estes comandos apagam e alteram dados sozinhos, todo dia, sem ninguém olhando.
Por isso o que mais importa aqui não é o que eles removem — é o que se recusam
a remover: conta com registro clínico e atendimento que ainda pode estar em
preenchimento.
"""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone


def _rodar(comando, **kwargs):
    saida = StringIO()
    call_command(comando, stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


@pytest.fixture
def conta_bot(db):
    """Cadastro automatizado: nunca verificou e nunca usou nada."""
    from users.models import CustomUser
    u = CustomUser.objects.create_user(
        username='bot_x', email='bot@spam.test', password='Senha@1234',
        role='PATIENT', is_email_verified=False,
    )
    CustomUser.objects.filter(pk=u.pk).update(
        date_joined=timezone.now() - timedelta(days=10))
    u.refresh_from_db()
    return u


@pytest.fixture
def conta_real(db):
    """Não verificou o e-mail, mas tem registro clínico."""
    from users.models import CustomUser
    u = CustomUser.objects.create_user(
        username='pac_real', email='real@test.com', password='Senha@1234',
        role='PATIENT', is_email_verified=False,
    )
    CustomUser.objects.filter(pk=u.pk).update(
        date_joined=timezone.now() - timedelta(days=10))
    u.refresh_from_db()
    return u


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Contas não verificadas
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLimpezaDeContas:

    def test_sem_execute_nao_apaga_nada(self, conta_bot):
        from users.models import CustomUser
        saida = _rodar('clean_unverified_users', hours=48)
        assert 'AUDITORIA' in saida
        assert CustomUser.objects.filter(pk=conta_bot.pk).exists(), \
            'Comando apagou sem --execute'

    def test_com_execute_remove_o_cadastro_abandonado(self, conta_bot):
        from users.models import CustomUser
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert not CustomUser.objects.filter(pk=conta_bot.pk).exists()

    def test_preserva_conta_com_consulta(self, conta_real):
        """
        Apagar o usuário levaria junto, por CASCADE, a consulta e seus anexos.
        Numa rotina automática isso seria perda de dado clínico.
        """
        from users.models import CustomUser
        from consultations.models import Consultation

        Consultation.objects.create(
            patient=conta_real, date='2026-08-10', professional_name='Dr. Teste',
            profession='Médico', specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
            status='active', severity='low',
        )
        _rodar('clean_unverified_users', hours=48, execute=True)

        assert CustomUser.objects.filter(pk=conta_real.pk).exists(), \
            'Conta com consulta foi removida pela rotina'
        assert Consultation.objects.filter(patient=conta_real).exists()

    def test_preserva_conta_com_sinal_vital(self, conta_real):
        from users.models import CustomUser
        from consultations.models import VitalSign

        VitalSign.objects.create(patient=conta_real, date=timezone.localdate())
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert CustomUser.objects.filter(pk=conta_real.pk).exists()

    def test_preserva_conta_com_sessao_de_atendimento(self, conta_real):
        from users.models import CustomUser
        from consultations.models import ConsultationSession

        ConsultationSession.objects.create(patient=conta_real)
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert CustomUser.objects.filter(pk=conta_real.pk).exists()

    def test_nao_toca_em_conta_verificada(self, db):
        from users.models import CustomUser
        u = CustomUser.objects.create_user(
            username='ok', email='ok@test.com', password='Senha@1234',
            role='PATIENT', is_email_verified=True,
        )
        CustomUser.objects.filter(pk=u.pk).update(
            date_joined=timezone.now() - timedelta(days=30))
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert CustomUser.objects.filter(pk=u.pk).exists()

    def test_nao_toca_em_conta_recente(self, db):
        """Quem acabou de se cadastrar ainda vai confirmar o e-mail."""
        from users.models import CustomUser
        u = CustomUser.objects.create_user(
            username='novo', email='novo@test.com', password='Senha@1234',
            role='PATIENT', is_email_verified=False,
        )
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert CustomUser.objects.filter(pk=u.pk).exists()

    def test_nao_toca_em_superusuario(self, db):
        from users.models import CustomUser
        u = CustomUser.objects.create_superuser(
            username='raiz', email='raiz@test.com', password='Senha@1234',
        )
        CustomUser.objects.filter(pk=u.pk).update(
            is_email_verified=False, date_joined=timezone.now() - timedelta(days=30))
        _rodar('clean_unverified_users', hours=48, execute=True)
        assert CustomUser.objects.filter(pk=u.pk).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Sessões de atendimento vencidas
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_s', email='pac_s@test.com', password='Senha@1234',
        role='PATIENT', is_email_verified=True,
    )


def _sessao(paciente, status, vencida_ha_horas):
    from consultations.models import ConsultationSession
    s = ConsultationSession.objects.create(
        patient=paciente,
        expires_at=timezone.now() - timedelta(hours=vencida_ha_horas),
    )
    ConsultationSession.objects.filter(pk=s.pk).update(status=status)
    s.refresh_from_db()
    return s


@pytest.mark.django_db
class TestSessoesVencidas:

    def test_sem_execute_nao_altera(self, paciente):
        from consultations.models import ConsultationSession
        s = _sessao(paciente, 'pending', 48)
        saida = _rodar('expirar_sessoes')
        assert 'AUDITORIA' in saida
        s.refresh_from_db()
        assert s.status == 'pending'

    def test_encerra_codigo_nunca_usado_e_vencido(self, paciente):
        s = _sessao(paciente, 'pending', 48)
        _rodar('expirar_sessoes', execute=True)
        s.refresh_from_db()
        assert s.status == 'expired'

    def test_nao_encerra_codigo_dentro_da_validade(self, paciente):
        from consultations.models import ConsultationSession
        s = ConsultationSession.objects.create(
            patient=paciente, expires_at=timezone.now() + timedelta(hours=5))
        _rodar('expirar_sessoes', execute=True)
        s.refresh_from_db()
        assert s.status == 'pending'

    def test_respeita_a_carencia_do_atendimento_em_andamento(self, paciente):
        """
        Sessão já aberta pelo profissional, vencida há pouco: pode haver alguém
        com o formulário na tela. Encerrar agora faria perder o preenchimento.
        """
        s = _sessao(paciente, 'active', 2)
        _rodar('expirar_sessoes', execute=True, carencia=24)
        s.refresh_from_db()
        assert s.status == 'active', 'Atendimento recente foi interrompido'

    def test_encerra_atendimento_abandonado(self, paciente):
        s = _sessao(paciente, 'active', 72)
        _rodar('expirar_sessoes', execute=True, carencia=24)
        s.refresh_from_db()
        assert s.status == 'expired'

    def test_nao_reabre_sessao_ja_encerrada(self, paciente):
        s = _sessao(paciente, 'closed', 100)
        _rodar('expirar_sessoes', execute=True)
        s.refresh_from_db()
        assert s.status == 'closed'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Rotina diária
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRotinaDiaria:

    def test_executa_as_duas_rotinas(self, conta_bot, paciente):
        from users.models import CustomUser
        s = _sessao(paciente, 'pending', 48)

        _rodar('manutencao_diaria', execute=True)

        assert not CustomUser.objects.filter(pk=conta_bot.pk).exists()
        s.refresh_from_db()
        assert s.status == 'expired'

    def test_modo_auditoria_nao_altera_nada(self, conta_bot, paciente):
        from users.models import CustomUser
        s = _sessao(paciente, 'pending', 48)

        saida = _rodar('manutencao_diaria')

        assert 'AUDITORIA' in saida
        assert CustomUser.objects.filter(pk=conta_bot.pk).exists()
        s.refresh_from_db()
        assert s.status == 'pending'
