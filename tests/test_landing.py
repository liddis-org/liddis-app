"""
Conteúdo e posicionamento da landing page.

A LIDDIS se apresenta como Passaporte de Saúde Digital, não como sistema de
prontuário. Essa distinção não é estilística: define o que a plataforma é
perante o paciente, que é quem controla o próprio histórico. O teste mais
importante deste arquivo é o que reprova qualquer reaparição do termo.
"""
import re

import pytest
from django.urls import reverse


@pytest.fixture
def html(client):
    resp = client.get(reverse('landing'))
    assert resp.status_code == 200
    return resp.content.decode('utf-8')


def _bloco(html, id_inicio, id_fim=None):
    """
    Recorta do `id=` informado até o próximo — e não da primeira aparição do
    nome, que também ocorre em aria-controls, nem até o fim da página, que
    arrastaria o JS do rodapé para dentro da amostra.
    """
    ini = html.index(f'id="{id_inicio}"')
    fim = html.index(f'id="{id_fim}"') if id_fim else len(html)
    return html[ini:fim]


def _secao_planos(html):
    ini = html.index('<section class="pricing"')
    return html[ini:html.index('</section>', ini)]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Posicionamento
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPosicionamento:

    def test_nao_menciona_prontuario(self, html):
        """
        'Prontuário' é o registro sob guarda do profissional, com obrigação
        legal de 20 anos. Apresentar a LIDDIS assim inverteria quem controla
        os dados e contradiria os próprios termos de uso.
        """
        ocorrencias = re.findall(r'prontu\w*', html, re.IGNORECASE)
        assert not ocorrencias, f'Landing voltou a mencionar prontuário: {set(ocorrencias)}'

    def test_apresenta_o_passaporte_de_saude(self, html):
        assert 'Passaporte de Saúde' in html

    def test_mensagem_central_sobre_dados_que_acompanham(self, html):
        assert 'acompanha você' in html or 'acompanhar você' in html
        assert 'presos em diferentes sistemas' in html

    def test_nao_se_apresenta_como_software_de_clinica(self, html):
        for termo in ('gestão clínica para', 'software para clínicas', 'sistema para consultórios'):
            assert termo.lower() not in html.lower(), f'Posicionamento indevido: {termo!r}'


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Narrativa e seções
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestNarrativa:

    def test_secoes_presentes_e_na_ordem(self, html):
        ordem = ['id="problema"', 'id="causa"', 'id="como-funciona"',
                 'id="lumi"', 'id="seguranca"', 'id="planos"']
        posicoes = []
        for marca in ordem:
            assert marca in html, f'Seção ausente: {marca}'
            posicoes.append(html.index(marca))
        assert posicoes == sorted(posicoes), 'Seções fora da ordem narrativa'

    def test_interoperabilidade_mostra_o_fluxo(self, html):
        for fonte in ('SUS', 'Planos de saúde', 'Clínicas', 'Laboratórios', 'Profissionais'):
            assert fonte in html, f'Fonte de dados ausente do fluxo: {fonte}'

    def test_separa_o_que_existe_hoje_da_visao_futura(self, html):
        """Não prometer integração que ainda não existe."""
        assert 'O que a LIDDIS já entrega' in html
        assert 'Onde queremos chegar' in html
        assert 'não integrações já disponíveis' in html, \
            'Falta a ressalva de que a visão futura não está disponível'

    def test_menu_aponta_para_secoes_existentes(self, html):
        ancoras = set(re.findall(r'href="#([a-z-]+)"', html))
        ids = set(re.findall(r'id="([a-z-]+)"', html))
        quebrados = {a for a in ancoras if a not in ids}
        assert not quebrados, f'Links de menu sem destino: {quebrados}'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Planos
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPlanos:

    def test_publicos_separados_em_grupos(self, html):
        assert 'grupo-paciente' in html
        assert 'grupo-profissional' in html
        assert 'Para Pacientes' in html
        assert 'Para Profissionais e Clínicas' in html

    def test_planos_do_paciente(self, html):
        grupo = _bloco(html, 'grupo-paciente', 'grupo-profissional')
        assert 'Free' in grupo and 'R$0' in grupo
        assert 'Premium' in grupo
        assert 'Passaporte de Saúde Digital' in grupo
        assert 'até 2 profissionais' in grupo.lower()
        assert 'Dashboard de acompanhamento' in grupo

    def test_free_declara_o_que_nao_inclui(self, html):
        grupo = _bloco(html, 'grupo-paciente', 'grupo-profissional')
        assert 'plan-feat na' in grupo, 'Plano Free não marca os recursos ausentes'

    def test_professional_limitado_a_um_profissional(self, html):
        grupo = _bloco(html, 'grupo-profissional')
        assert 'Professional' in grupo
        assert 'Limitado a 1 profissional' in grupo

    def test_enterprise_nao_apresenta_preco_fixo(self, html):
        grupo = _bloco(html, 'grupo-profissional')
        assert 'A partir de' in grupo
        assert 'Consulte-nos' in grupo
        assert 'Falar com a LIDDIS' in grupo

    def test_precos_antigos_removidos(self, html):
        for antigo in ('19,90', '29,90'):
            assert antigo not in html, f'Preço antigo ainda na página: {antigo}'

    def test_toggle_nao_colide_com_as_abas_de_funcionalidades(self, html):
        """
        As abas de features usam .tab-btn e o JS delas é global. O seletor do
        toggle de planos precisa ser distinto, senão clicar num grupo apaga o
        painel do outro.
        """
        grupo_planos = _secao_planos(html)
        assert 'tab-btn' not in grupo_planos, \
            'Toggle de planos reutiliza a classe das abas e quebraria ambas'
        assert 'pt-btn' in grupo_planos


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Integridade — nada quebrado pela reescrita
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestIntegridade:

    def test_ctas_de_cadastro_e_login_resolvem(self, html):
        assert reverse('register') in html
        assert reverse('login') in html

    def test_rodape_mantem_os_documentos_juridicos(self, html):
        for rota in ('termos_paciente', 'termos_profissional', 'privacidade'):
            assert reverse(rota) in html, f'Rodapé perdeu o link para {rota}'

    def test_login_continua_acessivel(self, client):
        assert client.get(reverse('login')).status_code == 200

    def test_pagina_nao_vaza_sintaxe_de_template(self, html):
        corpo = re.sub(r'<script\b.*?</script>', '', html, flags=re.S | re.I)
        corpo = re.sub(r'<style\b.*?</style>', '', corpo, flags=re.S | re.I)
        for marca in ('{#', '#}', '{%', '}}'):
            assert marca not in corpo, f'Sintaxe de template visível: {marca}'

    def test_lumi_nao_e_apresentada_como_substituta(self, html):
        """A IA é apoio; apresentá-la como decisória contraria os termos."""
        baixo = html.lower()
        for proibido in ('diagnóstico automático', 'substitui o médico',
                         'substitui o profissional', 'diagnostica por você'):
            assert proibido not in baixo, f'LUMI apresentada indevidamente: {proibido!r}'
