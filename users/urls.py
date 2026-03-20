from django.urls import path
from .views import (
    RegisterAPIView, MeView, RegisterWebView,
    dashboard, profile,
    verificar_email, verificar_celular,
)

urlpatterns = [
    # Web
    path('register/',  RegisterWebView.as_view(), name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('perfil/',    profile,   name='profile'),

    # Verificação de identidade
    path('verificar/email/',    verificar_email,    name='verificar_email'),
    path('verificar/celular/',  verificar_celular,  name='verificar_celular'),

    # API REST
    path('api-register/', RegisterAPIView.as_view(), name='api_register'),
    path('me/',           MeView.as_view(),          name='me'),
]
