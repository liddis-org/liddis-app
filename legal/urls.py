from django.urls import path

from . import views

urlpatterns = [
    path('termos/',                views.termos,               name='termos'),
    path('termos/profissional/',   views.termos_profissional,  name='termos_profissional'),
    path('termos/paciente/',       views.termos_paciente,      name='termos_paciente'),
    # A política de privacidade integra o mesmo documento (Parte II); a rota
    # existe porque o rodapé e o cadastro a referenciam por nome próprio.
    path('privacidade/',           views.termos,               name='privacidade'),
]
