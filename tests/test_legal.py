"""
Documentos jurídicos e registro de consentimento.

Duas garantias sustentam este módulo. A primeira é de acesso: os termos
precisam ser legíveis por quem ainda não tem conta — é antes de se cadastrar
que a pessoa decide se aceita. A segunda é probatória: anos depois é preciso
demonstrar qual versão exata cada pessoa aceitou, e por isso o aceite guarda
versão, data, IP e papel, e nunca é sobrescrito.
"""
import re

import pytest
from django.conf import settings
from django.urls import reverse

from legal.models import TermsAcceptance, TermsDocument


# Campos do modelo original que precisam ter sido substituídos pelos dados reais.
_PLACEHOLDERS = [
    'RAZÃO SOCIAL', '[CNPJ]', 'ENDEREÇO COMPLETO', 'NOME DO ENCARREGADO',
    'COMARCA DA SEDE', 'privacidade@liddis.com.br', 'suporte@liddis.com.br',
]


@pytest.fixture
def profissional(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='prof_legal', email='prof_legal@test.com', password='Senha@1234',
        first_name='Regina', last_name='Alves', role='DOCTOR',
        profession='Médica', is_email_verified=True,
    )


@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_legal', email='pac_legal@test.com', password='Senha@1234',
        role='PATIENT', is_email_verified=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Acesso público
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAcessoPublico:

    def test_termos_do_profissional_sem_login(self, client):
        resp = client.get(reverse('termos_profissional'))
        assert resp.status_code == 200, 'Termos exigiram autenticação'

    def test_rota_generica_e_privacidade_sem_login(self, client):
        for nome in ('termos', 'privacidade'):
            assert client.get(reverse(nome)).status_code == 200

    def test_profissional_logado_ve_o_documento_do_seu_papel(self, client, profissional):
        client.force_login(profissional)
        html = client.get(reverse('termos')).content.decode('utf-8')
        assert 'Profissional' in html


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Conteúdo — nenhum campo do modelo ficou por preencher
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestConteudo:

    def test_dados_oficiais_da_empresa_aparecem(self, client):
        html = client.get(reverse('termos_profissional')).content.decode('utf-8')
        assert settings.EMPRESA['razao_social'] in html
        assert settings.EMPRESA['cnpj'] in html
        assert 'Fernando Ferrari' in html
        assert settings.EMPRESA['email_suporte'] in html

    def test_nenhum_placeholder_do_modelo_sobrou(self, client):
        html = client.get(reverse('termos_profissional')).content.decode('utf-8')
        restantes = [p for p in _PLACEHOLDERS if p in html]
        assert not restantes, f'Campos do modelo não preenchidos: {restantes}'

    def test_clausulas_estruturais_presentes(self, client):
        """Amostra de cláusulas que não podem sumir numa reformatação."""
        html = client.get(reverse('termos_profissional')).content.decode('utf-8')
        for trecho in (
            'Acordo de Tratamento de Dados',
            '20 anos',                      # guarda do prontuário
            'ferramenta de apoio',          # LUMI
            'Resolução CFM nº 2.454/2026',
            'Operadora',
            '90 dias',                      # exportação após cancelamento
            '48 horas',                     # notificação de incidente
        ):
            assert trecho in html, f'Cláusula ausente do documento: {trecho!r}'

    def test_pagina_nao_vaza_sintaxe_de_template(self, client):
        html = client.get(reverse('termos_profissional')).content.decode('utf-8')
        corpo = re.sub(r'<script\b.*?</script>', '', html, flags=re.S | re.I)
        for marca in ('{#', '#}', '{%', '}}'):
            assert marca not in corpo, f'Sintaxe de template visível: {marca}'


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Versionamento
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVersionamento:

    def test_versao_1_0_do_profissional_esta_publicada(self):
        doc = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        assert doc is not None, 'Nenhuma versão vigente — a migration de seed não rodou'
        assert doc.versao == '1.0'

    def test_versao_futura_nao_entra_em_vigor_antes_da_data(self):
        """Permite cadastrar a próxima versão com os 30 dias de aviso prévio."""
        from datetime import timedelta
        from django.utils import timezone

        TermsDocument.objects.create(
            tipo=TermsDocument.Tipo.PROFISSIONAL, versao='2.0',
            titulo='Termos v2', template='legal/professional_v1_0.html',
            vigente_desde=timezone.localdate() + timedelta(days=30),
        )
        assert TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL).versao == '1.0'

    def test_documento_escolhido_segue_o_papel(self):
        assert TermsDocument.para_papel('DOCTOR').tipo == TermsDocument.Tipo.PROFISSIONAL
        assert TermsDocument.para_papel('NURSE').tipo == TermsDocument.Tipo.PROFISSIONAL
        assert TermsDocument.para_papel('PATIENT').tipo == TermsDocument.Tipo.PACIENTE


