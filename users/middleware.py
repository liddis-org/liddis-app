from django.shortcuts import redirect

# URLs que não exigem e-mail verificado
_EXEMPT = (
    '/login/',
    '/logout/',
    '/register/',
    '/verificar/',
    '/admin/',
    '/api/',
    '/static/',
    '/media/',
)


class EmailVerificationMiddleware:
    """
    Redireciona usuários logados mas com e-mail não verificado
    para a página de verificação OTP.
    Não afeta as rotas isentas listadas em _EXEMPT.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_email_verified
            and not any(request.path.startswith(p) for p in _EXEMPT)
        ):
            return redirect('/verificar/email/')
        return self.get_response(request)
