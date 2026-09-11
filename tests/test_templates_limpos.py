"""
Garantias sobre o que os templates entregam ao usuário.

Existe por causa de um caso concreto: um comentário `{# ... #}` escrito em
várias linhas foi renderizado como texto visível na tela de atendimento
externo. A sintaxe `{# #}` do Django só vale em linha única — em várias
linhas o parser não a reconhece como comentário e imprime tudo. O erro passa
despercebido porque nada quebra: a página carrega normalmente, só com texto
técnico no meio.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse


RAIZ_TEMPLATES = Path(settings.BASE_DIR) / 'templates'


def _todos_os_templates():
    return sorted(RAIZ_TEMPLATES.rglob('*.html'))


def _ids(p):
    return str(p.relative_to(RAIZ_TEMPLATES)).replace('\\', '/')


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Sintaxe de comentário que vaza para a tela
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('caminho', _todos_os_templates(), ids=_ids)
def test_comentario_de_template_fecha_na_mesma_linha(caminho):
    """
    `{# ... #}` precisa abrir e fechar na mesma linha. Para comentário de
    várias linhas o correto é `{% comment %} ... {% endcomment %}`.
    """
    infratoras = [
        (n, linha.strip())
        for n, linha in enumerate(caminho.read_text(encoding='utf-8').splitlines(), 1)
        if '{#' in linha and '#}' not in linha
    ]
    assert not infratoras, (
        f'{_ids(caminho)}: comentário {{# #}} sem fechamento na mesma linha '
        f'(linha {infratoras[0][0]}) — seria renderizado como texto visível. '
        f'Use {{% comment %}}...{{% endcomment %}}.'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Páginas não entregam sintaxe de template nem texto técnico
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def profissional(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='prof_tpl', email='prof_tpl@test.com', password='Senha@1234',
        first_name='Marta', last_name='Nunes', role='NURSE',
        profession='Enfermeira', is_email_verified=True,
    )


# Marcadores que só fazem sentido para quem escreve o código.
_VAZAMENTOS = ('{#', '#}', '{%', '}}', 'TODO', 'FIXME', 'lorem ipsum')


def _procurar_vazamento(html):
    corpo = html
    # Blocos <script> e <style> legitimamente contêm chaves.
    corpo = re.sub(r'<script\b.*?</script>', '', corpo, flags=re.S | re.I)
    corpo = re.sub(r'<style\b.*?</style>', '', corpo, flags=re.S | re.I)
    baixo = corpo.lower()
    return [m for m in _VAZAMENTOS if (m.lower() in baixo)]


@pytest.mark.django_db
class TestPaginasSemTextoTecnico:

    def test_formulario_de_atendimento_externo(self, client, profissional):
        client.force_login(profissional)
        resp = client.get(reverse('external_consultation_create'))
        assert resp.status_code == 200
        html = resp.content.decode('utf-8', errors='ignore')

        achados = _procurar_vazamento(html)
        assert not achados, f'Texto técnico visível na tela: {achados}'
        assert '_handle_image_uploads' not in html, \
            'Nome de função interna exposto ao usuário'

    def test_login_e_registro(self, client):
        for nome in ('login', 'register'):
            resp = client.get(reverse(nome))
            assert resp.status_code == 200
            html = resp.content.decode('utf-8', errors='ignore')
            achados = _procurar_vazamento(html)
            assert not achados, f'Texto técnico visível em {nome}: {achados}'

    def test_formulario_externo_tem_upload_proprio(self, client, profissional):
        """
        O componente de anexo precisa ser o da LIDDIS, não o botão nativo:
        o input fica oculto e a área clicável é desenhada pela aplicação.
        """
        client.force_login(profissional)
        html = client.get(reverse('external_consultation_create')).content.decode('utf-8')

        assert 'anexo-zona' in html, 'Área de upload própria ausente'
        assert 'type="file"' in html and 'hidden' in html, \
            'O input nativo deveria estar oculto atrás do componente'
        for tab in ('anamnese', 'exames', 'diagnostico', 'prescricao'):
            assert f'images_{tab}' in html, f'Campo de anexo da aba {tab} ausente'
            assert f'caption_{tab}' in html, f'Campo de legenda da aba {tab} ausente'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Isolamento — uma consulta não mostra dados de outra
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestIsolamentoEntreConsultas:

    def test_formulario_novo_nao_traz_dados_da_consulta_anterior(self, client, profissional):
        """Estado residual entre um registro e o seguinte."""
        from consultations.models import Consultation

        client.force_login(profissional)
        dados = {
            'name': 'Paciente Um', 'date': '2026-05-20',
            'clinic_name': 'Clínica Alfa', 'clinic_neighborhood': 'Centro',
            'clinic_city': 'São Paulo', 'diagnosis': 'Cefaleia tensional',
            'prescription': 'Dipirona 500mg',
        }
        client.post(reverse('external_consultation_create'), dados, follow=True)
        assert Consultation.objects.filter(external_patient__name='Paciente Um').exists()

        html = client.get(reverse('external_consultation_create')).content.decode('utf-8')
        for residuo in ('Paciente Um', 'Cefaleia tensional', 'Dipirona 500mg', 'Clínica Alfa'):
            assert residuo not in html, \
                f'Formulário novo veio com dado da consulta anterior: {residuo!r}'

    def test_detalhe_mostra_apenas_os_proprios_anexos(self, client, profissional):
        from consultations.models import Consultation, ConsultationImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(profissional)
        base = {
            'date': '2026-05-20', 'clinic_name': 'Clínica Beta',
            'clinic_neighborhood': 'Centro', 'clinic_city': 'São Paulo',
        }
        client.post(reverse('external_consultation_create'), dict(base, name='Ana Primeira'), follow=True)
        client.post(reverse('external_consultation_create'), dict(base, name='Bruno Segundo'), follow=True)

        c1 = Consultation.objects.get(external_patient__name='Ana Primeira')
        c2 = Consultation.objects.get(external_patient__name='Bruno Segundo')

        png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'\x00' * 20
        for consulta, legenda in ((c1, 'Exame da Ana'), (c2, 'Exame do Bruno')):
            client.post(
                reverse('consultation_upload_image', args=[consulta.pk]),
                {'tab': 'exames', 'caption': legenda,
                 'image': SimpleUploadedFile('e.png', png, content_type='image/png')},
                follow=True,
            )

        html1 = client.get(reverse('consultation_detail', args=[c1.pk])).content.decode('utf-8')
        assert 'Exame da Ana' in html1
        assert 'Exame do Bruno' not in html1, 'Anexo de outra consulta apareceu'
        assert 'Bruno Segundo' not in html1, 'Paciente de outra consulta apareceu'

        anexo_c2 = ConsultationImage.objects.get(consultation=c2)
        url_c2 = reverse('consultation_attachment', args=[c2.pk, anexo_c2.pk])
        assert url_c2 not in html1, 'Link de anexo de outra consulta exposto'