# ═══════════════════════════════════════════════════════════════════════════════
# 3b. Documento do paciente
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDocumentoDoPaciente:

    def test_versao_1_0_publicada(self):
        doc = TermsDocument.vigente(TermsDocument.Tipo.PACIENTE)
        assert doc is not None, 'Termos do paciente não publicados'
        assert doc.versao == '1.0'

    def test_acessivel_sem_login(self, client):
        assert client.get(reverse('termos_paciente')).status_code == 200

    def test_visitante_anonimo_recebe_o_documento_do_paciente(self, client):
        html = client.get(reverse('termos')).content.decode('utf-8')
        assert 'Usuário' in html and 'SAMU' in html, \
            'Rota genérica deveria levar o visitante ao documento do paciente'

    def test_paciente_logado_ve_o_proprio_documento(self, client, paciente):
        client.force_login(paciente)
        html = client.get(reverse('termos')).content.decode('utf-8')
        assert 'SAMU' in html

    def test_nenhum_placeholder_do_modelo_sobrou(self, client):
        html = client.get(reverse('termos_paciente')).content.decode('utf-8')
        restantes = [p for p in _PLACEHOLDERS if p in html]
        assert not restantes, f'Campos do modelo não preenchidos: {restantes}'

    def test_clausulas_proprias_do_paciente(self, client):
        """
        Amostra do que distingue este documento do profissional: emergência,
        menor de idade, direitos do titular e o que a LIDDIS nunca faz.
        """
        html = client.get(reverse('termos_paciente')).content.decode('utf-8')
        for trecho in (
            '192',                              # emergência
            'Lei nº 15.211/2025',               # ECA Digital
            'não presta serviços médicos',
            'Código de Atendimento',
            'seleção de riscos',                # vedação a planos/seguradoras
            'gov.br/anpd',
            'foro do domicílio do Usuário',
            'Registro Auto-relatado',
        ):
            assert trecho in html, f'Cláusula ausente do documento: {trecho!r}'

    def test_nao_impoe_ao_paciente_obrigacao_do_profissional(self, client):
        """
        A guarda de 20 anos é do Profissional. No documento do paciente ela só
        aparece para explicar por que a exclusão da conta não apaga o prontuário.
        """
        html = client.get(reverse('termos_paciente')).content.decode('utf-8')
        assert 'sob responsabilidade do Profissional' in html
        assert 'Acordo de Tratamento de Dados' not in html, \
            'DPA é documento do profissional e não deve constar do termo do paciente'

    def test_aponta_para_o_documento_do_profissional(self, client):
        html = client.get(reverse('termos_paciente')).content.decode('utf-8')
        assert reverse('termos_profissional') in html, \
            'Cláusula 1.3 deveria linkar o documento do profissional'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Registro do aceite
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAceite:

    def test_aceite_guarda_versao_papel_e_evidencia(self, profissional, rf):
        req = rf.post('/register/', HTTP_USER_AGENT='Mozilla/5.0 Teste')
        req.META['REMOTE_ADDR'] = '203.0.113.7'

        doc = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        aceite = TermsAcceptance.registrar(
            profissional, doc, request=req, declarou_habilitacao=True,
        )

        assert aceite.versao == doc.versao
        assert aceite.tipo_documento == 'professional'
        assert aceite.papel == 'DOCTOR'
        assert aceite.ip == '203.0.113.7'
        assert 'Teste' in aceite.user_agent
        assert aceite.declarou_habilitacao is True
        assert aceite.aceitou_marketing is False
        assert aceite.aceito_em is not None

    def test_nova_versao_torna_o_aceite_pendente(self, profissional):
        from datetime import timedelta
        from django.utils import timezone

        doc1 = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        TermsAcceptance.registrar(profissional, doc1)
        assert TermsAcceptance.pendente_para(profissional) is None

        # Data igual ou posterior à da versão atual: é o que a faz entrar em vigor.
        TermsDocument.objects.create(
            tipo=TermsDocument.Tipo.PROFISSIONAL, versao='2.0',
            titulo='Termos v2', template='legal/professional_v1_0.html',
            vigente_desde=max(doc1.vigente_desde, timezone.localdate()),
            exige_novo_aceite=True,
        )
        pendente = TermsAcceptance.pendente_para(profissional)
        assert pendente is not None and pendente.versao == '2.0', \
            'Versão nova deveria exigir novo aceite'

    def test_correcao_de_forma_nao_interrompe_o_uso(self, profissional):
        from datetime import timedelta
        from django.utils import timezone

        doc1 = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        TermsAcceptance.registrar(profissional, doc1)
        TermsDocument.objects.create(
            tipo=TermsDocument.Tipo.PROFISSIONAL, versao='1.1',
            titulo='Termos v1.1', template='legal/professional_v1_0.html',
            vigente_desde=max(doc1.vigente_desde, timezone.localdate()),
            exige_novo_aceite=False,
        )
        assert TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL).versao == '1.1', \
            'A v1.1 deveria estar vigente para o teste ser significativo'
        assert TermsAcceptance.pendente_para(profissional) is None

    def test_historico_de_aceites_e_preservado(self, profissional):
        doc = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        TermsAcceptance.registrar(profissional, doc)
        TermsAcceptance.registrar(profissional, doc, origem=TermsAcceptance.Origem.REACEITE)
        assert TermsAcceptance.objects.filter(usuario=profissional).count() == 2, \
            'Aceite foi sobrescrito em vez de acrescentado'

    def test_documento_com_aceite_nao_pode_ser_apagado(self, profissional):
        """PROTECT: apagar a versão apagaria a prova de quem a aceitou."""
        from django.db.models import ProtectedError

        doc = TermsDocument.vigente(TermsDocument.Tipo.PROFISSIONAL)
        TermsAcceptance.registrar(profissional, doc)
        with pytest.raises(ProtectedError):
            doc.delete()
