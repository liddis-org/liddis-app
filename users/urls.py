from django.urls import path
from .views import (
    home,
    RegisterAPIView, MeView, RegisterWebView,
    dashboard, profile,
    verificar_email, verificar_celular,
    quem_somos,
)

urlpatterns = [
    # Home (landing page)
    path('home/', home, name='home'),

    # Web
    path('register/',  RegisterWebView.as_view(), name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('perfil/',    profile,   name='profile'),
    path('quem-somos/', quem_somos, name='quem_somos'),

    # Verificação de identidade
    path('verificar/email/',    verificar_email,    name='verificar_email'),
    path('verificar/celular/',  verificar_celular,  name='verificar_celular'),

    # API REST
    path('api-register/', RegisterAPIView.as_view(), name='api_register'),
    path('me/',           MeView.as_view(),          name='me'),
]
