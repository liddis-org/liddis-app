"""
Testes dos templates de e-mail.

O foco é a regra que já falhou uma vez: nenhum template de e-mail pode depender
de recurso hospedado fora do domínio. Em e-mail isso quebra de três formas —
o serviço externo sai do ar, a maioria dos clientes bloqueia imagem remota por
padrão, e cada abertura entrega o IP do destinatário a um terceiro. Em e-mail
de código de verificação, o vazamento é o mais sério dos três.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.template.loader import render_to_string


EMAIL_DIRS = ('email', 'emails')

# Recurso remoto embutido no corpo do e-mail (imagem, script, folha de estilo).
# Links clicáveis em <a href> são legítimos e ficam fora da regra.
_RECURSO_REMOTO = re.compile(r"""(?:src|background)\s*=\s*["']https?://([^"'/]+)""", re.I)

# Domínios próprios são aceitáveis: o servidor é nosso e não há terceiro no meio.
_PERMITIDOS = ('liddis.com.br', 'www.liddis.com.br', 'storage.googleapis.com')


def _templates_de_email():
    raiz = Path(settings.BASE_DIR) / 'templates'
    for pasta in EMAIL_DIRS:
        yield from sorted((raiz / pasta).glob('*.html'))


def test_existe_ao_menos_um_template_para_auditar():
    """Protege o teste abaixo de passar por não ter encontrado arquivo nenhum."""
    assert list(_templates_de_email()), 'Nenhum template de e-mail localizado'


@pytest.mark.parametrize(
    'caminho', list(_templates_de_email()), ids=lambda p: f'{p.parent.name}/{p.name}'
)
def test_template_nao_carrega_recurso_de_terceiro(caminho):
    html = caminho.read_text(encoding='utf-8')
    externos = [
        host for host in _RECURSO_REMOTO.findall(html)
        if not any(host == p or host.endswith('.' + p) for p in _PERMITIDOS)
    ]
    assert not externos, (
        f'{caminho.name} carrega recurso de terceiro: {externos}. '
        'Use marcação inline ou anexe o recurso ao e-mail.'
    )


@pytest.mark.django_db
class TestEmailDeVerificacao:

    CTX = {'first_name': 'Ana', 'code': '482913', 'channel': 'e-mail'}

    def test_renderiza_com_o_codigo_visivel(self):
        html = render_to_string('email/otp.html', self.CTX)
        assert self.CTX['code'] in html, 'O código de verificação não aparece no e-mail'
        assert self.CTX['first_name'] in html

    def test_versao_texto_tambem_traz_o_codigo(self):
        txt = render_to_string('email/otp.txt', self.CTX)
        assert self.CTX['code'] in txt

    def test_logo_e_inline_e_nao_imagem_remota(self):
        html = render_to_string('email/otp.html', self.CTX)
        assert 'via.placeholder.com' not in html, \
            'Logo voltou a apontar para serviço externo de placeholder'
        assert not _RECURSO_REMOTO.findall(html), \
            'E-mail de verificação carrega recurso remoto'
