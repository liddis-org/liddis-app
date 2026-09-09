"""
Testes do endpoint de health check.

Duas garantias importam aqui: que o endpoint acuse falha em vez de responder
200 às cegas, e que não vaze detalhes de infraestrutura para quem não é staff —
mensagens de erro de banco carregam host, usuário e nome da base.
"""
import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHealthCheck:

    def test_responde_ok_com_tudo_de_pe(self, client):
        resp = client.get(reverse('health'))
        assert resp.status_code == 200
        corpo = json.loads(resp.content)
        assert corpo['status'] == 'ok'
        assert corpo['checagens']['banco'] == 'ok'
        assert 'timestamp' in corpo

    def test_cobre_banco_storage_e_oauth(self, client):
        corpo = json.loads(client.get(reverse('health')).content)
        assert set(corpo['checagens']) == {'banco', 'storage', 'oauth'}

    def test_acusa_503_quando_dependencia_cai(self, client, monkeypatch):
        """Responder 200 com o banco fora tornaria o monitoramento inútil."""
        monkeypatch.setattr(
            'config.health._checar_banco',
            lambda: (False, 'OperationalError: could not connect'),
        )
        # A tupla de verificações é montada na importação — refaz com o mock.
        import config.health as h
        monkeypatch.setattr(h, '_VERIFICACOES', (
            ('banco', h._checar_banco),
            ('storage', h._checar_storage),
            ('oauth', h._checar_config_oauth),
        ))

        resp = client.get(reverse('health'))
        assert resp.status_code == 503
        corpo = json.loads(resp.content)
        assert corpo['status'] == 'degradado'
        assert corpo['checagens']['banco'] == 'falha'

    def test_nao_vaza_detalhe_de_infra_para_anonimo(self, client, monkeypatch):
        import config.health as h
        monkeypatch.setattr(
            'config.health._checar_banco',
            lambda: (False, 'OperationalError: host=db-interno senha invalida'),
        )
        monkeypatch.setattr(h, '_VERIFICACOES', (
            ('banco', h._checar_banco),
            ('storage', h._checar_storage),
            ('oauth', h._checar_config_oauth),
        ))

        resp = client.get(reverse('health') + '?detalhe=1')
        corpo = json.loads(resp.content)
        assert 'detalhes' not in corpo, 'Endpoint aberto expôs detalhe de infraestrutura'
        assert b'db-interno' not in resp.content

    def test_staff_ve_o_detalhe(self, client, monkeypatch, admin_user):
        import config.health as h
        monkeypatch.setattr(
            'config.health._checar_banco',
            lambda: (False, 'OperationalError: host=db-interno'),
        )
        monkeypatch.setattr(h, '_VERIFICACOES', (
            ('banco', h._checar_banco),
            ('storage', h._checar_storage),
            ('oauth', h._checar_config_oauth),
        ))

        client.force_login(admin_user)
        corpo = json.loads(client.get(reverse('health') + '?detalhe=1').content)
        assert 'detalhes' in corpo
        assert 'banco' in corpo['detalhes']

    def test_dispensa_autenticacao(self, client):
        """Monitor externo não faz login — o endpoint precisa responder anônimo."""
        resp = client.get(reverse('health'))
        assert resp.status_code in (200, 503)
