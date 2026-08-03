from django.urls import path
from . import views

urlpatterns = [
    # Paciente
    path('',                        views.PatientAppointmentListView.as_view(), name='appointment_list'),
    path('novo/',                   views.appointment_create,                   name='appointment_create'),
    path('<uuid:pk>/',              views.AppointmentDetailView.as_view(),      name='appointment_detail'),
    path('<uuid:pk>/cancelar/',     views.appointment_cancel,                   name='appointment_cancel'),
    path('<uuid:pk>/remarcar/',     views.appointment_reschedule,               name='appointment_reschedule'),

    # Profissional
    path('agenda/',                         views.professional_agenda,          name='professional_agenda'),
    path('disponibilidade/',                views.manage_availability,          name='manage_availability'),
    path('disponibilidade/<uuid:pk>/excluir/', views.delete_availability,       name='delete_availability'),
    path('<uuid:pk>/iniciar/',              views.iniciar_atendimento_agendamento, name='iniciar_atendimento_agendamento'),
    path('<uuid:pk>/status/<str:new_status>/', views.appointment_mark_status,  name='appointment_mark_status'),

    # AJAX
    path('api/slots/',              views.available_slots,                      name='available_slots'),
]
