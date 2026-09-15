"""
Múltiplos anexos na mesma consulta.

Relato de produção: dificuldade para anexar exames, limite indevido na
quantidade, e consulta que não salva ao enviar dois ou mais arquivos. Estes
testes exercitam 1, 2, 3+ arquivos, tipos misturados e o caso em que um
arquivo da leva é inválido — cenário em que o resto não pode ser perdido.
"""
import shutil
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


@pytest.fixture(autouse=True)
def tmp_media(settings):
    d = tempfile.mkdtemp(prefix='liddis_multi_')
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


def png(nome):
    return SimpleUploadedFile(nome, PNG, content_type='image/png')


def pdf(nome):
    return SimpleUploadedFile(nome, PDF, content_type='application/pdf')


def jpg(nome):
    return SimpleUploadedFile(nome, JPG, content_type='image/jpeg')


@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_multi', email='pac_multi@test.com', password='Senha@1234',
        first_name='Clara', last_name='Dias', role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def medico(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_multi', email='dr_multi@test.com', password='Senha@1234',
        first_name='Iara', last_name='Bastos', role='DOCTOR',
        profession='Médica', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


@pytest.fixture
def consulta(db, paciente):
    from consultations.models import Consultation
    return Consultation.objects.create(
        patient=paciente, date='2026-06-10', professional_name='Dr. Teste',
        profession='Médico', specialty='clinico_geral', clinic_name='Clínica Central',
        record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        status='active', severity='low',
    )


DADOS_CONSULTA = {
    'date': '2026-06-10',
    'professional_name': 'Dra. Iara Bastos',
    'profession': 'Médico',
    'specialty': 'clinico_geral',
    'clinic_name': 'Clínica Central',
    'clinic_neighborhood': 'Centro',
    'clinic_city': 'São Paulo',
    'status': 'active',
    'severity': 'low',
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Quantidade de arquivos na criação da consulta
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVariosArquivosNaCriacao:

    @pytest.mark.parametrize('quantidade', [1, 2, 3, 5])
    def test_todos_os_arquivos_persistem(self, client, paciente, quantidade):
        from consultations.models import Consultation, ConsultationImage

        client.force_login(paciente)
        dados = dict(DADOS_CONSULTA)
        dados['images_exames'] = [png(f'exame_{i}.png') for i in range(quantidade)]

        resp = client.post(reverse('consultation_create'), dados, follow=True)
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(patient=paciente).first()
        assert consulta is not None, f'Consulta não foi salva com {quantidade} anexo(s)'

        anexos = ConsultationImage.objects.filter(consultation=consulta)
        assert anexos.count() == quantidade, \
            f'Enviados {quantidade}, gravados {anexos.count()}'
        for a in anexos:
            assert a.image.storage.exists(a.image.name), \
                f'Registro sem arquivo no storage: {a.image.name}'

    def test_pdf_e_imagem_na_mesma_leva(self, client, paciente):
        from consultations.models import Consultation, ConsultationImage

        client.force_login(paciente)
        dados = dict(DADOS_CONSULTA)
        dados['images_exames'] = [pdf('laudo.pdf'), png('raiox.png'), jpg('foto.jpg')]

        client.post(reverse('consultation_create'), dados, follow=True)
        consulta = Consultation.objects.filter(patient=paciente).first()
        anexos = ConsultationImage.objects.filter(consultation=consulta)
        assert anexos.count() == 3
        nomes = {a.image.name.rsplit('.', 1)[1] for a in anexos}
        assert nomes == {'pdf', 'png', 'jpg'}

    def test_arquivos_em_abas_diferentes_na_mesma_submissao(self, client, paciente):
        from consultations.models import Consultation, ConsultationImage

        client.force_login(paciente)
        dados = dict(DADOS_CONSULTA)
        dados['images_exames'] = [pdf('lab1.pdf'), pdf('lab2.pdf')]
        dados['images_anamnese'] = [png('aval.png')]

        client.post(reverse('consultation_create'), dados, follow=True)
        consulta = Consultation.objects.filter(patient=paciente).first()
        assert ConsultationImage.objects.filter(consultation=consulta, tab='exames').count() == 2
        assert ConsultationImage.objects.filter(consultation=consulta, tab='anamnese').count() == 1

    def test_consulta_sobrevive_a_arquivo_invalido_na_leva(self, client, paciente):
        """
        Um arquivo recusado não pode custar a consulta nem os arquivos válidos
        enviados junto — era o relato de "não salva ao adicionar dois ou mais".
        """
        from consultations.models import Consultation, ConsultationImage

        client.force_login(paciente)
        dados = dict(DADOS_CONSULTA)
        dados['images_exames'] = [
            pdf('bom1.pdf'),
            SimpleUploadedFile('malicioso.exe', b'MZ\x90\x00', content_type='application/octet-stream'),
            png('bom2.png'),
        ]

        resp = client.post(reverse('consultation_create'), dados, follow=True)
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(patient=paciente).first()
        assert consulta is not None, 'Consulta perdida por causa de um anexo inválido'

        anexos = ConsultationImage.objects.filter(consultation=consulta)
        assert anexos.count() == 2, 'Os arquivos válidos da leva deveriam persistir'
        assert not anexos.filter(image__endswith='.exe').exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Anexar depois, pela página da consulta
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVariosArquivosDepoisDeSalvar:

    def test_upload_aceita_varios_arquivos_de_uma_vez(self, client, paciente, consulta):
        """
        A página da consulta precisa aceitar seleção múltipla, como a tela de
        criação. Um arquivo por envio é a limitação relatada.
        """
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        client.post(
            reverse('consultation_upload_image', args=[consulta.pk]),
            {'tab': 'exames', 'caption': 'Série de exames',
             'image': [pdf('a.pdf'), png('b.png'), jpg('c.jpg')]},
            follow=True,
        )
        assert ConsultationImage.objects.filter(consultation=consulta).count() == 3, \
            'Envio múltiplo pela página da consulta não gravou todos os arquivos'

    def test_envios_sucessivos_acumulam_sem_sobrescrever(self, client, paciente, consulta):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        for i in range(3):
            client.post(
                reverse('consultation_upload_image', args=[consulta.pk]),
                {'tab': 'exames', 'image': png(f'serie_{i}.png')},
                follow=True,
            )
        anexos = ConsultationImage.objects.filter(consultation=consulta)
        assert anexos.count() == 3, 'Anexo sobrescrito em envio sucessivo'
        caminhos = {a.image.name for a in anexos}
        assert len(caminhos) == 3, 'Dois registros apontam para o mesmo arquivo'

    def test_remover_um_nao_afeta_os_outros(self, client, paciente, consulta):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        for i in range(3):
            client.post(
                reverse('consultation_upload_image', args=[consulta.pk]),
                {'tab': 'exames', 'image': png(f'x{i}.png')}, follow=True,
            )
        anexos = list(ConsultationImage.objects.filter(consultation=consulta).order_by('pk'))
        alvo = anexos[1]
        sobreviventes = [(a.image.storage, a.image.name) for a in (anexos[0], anexos[2])]

        client.post(reverse('consultation_delete_image', args=[consulta.pk, alvo.pk]), follow=True)

        assert ConsultationImage.objects.filter(consultation=consulta).count() == 2
        for storage, nome in sobreviventes:
            assert storage.exists(nome), 'Remoção de um anexo apagou arquivo de outro'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Fluxo do profissional via token
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVariosArquivosNoAtendimento:

    def test_profissional_anexa_varios_ao_registrar(self, client, paciente, medico):
        from consultations.models import Consultation, ConsultationImage, ConsultationSession

        sessao = ConsultationSession.objects.create(patient=paciente)
        sessao.professional = medico
        sessao.status = 'active'
        sessao.save()

        client.force_login(medico)
        dados = {
            'date': '2026-06-10', 'clinic_name': 'Clínica Central',
            'clinic_neighborhood': 'Centro', 'clinic_city': 'São Paulo',
            'diagnosis': 'Avaliação de rotina',
            'images_exames': [pdf('lab_a.pdf'), pdf('lab_b.pdf'), png('img.png')],
            'images_diagnostico': [png('diag.png')],
        }
        resp = client.post(
            reverse('atendimento_consulta', args=[sessao.token]), dados, follow=True,
        )
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(patient=paciente).first()
        assert consulta is not None, 'Atendimento não foi salvo com múltiplos anexos'
        assert ConsultationImage.objects.filter(consultation=consulta, tab='exames').count() == 3
        assert ConsultationImage.objects.filter(consultation=consulta, tab='diagnostico').count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Recuperação no histórico
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestHistorico:

    def test_todos_os_anexos_aparecem_apos_recarregar(self, client, paciente, consulta):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        for i in range(4):
            client.post(
                reverse('consultation_upload_image', args=[consulta.pk]),
                {'tab': 'exames', 'image': png(f'h{i}.png'), 'caption': f'Exame {i}'},
                follow=True,
            )

        html = client.get(reverse('consultation_detail', args=[consulta.pk])).content.decode('utf-8')
        for anexo in ConsultationImage.objects.filter(consultation=consulta):
            url = reverse('consultation_attachment', args=[consulta.pk, anexo.pk])
            assert url in html, f'Anexo {anexo.pk} não aparece no histórico'

    def test_cada_anexo_baixa_o_proprio_conteudo(self, client, paciente, consulta):
        from consultations.models import ConsultationImage

        client.force_login(paciente)
        client.post(reverse('consultation_upload_image', args=[consulta.pk]),
                    {'tab': 'exames', 'image': pdf('doc.pdf')}, follow=True)
        client.post(reverse('consultation_upload_image', args=[consulta.pk]),
                    {'tab': 'exames', 'image': png('img.png')}, follow=True)

        tipos = set()
        for anexo in ConsultationImage.objects.filter(consultation=consulta):
            resp = client.get(reverse('consultation_attachment', args=[consulta.pk, anexo.pk]))
            assert resp.status_code == 200
            tipos.add(resp['Content-Type'])
        assert tipos == {'application/pdf', 'image/png'}, \
            f'Content-Type incorreto por anexo: {tipos}'
