from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Estilos e templates compartilhados para views de autenticação
_PASS_RESET_KWARGS = {
    'template_name':            'users/password_reset.html',
    'email_template_name':      'email/password_reset.txt',
    'html_email_template_name': 'email/password_reset.html',
    'subject_template_name':    'email/password_reset_subject.txt',
    'extra_email_context':      {'site_name': 'LIDDIS'},
}


def api_root(request):
    return JsonResponse({
        'projeto': 'HealthData Hub',
        'status': 'online',
        'versao': '1.0.0',
        'web': {
            'login':      '/login/',
            'cadastro':   '/cadastro/',
            'dashboard':  '/dashboard/',
            'consultas':  '/consultas/',
        },
        'api': {
            'token':   '/api/auth/token/',
            'refresh': '/api/auth/token/refresh/',
            'me':      '/api/auth/me/',
        }
    })


urlpatterns = [
    # Raiz
    path('', api_root, name='api_root'),

    # Admin
    path('admin/', admin.site.urls),

    # Auth (web) — login / logout
    path('login/',  auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ── Recuperação de senha (Django built-in — token com expiração) ───────────
    path('senha/recuperar/',
         auth_views.PasswordResetView.as_view(**_PASS_RESET_KWARGS),
         name='password_reset'),
    path('senha/recuperar/enviado/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('senha/redefinir/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('senha/redefinir/sucesso/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # ── Allauth (Google OAuth + rotas sociais) ─────────────────────────────────
    path('accounts/', include('allauth.urls')),

    # Rotas do app users
    path('', include('users.urls')),

    # Consultas (web)
    path('consultas/', include('consultations.urls')),

    # API REST
    path('api/auth/token/',         TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(),    name='token_refresh'),
]
