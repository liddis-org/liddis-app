from django.http import HttpResponsePermanentRedirect


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
