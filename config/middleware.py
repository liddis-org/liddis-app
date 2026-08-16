import ipaddress

from django.conf import settings
from django.http import HttpResponse, HttpResponsePermanentRedirect

# IPs publicados pelo Cloudflare: https://www.cloudflare.com/ips/
_CF_RANGES = [
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22',
    '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20',
    '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32',
    '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32',
]
_CF_NETWORKS = [ipaddress.ip_network(n) for n in _CF_RANGES]


def _is_cloudflare_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str.strip())
        return any(addr in net for net in _CF_NETWORKS)
    except ValueError:
        return False


class CloudflareOnlyMiddleware:
    """
    Bloqueia requisições que chegam diretamente ao URL do Cloud Run (*.run.app)
    sem passar pelo Cloudflare, protegendo contra bypass das regras WAF.

    Cloudflare sempre injeta o header CF-Connecting-IP e seu próprio IP aparece
    no X-Forwarded-For. Verificamos os dois para evitar que alguém finja ser
    o Cloudflare adicionando o header manualmente.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG:
            cf_connecting_ip = request.META.get('HTTP_CF_CONNECTING_IP', '')
            forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
            ips = [ip.strip() for ip in forwarded_for.split(',') if ip.strip()]
            cloudflare_in_chain = any(_is_cloudflare_ip(ip) for ip in ips)

            if not cf_connecting_ip or not cloudflare_in_chain:
                return HttpResponse(
                    'Acesso restrito. Use https://liddis.com.br',
                    status=403,
                    content_type='text/plain; charset=utf-8',
                )

        return self.get_response(request)


class FixCloudRunHostMiddleware:
    """
    O Cloudflare Worker proxy mantém Host: *.run.app para que o Cloud Run aceite
    a requisição. Este middleware corrige o host para liddis.com.br antes que
    qualquer código o leia, garantindo que o allauth construa o redirect_uri
    correto no OAuth do Google (https://liddis.com.br/accounts/google/login/callback/).
    Sem isso, o callback vai direto ao Cloud Run sem o cookie de sessão → falha OAuth.
    """

    _CLOUD_RUN_SUFFIX = '.run.app'
    _REAL_HOST = 'liddis.com.br'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.META.get('HTTP_HOST', '')
        if host.endswith(self._CLOUD_RUN_SUFFIX):
            request.META['HTTP_HOST'] = self._REAL_HOST
        return self.get_response(request)


class RemoveWWWMiddleware:
    """Redireciona permanentemente www.liddis.com.br → liddis.com.br."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        if host.startswith('www.'):
            canonical = host[4:]
            return HttpResponsePermanentRedirect(
                f'https://{canonical}{request.get_full_path()}'
            )
        return self.get_response(request)
