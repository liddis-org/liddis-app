"""
conftest.py — Fixtures compartilhadas entre todos os testes.
O pytest-django lê este arquivo automaticamente.
"""
import pytest
from django.test import Client


# ── Configuração do Django para pytest ────────────────────────────────────────
# O arquivo pytest.ini (na raiz) define: django_settings_module = config.settings


# ── Fixtures de Usuários ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    return Client()


@pytest.fixture
def patient_user(db):
    """Paciente verificado pronto para uso nos testes."""
    from users.models import CustomUser
    user = CustomUser.objects.create_user(
        username='paciente_teste',
        email='paciente@teste.com',
        password='senha_segura_123',
        first_name='Ana',
        last_name='Silva',
        role='PATIENT',
        is_email_verified=True,
    )
    return user


@pytest.fixture
def doctor_user(db):
    """Médico verificado pronto para uso nos testes."""
    from users.models import CustomUser
    user = CustomUser.objects.create_user(
        username='medico_teste',
        email='medico@teste.com',
        password='senha_segura_123',
        first_name='Dr. Carlos',
        last_name='Oliveira',
        role='DOCTOR',
        profession='Médico',
        professional_specialty='clinico_geral',
        is_email_verified=True,
    )
    return user


@pytest.fixture
def nurse_user(db):
    """Enfermeira verificada pronta para uso nos testes."""
    from users.models import CustomUser
    user = CustomUser.objects.create_user(
        username='enfermeira_teste',
        email='enfermeira@teste.com',
        password='senha_segura_123',
        first_name='Beatriz',
        last_name='Santos',
        role='NURSE',
        profession='Enfermeira',
        is_email_verified=True,
    )
    return user


@pytest.fixture
def admin_user(db):
    """Usuário ADMIN verificado."""
    from users.models import CustomUser
    user = CustomUser.objects.create_user(
        username='admin_teste',
        email='admin@teste.com',
        password='senha_segura_123',
        first_name='Admin',
        last_name='Sistema',
        role='ADMIN',
        is_email_verified=True,
        is_staff=True,
    )
    return user


@pytest.fixture
def organization(db):
    """Organização de saúde para testes multi-tenant."""
    from users.models import Organization
    return Organization.objects.create(
        name='Clínica Teste',
        slug='clinica-teste',
        plan='premium',
    )


@pytest.fixture
def consultation(db, patient_user):
    """Consulta básica vinculada ao paciente de teste."""
    from consultations.models import Consultation
    return Consultation.objects.create(
        patient=patient_user,
        date='2025-01-15',
        professional_name='Dr. Teste',
        profession='Médico',
        specialty='clinico_geral',
        clinic_name='Clínica Central',
        clinic_neighborhood='Centro',
        clinic_city='São Paulo',
        status='active',
        severity='low',
    )


@pytest.fixture
def patient_access(db, patient_user, doctor_user):
    """Vínculo ativo entre paciente e médico."""
    from users.models import PatientProfessionalAccess
    return PatientProfessionalAccess.objects.create(
        patient=patient_user,
        professional=doctor_user,
        granted_by=patient_user,
        access_reason='Consulta de rotina',
        is_active=True,
    )


@pytest.fixture
def logged_patient(client, patient_user):
    """Client HTTP já autenticado como paciente."""
    client.force_login(patient_user)
    return client


@pytest.fixture
def logged_doctor(client, doctor_user):
    """Client HTTP já autenticado como médico."""
    client.force_login(doctor_user)
    return client
