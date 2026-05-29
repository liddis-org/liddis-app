from django.urls import path
from . import views

urlpatterns = [
    # Consultas do paciente
    path('', views.ConsultationListView.as_view(), name='consultation_list'),
    path('nova/', views.ConsultationCreateView.as_view(), name='consultation_create'),
    path('<uuid:pk>/', views.ConsultationDetailView.as_view(), name='consultation_detail'),
    path('<uuid:pk>/editar/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    path('<uuid:pk>/excluir/', views.ConsultationDeleteView.as_view(), name='consultation_delete'),

    # Meus Atendimentos (profissional)
    path('meus-atendimentos/', views.meus_atendimentos, name='meus_atendimentos'),

    # Perfil clínico do paciente (editado pelo profissional)
    path('<uuid:consultation_pk>/perfil-clinico/', views.patient_clinical_summary, name='patient_clinical_summary'),

    # Sinais vitais
    path('sinais-vitais/', views.VitalSignListView.as_view(), name='vitals'),
    path('sinais-vitais/novo/', views.VitalSignCreateView.as_view(), name='vital_create'),

    # Anexos da consulta (imagens e PDFs)
    path('<uuid:pk>/imagem/', views.upload_image, name='consultation_upload_image'),
    path('<uuid:pk>/imagem/<int:img_pk>/excluir/', views.delete_image, name='consultation_delete_image'),
    path('<uuid:pk>/anexo/<int:img_pk>/', views.attachment_proxy, name='consultation_attachment'),

    # Evoluções multiprofissionais
    path('<uuid:consultation_pk>/evolucoes/', views.evolution_list, name='evolution_list'),
    path('<uuid:consultation_pk>/evolucoes/nova/', views.evolution_create, name='evolution_create'),
    path('<uuid:consultation_pk>/evolucoes/<uuid:pk>/editar/', views.evolution_edit, name='evolution_edit'),

    # Prescrições
    path('<uuid:consultation_pk>/prescricoes/', views.prescription_list, name='prescription_list'),
    path('<uuid:consultation_pk>/prescricoes/nova/', views.prescription_create, name='prescription_create'),

    # Diagnósticos CID-10
    path('<uuid:consultation_pk>/diagnosticos/', views.diagnosis_list, name='diagnosis_list'),
    path('<uuid:consultation_pk>/diagnosticos/novo/', views.diagnosis_create, name='diagnosis_create'),

    # Exame físico
    path('<uuid:consultation_pk>/exame-fisico/', views.physical_exam_view, name='physical_exam_view'),

    # Solicitações de exame laboratorial
    path('<uuid:consultation_pk>/exames-lab/', views.lab_request_list, name='lab_request_list'),
    path('<uuid:consultation_pk>/exames-lab/solicitar/', views.lab_request_create, name='lab_request_create'),
    path('<uuid:consultation_pk>/exames-lab/<uuid:pk>/resultado/', views.lab_result_fill, name='lab_result_fill'),

    # Fluxo de atendimento por token
    path('atendimento/iniciar/', views.iniciar_atendimento, name='iniciar_atendimento'),
    path('atendimento/entrar/', views.entrar_atendimento, name='entrar_atendimento'),
    path('atendimento/<uuid:token>/consulta/', views.atendimento_consulta, name='atendimento_consulta'),
    path('atendimento/<uuid:token>/cancelar/', views.cancelar_sessao, name='cancelar_sessao'),
]
