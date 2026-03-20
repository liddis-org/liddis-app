from django.urls import path
from . import views

urlpatterns = [
    # Consultas do paciente
    path('', views.ConsultationListView.as_view(), name='consultation_list'),
    path('nova/', views.ConsultationCreateView.as_view(), name='consultation_create'),
    path('<int:pk>/', views.ConsultationDetailView.as_view(), name='consultation_detail'),
    path('<int:pk>/editar/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    path('<int:pk>/excluir/', views.ConsultationDeleteView.as_view(), name='consultation_delete'),

    # Sinais vitais
    path('sinais-vitais/', views.VitalSignListView.as_view(), name='vitals'),
    path('sinais-vitais/novo/', views.VitalSignCreateView.as_view(), name='vital_create'),

    # Fluxo de atendimento por token
    path('atendimento/iniciar/', views.iniciar_atendimento, name='iniciar_atendimento'),
    path('atendimento/entrar/', views.entrar_atendimento, name='entrar_atendimento'),
    path('atendimento/<uuid:token>/consulta/', views.atendimento_consulta, name='atendimento_consulta'),
    path('atendimento/<uuid:token>/cancelar/', views.cancelar_sessao, name='cancelar_sessao'),
]