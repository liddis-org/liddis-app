"""
Testes dos models do app users.
Cobre: CustomUser, Organization, PatientProfile, VerificationCode,
       PatientProfessionalAccess, AuditLog.
"""
import pytest
from django.utils import timezone
from datetime import timedelta


# ═══════════════════════════════════════════════════════════════════════════════
# CustomUser
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCustomUser:

    def test_criar_paciente(self):
        from users.models import CustomUser
        user = CustomUser.objects.create_user(
            username='joao',
            email='joao@teste.com',
            password='Senha@123',
            role='PATIENT',
        )
        assert user.role == 'PATIENT'
        assert user.is_email_verified is False
        assert user.deleted_at is None
        assert user.uid is not None

    def test_display_name_retorna_nome_completo(self, patient_user):
        patient_user.first_name = 'Maria'
        patient_user.last_name = 'Santos'
        patient_user.save()
        assert patient_user.display_name == 'Maria Santos'

    def test_display_name_fallback_username(self):
        from users.models import CustomUser
        user = CustomUser.objects.create_user(username='user123', email='u@teste.com', password='Senha@123')
        assert user.display_name == 'user123'

    def test_soft_delete(self, patient_user):
        patient_user.soft_delete()
        patient_user.refresh_from_db()
        assert patient_user.is_deleted is True
        assert patient_user.is_active is False
        assert patient_user.deleted_at is not None

    def test_age_calculado_corretamente(self, patient_user):
        from datetime import date
        patient_user.date_of_birth = date(1990, 6, 15)
        patient_user.save()
        # Idade deve ser um inteiro positivo
        assert isinstance(patient_user.age, int)
        assert patient_user.age > 0

    def test_age_none_sem_data_nascimento(self, patient_user):
        patient_user.date_of_birth = None
        assert patient_user.age is None

    def test_email_unico(self, patient_user):
        from users.models import CustomUser
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CustomUser.objects.create_user(
                username='outro_user',
                email=patient_user.email,  # mesmo e-mail
                password='Senha@123',
            )

    def test_role_choices_validos(self):
        from users.models import CustomUser
        roles_validos = [r[0] for r in CustomUser.Role.choices]
        assert 'PATIENT' in roles_validos
        assert 'DOCTOR' in roles_validos
        assert 'BIOMEDICO' in roles_validos
        assert 'ADMIN' in roles_validos
        assert len(roles_validos) == 13


# ═══════════════════════════════════════════════════════════════════════════════
# Organization
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOrganization:

    def test_criar_organizacao(self, organization):
        assert organization.name == 'Clínica Teste'
        assert organization.slug == 'clinica-teste'
        assert organization.is_active is True
        assert organization.is_deleted is False

    def test_soft_delete_organizacao(self, organization):
        organization.soft_delete()
        organization.refresh_from_db()
        assert organization.is_deleted is True
        assert organization.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# VerificationCode
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVerificationCode:

    def test_gerar_codigo_email(self, patient_user):
        from users.models import VerificationCode
        code = VerificationCode.generate(patient_user, purpose='email')
        assert len(code.code) == 6
        assert code.code.isdigit()
        assert code.is_valid is True
        assert code.is_expired is False

    def test_codigo_expira_em_10_minutos(self, patient_user):
        from users.models import VerificationCode
        code = VerificationCode.generate(patient_user, purpose='email')
        expected_expiry = timezone.now() + timedelta(minutes=10)
        diff = abs((code.expires_at - expected_expiry).total_seconds())
        assert diff < 5  # margem de 5 segundos

    def test_codigo_expirado_invalido(self, patient_user):
        from users.models import VerificationCode
        code = VerificationCode.generate(patient_user, purpose='email')
        code.expires_at = timezone.now() - timedelta(minutes=1)
        code.save()
        assert code.is_expired is True
        assert code.is_valid is False

    def test_generate_invalida_codigos_anteriores(self, patient_user):
        from users.models import VerificationCode
        code1 = VerificationCode.generate(patient_user, purpose='email')
        code2 = VerificationCode.generate(patient_user, purpose='email')
        code1.refresh_from_db()
        assert code1.is_used is True
        assert code2.is_valid is True

    def test_codigo_marcado_como_usado(self, patient_user):
        from users.models import VerificationCode
        code = VerificationCode.generate(patient_user, purpose='email')
        code.is_used = True
        code.save()
        assert code.is_valid is False


# ═══════════════════════════════════════════════════════════════════════════════
# PatientProfessionalAccess
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPatientProfessionalAccess:

    def test_criar_vinculo(self, patient_user, doctor_user):
        from users.models import PatientProfessionalAccess
        vinculo = PatientProfessionalAccess.objects.create(
            patient=patient_user,
            professional=doctor_user,
            granted_by=patient_user,
            access_reason='Acompanhamento mensal',
        )
        assert vinculo.is_active is True
        assert vinculo.revoked_at is None

    def test_revogar_vinculo(self, patient_access):
        patient_access.revoke()
        patient_access.refresh_from_db()
        assert patient_access.is_active is False
        assert patient_access.revoked_at is not None

    def test_vinculo_unico_por_par(self, patient_user, doctor_user):
        from users.models import PatientProfessionalAccess
        from django.db import IntegrityError
        PatientProfessionalAccess.objects.create(
            patient=patient_user,
            professional=doctor_user,
        )
        with pytest.raises(IntegrityError):
            PatientProfessionalAccess.objects.create(
                patient=patient_user,
                professional=doctor_user,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# AuditLog
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAuditLog:

    def test_criar_log_auditoria(self, patient_user, doctor_user):
        from users.models import AuditLog
        log = AuditLog.objects.create(
            actor=doctor_user,
            action='view',
            resource_type='consultation',
            resource_id='abc-123',
            patient=patient_user,
            ip_address='127.0.0.1',
            success=True,
        )
        assert log.id is not None
        assert log.timestamp is not None
        assert log.detail == {}

    def test_log_com_detail_json(self, doctor_user):
        from users.models import AuditLog
        detalhe = {'consulta_id': 'abc', 'motivo': 'revisão'}
        log = AuditLog.objects.create(
            actor=doctor_user,
            action='edit',
            resource_type='consultation',
            detail=detalhe,
        )
        log.refresh_from_db()
        assert log.detail['motivo'] == 'revisão'
