"""
Health check das dependências críticas.

Serve para detectar indisponibilidade antes que um usuário reporte. Responde
200 quando tudo que o sistema precisa para operar está de pé e 503 quando algo
essencial caiu — formato que monitores externos e o Cloud Run entendem sem
configuração adicional.

A resposta pública é deliberadamente pobre em detalhes: diz o que está de pé,
nunca por que caiu. Mensagens de erro de banco carregam host, usuário e nome de
base, e este endpoint é aberto.
"""
import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone

_log = logging.getLogger('liddis')


def _checar_banco():
    """Uma consulta trivial: confirma conexão, autenticação e resposta."""
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        return True, None
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def _checar_storage():
    """
    Confirma que o backend de arquivos responde. Sem isto, anexos de consulta
    falham silenciosamente — o registro é criado e o arquivo se perde.
    """
    try:
        from django.core.files.storage import default_storage
        default_storage.exists('health-check-probe')
        return True, None
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def _checar_config_oauth():
    """
    O login com Google depende de três coisas alinhadas: credenciais presentes
    e o Site do Django com o domínio certo, de onde o allauth monta o
    redirect_uri. Domínio errado aqui gera redirect_uri que o Google recusa.
    """
    try:
        from django.contrib.sites.models import Site

        provedor = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {})
        if not provedor.get('client_id') or not provedor.get('secret'):
            return False, 'credenciais_google_ausentes'

        site = Site.objects.get(id=settings.SITE_ID)
        if not settings.DEBUG and site.domain != settings.SITE_DOMAIN:
            return False, f'site_divergente:{site.domain}!={settings.SITE_DOMAIN}'
        return True, None
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


_VERIFICACOES = (
    ('banco',   _checar_banco),
    ('storage', _checar_storage),
    ('oauth',   _checar_config_oauth),
)


def health(request):
    """
    GET /health/ — estado das dependências.

    `?detalhe=1` acrescenta a causa de cada falha, e só é atendido para staff:
    a causa costuma conter host e credencial parcial.
    """
    resultados, falhas = {}, []

    for nome, verificar in _VERIFICACOES:
        ok, motivo = verificar()
        resultados[nome] = 'ok' if ok else 'falha'
        if not ok:
            falhas.append((nome, motivo))

    if falhas:
        _log.error(
            'health_check_falhou | componentes=%s | ambiente=%s',
            ', '.join(f'{n}={m}' for n, m in falhas),
            'desenvolvimento' if settings.DEBUG else 'producao',
        )

    corpo = {
        'status':    'degradado' if falhas else 'ok',
        'checagens': resultados,
        'timestamp': timezone.now().isoformat(),
    }

    detalhar = request.GET.get('detalhe') and getattr(request.user, 'is_staff', False)
    if detalhar and falhas:
        corpo['detalhes'] = {nome: motivo for nome, motivo in falhas}

    return JsonResponse(corpo, status=503 if falhas else 200)
