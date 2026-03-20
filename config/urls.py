from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


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

    # Auth (web)
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('users.urls')),

    # Consultas (web)
    path('consultas/', include('consultations.urls')),

    # API REST
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
