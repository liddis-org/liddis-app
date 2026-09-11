"""
Anexos em consultas de paciente sem conta LIDDIS.

O anexo pertence à consulta, não ao paciente — `ConsultationImage` referencia
apenas `Consultation`. Portanto a ausência de conta LIDDIS não deveria mudar
nada; estes testes cobrem o caminho externo ponta a ponta para garantir que ele
tenha exatamente os mesmos recursos do fluxo normal, e que a autorização
continue valendo quando não há usuário-paciente para ancorá-la.
"""
import shutil
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


# ═══════════════════════════════════════════════════════════════════════════════
# Infraestrutura
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def tmp_media(settings):
    d = tempfile.mkdtemp(prefix='liddis_ext_media_')
    settings.MEDIA_ROOT = d
    settings.STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    yield d
    shutil.rmtree(d, ignore_errors=True)


PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)
PDF = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
JPG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'


def png(nome='exame.png'):
    return SimpleUploadedFile(nome, PNG, content_type='image/png')


def pdf(nome='laudo.pdf'):
    return SimpleUploadedFile(nome, PDF, content_type='application/pdf')


def jpg(nome='foto.jpg'):
    return SimpleUploadedFile(nome, JPG, content_type='image/jpeg')


DADOS_CONSULTA = {
    'name':                'João Batista Ferreira',
    'cpf':                 '',
    'sex':                 '',
    'phone':               '',
    'email':               '',
    'notes':               '',
    'date':                '2026-05-20',
    'clinic_name':         'Clínica Santa Rita',
    'clinic_neighborhood': 'Centro',
    'clinic_city':         'São Paulo',
    'clinic_address':      'Rua das Palmeiras, 120',
    'diagnosis':           'Lombalgia mecânica',
    'notes_consulta':      '',
    'prescription':        'Anti-inflamatório por 5 dias',
}


