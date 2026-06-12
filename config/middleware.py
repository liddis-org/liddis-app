from django.http import HttpResponsePermanentRedirect


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
