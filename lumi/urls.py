from django.urls import path
from . import views

urlpatterns = [
    path('', views.lumi_page, name='lumi'),
    path('relatorio/', views.lumi_report, name='lumi_report'),
]