def _payload(**extra):
    d = {k: v for k, v in DADOS_CONSULTA.items() if k != 'notes_consulta'}
    d.update(extra)
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures de domínio
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def profissional(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_externo', email='dr_externo@test.com', password='Senha@1234',
        first_name='Helena', last_name='Prado', role='DOCTOR',
        profession='Médica', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


@pytest.fixture
def outro_profissional(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_intruso', email='dr_intruso@test.com', password='Senha@1234',
        first_name='Mario', last_name='Reis', role='DOCTOR',
        profession='Médico', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


@pytest.fixture
def consulta_externa(client, profissional):
    """Consulta de paciente sem conta, já criada pelo profissional."""
    from consultations.models import Consultation
    client.force_login(profissional)
    resp = client.post(reverse('external_consultation_create'), _payload(), follow=True)
    assert resp.status_code == 200
    consulta = Consultation.objects.filter(external_patient__isnull=False).first()
    assert consulta is not None, 'Consulta externa não foi criada'
    return consulta


def _anexar(client, consulta, arquivo, tab='exames', caption=''):
    return client.post(
        reverse('consultation_upload_image', args=[consulta.pk]),
        {'tab': tab, 'image': arquivo, 'caption': caption},
        follow=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Anexar durante a criação da consulta
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAnexoNaCriacao:

    def test_anexos_enviados_no_formulario_sao_gravados(self, client, profissional):
        from consultations.models import Consultation, ConsultationImage

        client.force_login(profissional)
        dados = _payload()
        dados['images_anamnese'] = pdf('avaliacao.pdf')
        dados['images_exames'] = png('hemograma.png')

        resp = client.post(reverse('external_consultation_create'), dados, follow=True)
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(external_patient__isnull=False).first()
        assert consulta is not None

        anexos = ConsultationImage.objects.filter(consultation=consulta)
        assert anexos.count() == 2, \
            'Anexos enviados no formulário de criação não foram gravados'
        assert set(anexos.values_list('tab', flat=True)) == {'anamnese', 'exames'}

        for a in anexos:
            assert a.image.storage.exists(a.image.name), \
                f'Registro criado mas arquivo ausente no storage: {a.image.name}'

    def test_legenda_do_anexo_e_preservada(self, client, profissional):
        from consultations.models import Consultation, ConsultationImage

        client.force_login(profissional)
        dados = _payload()
        dados['images_exames'] = png('raiox.png')
        dados['caption_exames'] = 'Raio-X lombar em perfil'

        client.post(reverse('external_consultation_create'), dados, follow=True)
        consulta = Consultation.objects.filter(external_patient__isnull=False).first()
        anexo = ConsultationImage.objects.get(consultation=consulta)
        assert anexo.caption == 'Raio-X lombar em perfil'

    def test_consulta_e_criada_mesmo_sem_anexo(self, client, profissional):
        """O anexo é opcional — sua ausência não pode impedir o registro."""
        from consultations.models import Consultation
        client.force_login(profissional)
        client.post(reverse('external_consultation_create'), _payload(), follow=True)
        assert Consultation.objects.filter(external_patient__isnull=False).count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Anexar depois, pela página da consulta
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAnexoAposSalvar:

    @pytest.mark.parametrize('arquivo,ext', [(pdf, 'pdf'), (png, 'png'), (jpg, 'jpg')])
    def test_formatos_previstos_sao_aceitos(self, client, profissional, consulta_externa,
                                            arquivo, ext):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, arquivo(f'doc.{ext}'), tab='exames')
        assert ConsultationImage.objects.filter(consultation=consulta_externa).count() == 1, \
            f'Formato {ext} recusado em consulta de paciente externo'

    def test_anexo_em_cada_uma_das_quatro_abas(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        for tab in ('anamnese', 'exames', 'diagnostico', 'prescricao'):
            _anexar(client, consulta_externa, png(f'{tab}.png'), tab=tab, caption=f'cap-{tab}')

        assert ConsultationImage.objects.filter(consultation=consulta_externa).count() == 4
        for tab in ('anamnese', 'exames', 'diagnostico', 'prescricao'):
            assert ConsultationImage.objects.filter(
                consultation=consulta_externa, tab=tab
            ).exists(), f'Aba {tab} não aceitou anexo'

    def test_anexo_aparece_na_pagina_apos_recarregar(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='diagnostico', caption='Ressonância')

        resp = client.get(reverse('consultation_detail', args=[consulta_externa.pk]))
        assert resp.status_code == 200
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)
        url = reverse('consultation_attachment', args=[consulta_externa.pk, anexo.pk])
        assert url.encode() in resp.content, 'Anexo não aparece na página da consulta'
        assert 'Ressonância'.encode() in resp.content

    def test_download_entrega_o_conteudo(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, pdf(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        resp = client.get(reverse('consultation_attachment',
                                  args=[consulta_externa.pk, anexo.pk]))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp['X-Content-Type-Options'] == 'nosniff'

    def test_anexo_sobrevive_a_novo_login(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='anamnese')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        client.logout()
        client.force_login(profissional)
        resp = client.get(reverse('consultation_attachment',
                                  args=[consulta_externa.pk, anexo.pk]))
        assert resp.status_code == 200

    def test_remocao_apaga_registro_e_arquivo(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)
        storage, nome = anexo.image.storage, anexo.image.name

        client.post(reverse('consultation_delete_image',
                            args=[consulta_externa.pk, anexo.pk]), follow=True)
        assert not ConsultationImage.objects.filter(pk=anexo.pk).exists()
        assert not storage.exists(nome), 'Arquivo ficou órfão no storage'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Relacionamentos e integridade
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRelacionamentos:

    def test_anexo_referencia_a_consulta_sem_depender_de_conta(
        self, client, profissional, consulta_externa
    ):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='exames', caption='Ultrassom')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        assert anexo.consultation_id == consulta_externa.pk
        assert consulta_externa.patient_id is None, 'Consulta externa não deve ter patient LIDDIS'
        assert consulta_externa.external_patient_id is not None
        assert anexo.uploaded_at is not None
        assert anexo.tab and anexo.caption and anexo.image.name

    def test_caminho_no_storage_isola_por_consulta(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)
        assert str(consulta_externa.pk) in anexo.image.name, \
            'Caminho do arquivo não identifica a consulta'

    def test_excluir_consulta_nao_deixa_arquivo_orfao(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, pdf(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)
        storage, nome = anexo.image.storage, anexo.image.name

        consulta_externa.delete()
        assert not storage.exists(nome), \
            'Documento clínico permaneceu no storage após exclusão da consulta'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Autorização — sem conta de paciente para ancorar a permissão
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutorizacao:

    def test_outro_profissional_nao_ve_o_anexo(
        self, client, profissional, outro_profissional, consulta_externa
    ):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, pdf(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        client.logout()
        client.force_login(outro_profissional)
        resp = client.get(reverse('consultation_attachment',
                                  args=[consulta_externa.pk, anexo.pk]))
        assert resp.status_code == 404, \
            'Profissional sem relação com a consulta acessou o anexo'

    def test_outro_profissional_nao_anexa(
        self, client, profissional, outro_profissional, consulta_externa
    ):
        from consultations.models import ConsultationImage
        client.force_login(outro_profissional)
        _anexar(client, consulta_externa, png(), tab='exames')
        assert ConsultationImage.objects.filter(consultation=consulta_externa).count() == 0

    def test_outro_profissional_nao_remove(
        self, client, profissional, outro_profissional, consulta_externa
    ):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, png(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        client.logout()
        client.force_login(outro_profissional)
        client.post(reverse('consultation_delete_image',
                            args=[consulta_externa.pk, anexo.pk]))
        assert ConsultationImage.objects.filter(pk=anexo.pk).exists()

    def test_anonimo_nao_acessa(self, client, profissional, consulta_externa):
        from consultations.models import ConsultationImage
        client.force_login(profissional)
        _anexar(client, consulta_externa, pdf(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        client.logout()
        resp = client.get(reverse('consultation_attachment',
                                  args=[consulta_externa.pk, anexo.pk]))
        assert resp.status_code in (302, 404)

    def test_paciente_alheio_nao_acessa(self, client, db, profissional, consulta_externa):
        from users.models import CustomUser
        from consultations.models import ConsultationImage

        client.force_login(profissional)
        _anexar(client, consulta_externa, pdf(), tab='exames')
        anexo = ConsultationImage.objects.get(consultation=consulta_externa)

        bisbilhoteiro = CustomUser.objects.create_user(
            username='curioso', email='curioso@test.com', password='Senha@1234',
            role='PATIENT', is_email_verified=True,
        )
        client.logout()
        client.force_login(bisbilhoteiro)
        resp = client.get(reverse('consultation_attachment',
                                  args=[consulta_externa.pk, anexo.pk]))
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Sem regressão no fluxo de paciente cadastrado
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSemRegressaoNoFluxoNormal:

    def test_paciente_liddis_continua_anexando(self, client, db):
        from users.models import CustomUser
        from consultations.models import Consultation, ConsultationImage

        paciente = CustomUser.objects.create_user(
            username='pac_normal', email='pac_normal@test.com', password='Senha@1234',
            role='PATIENT', is_email_verified=True,
        )
        consulta = Consultation.objects.create(
            patient=paciente, date='2026-05-20', professional_name='Dr. Teste',
            profession='Médico', specialty='clinico_geral', clinic_name='Clínica X',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
            status='active', severity='low',
        )
        client.force_login(paciente)
        _anexar(client, consulta, pdf(), tab='exames', caption='Exame de rotina')

        anexo = ConsultationImage.objects.get(consultation=consulta)
        assert anexo.caption == 'Exame de rotina'
        assert anexo.image.storage.exists(anexo.image.name)
        assert consulta.patient_id == paciente.pk
        assert consulta.external_patient_id is None
