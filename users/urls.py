from django.urls import path
from .views import (
    home,
    RegisterAPIView, MeView, RegisterWebView,
    dashboard, analytics, profile,
    verificar_email, verificar_celular,
    quem_somos,
    my_accesses, grant_access, revoke_access,
    platform_feedback,
)

urlpatterns = [
    # Home (landing page)
    path('home/', home, name='home'),

    # Web
    path('register/',  RegisterWebView.as_view(), name='register'),
    path('dashboard/',  dashboard, name='dashboard'),
    path('analytics/',  analytics, name='analytics'),
    path('perfil/',    profile,   name='profile'),
    path('quem-somos/', quem_somos, name='quem_somos'),
    path('feedback/',  platform_feedback, name='platform_feedback'),

    # Verificação de identidade
    path('verificar/email/',    verificar_email,    name='verificar_email'),
    path('verificar/celular/',  verificar_celular,  name='verificar_celular'),

    # Gestão de vínculos paciente-profissional
    path('vinculos/',                      my_accesses,  name='my_accesses'),
    path('vinculos/conceder/',             grant_access, name='grant_access'),
    path('vinculos/revogar/<uuid:access_id>/', revoke_access, name='revoke_access'),

    # API REST
    path('api-register/', RegisterAPIView.as_view(), name='api_register'),
    path('me/',           MeView.as_view(),          name='me'),
]
