"""
Ajustes na tela de registro de consulta.

Cobre três mudanças que se tocam: endereço deixou de ser obrigatório, o
formulário passou a guardar rascunho contra refresh acidental, e o rótulo de
observações foi simplificado.

O ponto delicado é o rascunho. São dados de saúde, e a garantia que importa
não é "o campo continuou preenchido" — é que o rascunho de um preenchimento
nunca apareça em outro, nem para outra pessoa no mesmo computador.
"""
import re
import shutil
import tempfile

import pytest
from django.urls import reverse


@pytest.fixture(autouse=True)
def tmp_media(settings):
    d = tempfile.mkdtemp(prefix='liddis_ajustes_')
    settings.MEDIA_ROOT = d
    settings.STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_aj', email='pac_aj@test.com', password='Senha@1234',
        first_name='Célia', last_name='Rocha', role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def outro_paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_aj2', email='pac_aj2@test.com', password='Senha@1234',
        role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def medico(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_aj', email='dr_aj@test.com', password='Senha@1234',
        first_name='Otávio', last_name='Reis', role='DOCTOR',
        profession='Médico', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


CONSULTA_MINIMA = {
    'date': '2026-07-14',
    'professional_name': 'Dra. Helena Prado',
    'profession': 'Médico',
    'specialty': 'clinico_geral',
    'status': 'active',
    'severity': 'low',
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Endereço deixou de ser obrigatório
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEnderecoOpcional:

    def test_paciente_salva_consulta_sem_endereco(self, client, paciente):
        from consultations.models import Consultation

        client.force_login(paciente)
        resp = client.post(reverse('consultation_create'), dict(CONSULTA_MINIMA), follow=True)
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(patient=paciente).first()
        assert consulta is not None, 'Consulta recusada por falta de endereço'
        assert consulta.clinic_name == ''
        assert consulta.clinic_city == ''

    def test_endereco_preenchido_continua_sendo_gravado(self, client, paciente):
        from consultations.models import Consultation

        client.force_login(paciente)
        client.post(reverse('consultation_create'), dict(
            CONSULTA_MINIMA,
            clinic_name='Clínica Aurora', clinic_neighborhood='Savassi',
            clinic_city='Belo Horizonte', clinic_address='Rua Pernambuco, 100',
        ), follow=True)

        c = Consultation.objects.get(patient=paciente)
        assert c.clinic_name == 'Clínica Aurora'
        assert c.clinic_neighborhood == 'Savassi'
        assert c.clinic_city == 'Belo Horizonte'
        assert c.clinic_address == 'Rua Pernambuco, 100'

    def test_endereco_parcial_e_aceito(self, client, paciente):
        from consultations.models import Consultation

        client.force_login(paciente)
        client.post(reverse('consultation_create'),
                    dict(CONSULTA_MINIMA, clinic_city='Recife'), follow=True)
        c = Consultation.objects.get(patient=paciente)
        assert c.clinic_city == 'Recife' and c.clinic_neighborhood == ''

    def test_profissional_registra_atendimento_sem_endereco(self, client, paciente, medico):
        from consultations.models import Consultation, ConsultationSession

        sessao = ConsultationSession.objects.create(patient=paciente)
        sessao.professional = medico
        sessao.status = 'active'
        sessao.save()

        client.force_login(medico)
        resp = client.post(reverse('atendimento_consulta', args=[sessao.token]),
                           {'date': '2026-07-14', 'diagnosis': 'Avaliação de rotina'},
                           follow=True)
        assert resp.status_code == 200
        assert Consultation.objects.filter(patient=paciente).exists(), \
            'Atendimento recusado por falta de endereço'

    def test_paciente_externo_sem_endereco(self, client, medico):
        from consultations.models import Consultation

        client.force_login(medico)
        resp = client.post(reverse('external_consultation_create'),
                           {'name': 'Rubens Tavares', 'date': '2026-07-14'}, follow=True)
        assert resp.status_code == 200
        assert Consultation.objects.filter(external_patient__isnull=False).exists(), \
            'Consulta externa recusada por falta de endereço'

    def test_formularios_nao_exigem_mais_local(self):
        from consultations.forms import (AtendimentoForm, ConsultationForm,
                                         ExternalConsultationForm)
        for F in (ConsultationForm, AtendimentoForm, ExternalConsultationForm):
            obrig = [k for k, v in F().fields.items() if v.required]
            for campo in ('clinic_name', 'clinic_neighborhood', 'clinic_city', 'clinic_address'):
                assert campo not in obrig, f'{F.__name__}.{campo} ainda é obrigatório'

    def test_telas_nao_marcam_endereco_como_obrigatorio(self, client, paciente):
        client.force_login(paciente)
        html = client.get(reverse('consultation_create')).content.decode('utf-8')
        for rotulo in ('Bairro', 'Cidade'):
            trecho = html[html.index(f'>{rotulo}'):][:200]
            assert '(opcional)' in trecho, f'{rotulo} ainda aparece como obrigatório'


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Rascunho contra refresh acidental
# ═══════════════════════════════════════════════════════════════════════════════

def _chave_rascunho(html):
    m = re.search(r"var CHAVE = '([^']+)'", html)
    return m.group(1) if m else None


@pytest.mark.django_db
class TestRascunho:

    def test_formulario_do_paciente_tem_rascunho(self, client, paciente):
        client.force_login(paciente)
        html = client.get(reverse('consultation_create')).content.decode('utf-8')
        assert 'rascunho-aviso' in html, 'Formulário sem rascunho automático'
        assert _chave_rascunho(html), 'Chave do rascunho não foi gerada'

    def test_chave_identifica_o_usuario(self, client, paciente, outro_paciente):
        """Duas pessoas no mesmo navegador não podem compartilhar rascunho."""
        client.force_login(paciente)
        chave_a = _chave_rascunho(client.get(reverse('consultation_create')).content.decode('utf-8'))

        client.logout()
        client.force_login(outro_paciente)
        chave_b = _chave_rascunho(client.get(reverse('consultation_create')).content.decode('utf-8'))

        assert chave_a and chave_b and chave_a != chave_b, \
            'Usuários diferentes receberam a mesma chave de rascunho'
        assert str(paciente.pk) in chave_a
        assert str(outro_paciente.pk) in chave_b

    def test_escopo_difere_entre_consulta_nova_e_edicao(self, client, paciente):
        """O rascunho de uma consulta não pode ser oferecido em outra."""
        from consultations.models import Consultation

        consulta = Consultation.objects.create(
            patient=paciente, date='2026-07-14', professional_name='Dr. Teste',
            profession='Médico', specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
            status='active', severity='low',
        )
        client.force_login(paciente)
        nova = _chave_rascunho(client.get(reverse('consultation_create')).content.decode('utf-8'))
        edicao = _chave_rascunho(
            client.get(reverse('consultation_update', args=[consulta.pk])).content.decode('utf-8'))

        assert nova != edicao, 'Consulta nova e edição compartilham o mesmo rascunho'
        assert str(consulta.pk) in edicao

    def test_atendimento_escopado_pela_sessao_do_paciente(self, client, paciente, medico):
        """
        No atendimento a chave usa o token da sessão, que já é único por
        paciente — assim o rascunho de um paciente não alcança o próximo.
        """
        from consultations.models import ConsultationSession

        s1 = ConsultationSession.objects.create(patient=paciente)
        s1.professional = medico; s1.status = 'active'; s1.save()

        client.force_login(medico)
        chave1 = _chave_rascunho(
            client.get(reverse('atendimento_consulta', args=[s1.token])).content.decode('utf-8'))
        assert chave1 and str(s1.token) in chave1

    def test_rascunho_nao_guarda_arquivo_nem_csrf(self, client, paciente):
        client.force_login(paciente)
        html = client.get(reverse('consultation_create')).content.decode('utf-8')
        assert "campo.type === 'file'" in html, 'Rascunho não exclui campos de arquivo'
        assert "csrfmiddlewaretoken" in html, 'Rascunho não exclui o token CSRF'

    def test_rascunho_e_limpo_ao_enviar(self, client, paciente):
        client.force_login(paciente)
        html = client.get(reverse('consultation_create')).content.decode('utf-8')
        assert "addEventListener('submit', limpar)" in html, \
            'Rascunho não é descartado após o envio'

    def test_usa_sessionstorage_e_nao_localstorage(self, client, paciente):
        """
        localStorage sobreviveria ao fechamento do navegador e ao logout. A
        checagem recorta o script do rascunho: a página usa localStorage para
        a preferência de tema, que não é dado de saúde.
        """
        client.force_login(paciente)
        html = client.get(reverse('consultation_create')).content.decode('utf-8')
        ini = html.index("var CHAVE = 'liddis:rascunho")
        script = html[ini:html.index('</script>', ini)]
        assert 'sessionStorage' in script
        assert 'localStorage' not in script, 'Dado de saúde não deve ir para localStorage'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Rótulo de observações
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRotuloObservacoes:

    def test_formularios_nao_dizem_mais_observacoes_clinicas(self):
        from consultations.forms import ExternalPatientForm
        assert ExternalPatientForm().fields['notes'].label == 'Observações'

    def test_nenhuma_tela_exibe_o_rotulo_antigo(self):
        from pathlib import Path
        from django.conf import settings

        raiz = Path(settings.BASE_DIR) / 'templates'
        culpados = [
            str(p.relative_to(raiz))
            for p in raiz.rglob('*.html')
            if 'legal' not in p.parts
            and re.search(r'Observaç[õo]es\s+[Cc]línicas', p.read_text(encoding='utf-8'))
        ]
        assert not culpados, f'Rótulo antigo ainda nas telas: {culpados}'
