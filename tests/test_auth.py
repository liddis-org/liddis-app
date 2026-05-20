"""
Testes de autenticação, registro e verificação de e-mail.
"""
import pytest
from django.urls import reverse


# ═══════════════════════════════════════════════════════════════════════════════
# Registro de usuário
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRegistro:

    def test_registro_valido(self, client):
        url = reverse('users:register')
        dados = {
            'first_name': 'Carlos',
            'last_name': 'Pereira',
            'email': 'carlos@teste.com',
            'username': 'carlos_pereira',
            'role': 'PATIENT',
            'password1': 'SenhaSegura@2025',
            'password2': 'SenhaSegura@2025',
        }
        response = client.post(url, dados)
        # Deve redirecionar após registro bem-sucedido
        assert response.status_code in [200, 302]

        from users.models import CustomUser
        assert CustomUser.objects.filter(email='carlos@teste.com').exists()

    def test_registro_email_duplicado(self, client, patient_user):
        url = reverse('users:register')
        dados = {
            'first_name': 'Outro',
            'last_name': 'Usuário',
            'email': patient_user.email,  # e-mail já existente
            'username': 'outro_usuario',
            'role': 'PATIENT',
            'password1': 'SenhaSegura@2025',
            'password2': 'SenhaSegura@2025',
        }
        response = client.post(url, dados)
        assert response.status_code == 200  # volta ao form com erros
        assert b'e-mail' in response.content.lower() or b'email' in response.content.lower()

    def test_registro_senha_fraca(self, client):
        url = reverse('users:register')
        dados = {
            'first_name': 'Teste',
            'last_name': 'Usuario',
            'email': 'fraco@teste.com',
            'username': 'usuario_fraco',
            'role': 'PATIENT',
            'password1': 'senha',        # senha fraca
            'password2': 'senha',
        }
        response = client.post(url, dados)
        assert response.status_code == 200  # form rejeitado

    def test_registro_senha_divergente(self, client):
        url = reverse('users:register')
        dados = {
            'first_name': 'Teste',
            'last_name': 'Usuario',
            'email': 'divergente@teste.com',
            'username': 'usuario_div',
            'role': 'PATIENT',
            'password1': 'SenhaSegura@2025',
            'password2': 'SenhaSegura@2026',  # diferente
        }
        response = client.post(url, dados)
        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Login
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLogin:

    def test_login_por_email(self, client, patient_user):
        response = client.post('/login/', {
            'username': patient_user.email,
            'password': 'senha_segura_123',
        })
        assert response.status_code == 302  # redireciona após login

    def test_login_por_username(self, client, patient_user):
        response = client.post('/login/', {
            'username': patient_user.username,
            'password': 'senha_segura_123',
        })
        assert response.status_code == 302

    def test_login_senha_errada(self, client, patient_user):
        response = client.post('/login/', {
            'username': patient_user.email,
            'password': 'senha_errada',
        })
        assert response.status_code == 200  # fica na página de login

    def test_login_usuario_inexistente(self, client):
        response = client.post('/login/', {
            'username': 'nao_existe@teste.com',
            'password': 'qualquer',
        })
        assert response.status_code == 200

    def test_usuario_nao_autenticado_redirecionado(self, client):
        response = client.get('/dashboard/')
        assert response.status_code == 302
        assert '/login/' in response['Location']


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard — acesso por papel
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboard:

    def test_dashboard_paciente_autenticado(self, logged_patient):
        response = logged_patient.get('/dashboard/')
        assert response.status_code == 200

    def test_dashboard_medico_autenticado(self, logged_doctor):
        response = logged_doctor.get('/dashboard/')
        assert response.status_code == 200

    def test_dashboard_sem_login_redireciona(self, client):
        response = client.get('/dashboard/')
        assert response.status_code == 302


# ═══════════════════════════════════════════════════════════════════════════════
# Verificação de E-mail
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVerificacaoEmail:

    def test_verificar_codigo_valido(self, client, patient_user):
        from users.models import VerificationCode
        patient_user.is_email_verified = False
        patient_user.save()
        code_obj = VerificationCode.generate(patient_user, purpose='email')

        client.force_login(patient_user)
        response = client.post('/verificar/email/', {'codigo': code_obj.code})
        # Deve redirecionar após verificação
        assert response.status_code in [200, 302]

    def test_verificar_codigo_expirado(self, client, patient_user):
        from users.models import VerificationCode
        from django.utils import timezone
        from datetime import timedelta

        patient_user.is_email_verified = False
        patient_user.save()
        code_obj = VerificationCode.generate(patient_user, purpose='email')
        code_obj.expires_at = timezone.now() - timedelta(minutes=1)
        code_obj.save()

        client.force_login(patient_user)
        response = client.post('/verificar/email/', {'codigo': code_obj.code})
        assert response.status_code == 200  # volta ao form com erro
