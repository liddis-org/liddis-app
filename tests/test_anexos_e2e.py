"""
Testes End-to-End do ciclo de vida de anexos.

Cobre o fluxo completo exigido pela auditoria:
  anexar → legenda → salvar → recarregar → logout/login → visualizar → baixar

Inclui isolamento entre pacientes (IDOR), formatos aceitos, paciente externo
e o cenário de arquivo ausente no storage.
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
    """MEDIA_ROOT isolado — nenhum teste escreve na pasta media/ do projeto."""
    d = tempfile.mkdtemp(prefix='liddis_test_media_')
    settings.MEDIA_ROOT = d
    settings.STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    yield d
    shutil.rmtree(d, ignore_errors=True)


PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)
PDF_BYTES = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
JPG_BYTES = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'


def png(name='exame.png'):
    return SimpleUploadedFile(name, PNG_BYTES, content_type='image/png')


def pdf(name='laudo.pdf'):
    return SimpleUploadedFile(name, PDF_BYTES, content_type='application/pdf')


def jpg(name='foto.jpg'):
    return SimpleUploadedFile(name, JPG_BYTES, content_type='image/jpeg')


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures de domínio
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_anexo', email='pac_anexo@test.com', password='Senha@1234',
        first_name='Ana', last_name='Lima', role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def outro_paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_intruso', email='pac_intruso@test.com', password='Senha@1234',
        first_name='Bruno', last_name='Souza', role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def medico(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_anexo', email='dr_anexo@test.com', password='Senha@1234',
        first_name='Carlos', last_name='Oliveira', role='DOCTOR',
        profession='Médico', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


@pytest.fixture
def consulta_do_paciente(db, paciente):
    """Consulta manual do paciente — ele tem direito de escrita sobre ela."""
    from consultations.models import Consultation
    return Consultation.objects.create(
        patient=paciente,
        date='2026-03-10',
        professional_name='Dr. Teste',
        profession='Médico',
        specialty='clinico_geral',
        clinic_name='Clínica Central',
        record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        status='active',
        severity='low',
    )


def _anexar(client, consulta, arquivo, tab='exames', caption=''):
    """Faz upload via HTTP e devolve a resposta."""
    return client.post(
        reverse('consultation_upload_image', args=[consulta.pk]),
        {'tab': tab, 'image': arquivo, 'caption': caption},
        follow=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Ciclo de vida completo — paciente LIDDIS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCicloVidaAnexoPaciente:

    def test_upload_persiste_no_banco_e_no_storage(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        resp = _anexar(client, consulta_do_paciente, pdf(), tab='exames', caption='Hemograma')
        assert resp.status_code == 200

        # Persistência no banco
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)
        assert img.tab == 'exames'
        assert img.caption == 'Hemograma'

        # Persistência no storage — o arquivo existe de fato
        assert img.image.storage.exists(img.image.name), \
            'Registro criado no banco mas arquivo ausente no storage'
        assert img.image.size == len(PDF_BYTES)

    def test_anexo_visivel_apos_recarregar_pagina(self, client, paciente, consulta_do_paciente):
        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, png(), tab='anamnese', caption='Raio-X')

        resp = client.get(reverse('consultation_detail', args=[consulta_do_paciente.pk]))
        assert resp.status_code == 200
        # A galeria precisa conter o link do proxy do anexo
        from consultations.models import ConsultationImage
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)
        url_proxy = reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk])
        assert url_proxy.encode() in resp.content, 'Anexo não aparece na página de detalhe'
        assert b'Raio-X' in resp.content, 'Legenda do anexo não aparece'

    def test_anexo_sobrevive_logout_e_novo_login(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames', caption='Laudo')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        client.logout()
        client.force_login(paciente)

        resp = client.get(reverse('consultation_detail', args=[consulta_do_paciente.pk]))
        url_proxy = reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk])
        assert url_proxy.encode() in resp.content, 'Anexo sumiu após novo login'

    def test_download_do_anexo_entrega_o_conteudo(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        resp = client.get(reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk]))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert b''.join(resp.streaming_content) == PDF_BYTES if resp.streaming \
            else resp.content == PDF_BYTES
        assert resp['X-Content-Type-Options'] == 'nosniff'

    def test_multiplos_anexos_em_abas_diferentes(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        for tab in ('anamnese', 'exames', 'diagnostico', 'prescricao'):
            _anexar(client, consulta_do_paciente, png(f'{tab}.png'), tab=tab, caption=f'cap-{tab}')

        assert ConsultationImage.objects.filter(consultation=consulta_do_paciente).count() == 4
        for tab in ('anamnese', 'exames', 'diagnostico', 'prescricao'):
            assert ConsultationImage.objects.filter(
                consultation=consulta_do_paciente, tab=tab
            ).exists(), f'Anexo da aba {tab} não persistiu'

    def test_remocao_apaga_registro_e_arquivo(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, png(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)
        storage, name = img.image.storage, img.image.name
        assert storage.exists(name)

        client.post(reverse('consultation_delete_image', args=[consulta_do_paciente.pk, img.pk]), follow=True)
        assert not ConsultationImage.objects.filter(pk=img.pk).exists()
        assert not storage.exists(name), 'Arquivo órfão deixado no storage após remoção'


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Formatos aceitos e rejeitados
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFormatosAnexo:

    @pytest.mark.parametrize('arquivo,ext', [
        (pdf, 'pdf'), (png, 'png'), (jpg, 'jpg'),
    ])
    def test_formatos_previstos_sao_aceitos(self, client, paciente, consulta_do_paciente, arquivo, ext):
        from consultations.models import ConsultationImage
        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, arquivo(f'arquivo.{ext}'), tab='exames')
        assert ConsultationImage.objects.filter(consultation=consulta_do_paciente).count() == 1, \
            f'Formato {ext} deveria ser aceito'

    def test_executavel_e_rejeitado(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage
        client.force_login(paciente)
        mal = SimpleUploadedFile('payload.exe', b'MZ\x90\x00', content_type='application/octet-stream')
        _anexar(client, consulta_do_paciente, mal, tab='exames')
        assert ConsultationImage.objects.filter(consultation=consulta_do_paciente).count() == 0, \
            'Executável não deveria ser aceito como anexo'

    def test_extensao_dupla_e_rejeitada(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage
        client.force_login(paciente)
        mal = SimpleUploadedFile('foto.png.exe', b'MZ\x90\x00', content_type='image/png')
        _anexar(client, consulta_do_paciente, mal, tab='exames')
        assert ConsultationImage.objects.filter(consultation=consulta_do_paciente).count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Segurança — IDOR / BOLA
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSegurancaAnexo:

    def test_outro_paciente_nao_acessa_anexo(self, client, paciente, outro_paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        client.logout()
        client.force_login(outro_paciente)
        resp = client.get(reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk]))
        assert resp.status_code == 404, 'IDOR: paciente acessou anexo de outro paciente'

    def test_nao_autenticado_nao_acessa_anexo(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        client.logout()
        resp = client.get(reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk]))
        assert resp.status_code in (302, 404)
        if resp.status_code == 302:
            assert '/login/' in resp['Location']

    def test_profissional_sem_vinculo_nao_acessa_anexo(self, client, paciente, medico, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        client.logout()
        client.force_login(medico)
        resp = client.get(reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk]))
        assert resp.status_code == 404, 'Profissional sem vínculo acessou anexo'

    def test_outro_paciente_nao_remove_anexo(self, client, paciente, outro_paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        client.logout()
        client.force_login(outro_paciente)
        client.post(reverse('consultation_delete_image', args=[consulta_do_paciente.pk, img.pk]))
        assert ConsultationImage.objects.filter(pk=img.pk).exists(), \
            'Paciente conseguiu remover anexo de outro paciente'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Arquivo ausente no storage — diagnóstico da regressão relatada
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestArquivoAusenteNoStorage:

    def test_registro_sem_arquivo_nao_derruba_a_pagina(self, client, paciente, consulta_do_paciente):
        """
        Simula o cenário de arquivos perdidos: o registro existe no banco mas o
        arquivo sumiu do storage. A página de detalhe deve continuar carregando.
        """
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, png(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)

        # Remove o arquivo por baixo, mantendo o registro
        img.image.storage.delete(img.image.name)
        assert not img.image.storage.exists(img.image.name)

        resp = client.get(reverse('consultation_detail', args=[consulta_do_paciente.pk]))
        assert resp.status_code == 200, 'Página quebrou por causa de anexo ausente'

    def test_proxy_de_arquivo_ausente_retorna_404(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, png(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)
        img.image.storage.delete(img.image.name)

        resp = client.get(reverse('consultation_attachment', args=[consulta_do_paciente.pk, img.pk]))
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Ciclo de vida do arquivo no storage — sem vazamento
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSemVazamentoDeArquivo:

    def test_excluir_consulta_apaga_arquivos_do_storage(self, client, paciente, consulta_do_paciente):
        """
        CASCADE apaga as linhas de anexo; os arquivos precisam sair junto.
        Documento clínico que permanece no bucket após exclusão é vazamento
        de storage e problema de LGPD.
        """
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, pdf(), tab='exames')
        _anexar(client, consulta_do_paciente, png(), tab='anamnese')

        imgs = list(ConsultationImage.objects.filter(consultation=consulta_do_paciente))
        assert len(imgs) == 2
        rastros = [(i.image.storage, i.image.name) for i in imgs]
        for storage, name in rastros:
            assert storage.exists(name)

        consulta_do_paciente.delete()

        for storage, name in rastros:
            assert not storage.exists(name), \
                f'Arquivo {name} ficou órfão no storage após exclusão da consulta'

    def test_exclusao_direta_do_anexo_apaga_arquivo(self, client, paciente, consulta_do_paciente):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        _anexar(client, consulta_do_paciente, png(), tab='exames')
        img = ConsultationImage.objects.get(consultation=consulta_do_paciente)
        storage, name = img.image.storage, img.image.name

        img.delete()
        assert not storage.exists(name), 'Arquivo permaneceu no storage após delete() do registro'
