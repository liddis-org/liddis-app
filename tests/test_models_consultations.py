"""
Testes dos models do app consultations.
Cobre: Consultation, VitalSign, ConsultationSession, Evolution,
       Prescription, DiagnosisCID, LabRequest.
"""
import pytest
from django.utils import timezone
from datetime import timedelta, date


# ═══════════════════════════════════════════════════════════════════════════════
# Consultation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestConsultation:

    def test_criar_consulta_basica(self, consultation):
        assert consultation.patient is not None
        assert consultation.status == 'active'
        assert consultation.severity == 'low'
        assert consultation.id is not None  # UUID gerado

    def test_specialty_label_padrao(self, consultation):
        consultation.specialty = 'cardiologia'
        assert consultation.specialty_label == 'Cardiologia'

    def test_specialty_label_outro(self, consultation):
        consultation.specialty = 'outro'
        consultation.specialty_other = 'Genética Médica'
        assert consultation.specialty_label == 'Genética Médica'

    def test_specialty_label_outro_sem_texto(self, consultation):
        consultation.specialty = 'outro'
        consultation.specialty_other = ''
        # Deve retornar o label padrão ('Outro') sem quebrar
        assert consultation.specialty_label == 'Outro'

    def test_soft_delete_via_cascade(self, consultation, patient_user):
        """Deletar paciente deve deletar consultas (CASCADE)."""
        from consultations.models import Consultation
        consultation_id = consultation.id
        patient_user.delete()
        assert not Consultation.objects.filter(id=consultation_id).exists()

    def test_ordering_mais_recente_primeiro(self, patient_user):
        from consultations.models import Consultation
        Consultation.objects.create(
            patient=patient_user, date='2024-01-01',
            professional_name='Dr. A', specialty='clinico_geral',
            clinic_name='Clínica A', clinic_neighborhood='N', clinic_city='SP',
        )
        Consultation.objects.create(
            patient=patient_user, date='2025-06-01',
            professional_name='Dr. B', specialty='cardiologia',
            clinic_name='Clínica B', clinic_neighborhood='N', clinic_city='SP',
        )
        consultas = list(Consultation.objects.filter(patient=patient_user))
        assert consultas[0].date > consultas[1].date


# ═══════════════════════════════════════════════════════════════════════════════
# VitalSign
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVitalSign:

    def test_criar_sinal_vital(self, patient_user):
        from consultations.models import VitalSign
        vs = VitalSign.objects.create(
            patient=patient_user,
            date=date.today(),
            blood_pressure='120/80',
            heart_rate=72,
            weight=70.5,
            temperature=36.8,
            oxygen_saturation=98,
        )
        assert vs.id is not None
        assert vs.heart_rate == 72
        assert float(vs.weight) == 70.5

    def test_sinal_vital_campos_opcionais(self, patient_user):
        from consultations.models import VitalSign
        vs = VitalSign.objects.create(
            patient=patient_user,
            date=date.today(),
        )
        assert vs.heart_rate is None
        assert vs.weight is None
        assert vs.blood_pressure == ''


# ═══════════════════════════════════════════════════════════════════════════════
# ConsultationSession
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestConsultationSession:

    def test_criar_sessao(self, patient_user):
        from consultations.models import ConsultationSession
        session = ConsultationSession.objects.create(
            patient=patient_user,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        assert session.token is not None
        assert session.status == 'pending'
        assert session.is_expired is False
        assert session.is_valid is True

    def test_sessao_expirada(self, patient_user):
        from consultations.models import ConsultationSession
        session = ConsultationSession.objects.create(
            patient=patient_user,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert session.is_expired is True
        assert session.is_valid is False

    def test_token_display_8_chars_maiusculo(self, patient_user):
        from consultations.models import ConsultationSession
        session = ConsultationSession.objects.create(
            patient=patient_user,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        display = session.token_display
        assert len(display) == 8
        assert display == display.upper()

    def test_sessao_invalida_quando_nao_pendente(self, patient_user):
        from consultations.models import ConsultationSession
        session = ConsultationSession.objects.create(
            patient=patient_user,
            status='closed',
            expires_at=timezone.now() + timedelta(hours=24),
        )
        assert session.is_valid is False


# ═══════════════════════════════════════════════════════════════════════════════
# Evolution
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEvolution:

    def test_criar_evolucao(self, consultation, doctor_user):
        from consultations.models import Evolution
        evo = Evolution.objects.create(
            consultation=consultation,
            professional=doctor_user,
            category='medical',
            content='Paciente estável. Continuar tratamento.',
            is_visible_to_patient=True,
        )
        assert evo.id is not None
        assert evo.get_category_display() == 'Médica'

    def test_evolucao_nao_visivel_paciente(self, consultation, doctor_user):
        from consultations.models import Evolution
        evo = Evolution.objects.create(
            consultation=consultation,
            professional=doctor_user,
            category='medical',
            content='Nota interna confidencial.',
            is_visible_to_patient=False,
        )
        assert evo.is_visible_to_patient is False


# ═══════════════════════════════════════════════════════════════════════════════
# Prescription
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPrescription:

    def test_criar_prescricao_medica(self, consultation, doctor_user):
        from consultations.models import Prescription
        rx = Prescription.objects.create(
            consultation=consultation,
            prescriber=doctor_user,
            prescription_type='medical',
            medication_name='Amoxicilina',
            dosage='500mg',
            frequency='8 em 8 horas',
            duration='7 dias',
            route='oral',
            is_active=True,
        )
        assert rx.id is not None
        assert rx.get_prescription_type_display() == 'Médica'

    def test_prescricao_inativa(self, consultation, doctor_user):
        from consultations.models import Prescription
        rx = Prescription.objects.create(
            consultation=consultation,
            prescriber=doctor_user,
            prescription_type='medical',
            medication_name='Ibuprofeno',
            is_active=False,
        )
        assert rx.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# DiagnosisCID
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDiagnosisCID:

    def test_criar_diagnostico(self, consultation, doctor_user):
        from consultations.models import DiagnosisCID
        diag = DiagnosisCID.objects.create(
            consultation=consultation,
            professional=doctor_user,
            icd_code='J18.9',
            description='Pneumonia não especificada',
            is_primary=True,
            certainty='confirmed',
        )
        assert diag.id is not None
        assert diag.get_certainty_display() == 'Confirmado'
        assert diag.is_primary is True


# ═══════════════════════════════════════════════════════════════════════════════
# LabRequest
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLabRequest:

    def test_criar_solicitacao_exame(self, consultation, doctor_user):
        from consultations.models import LabRequest
        req = LabRequest.objects.create(
            consultation=consultation,
            requesting_professional=doctor_user,
            exam_type='Hemograma completo',
            urgency=False,
            status='pending',
        )
        assert req.id is not None
        assert req.get_status_display() == 'Pendente'

    def test_exame_urgente(self, consultation, doctor_user):
        from consultations.models import LabRequest
        req = LabRequest.objects.create(
            consultation=consultation,
            requesting_professional=doctor_user,
            exam_type='PCR',
            urgency=True,
        )
        assert req.urgency is True

    def test_registrar_resultado(self, consultation, doctor_user, nurse_user):
        from consultations.models import LabRequest
        req = LabRequest.objects.create(
            consultation=consultation,
            requesting_professional=doctor_user,
            exam_type='Glicemia',
            status='pending',
        )
        req.result = '95 mg/dL'
        req.result_registered_by = nurse_user
        req.status = 'completed'
        req.save()
        req.refresh_from_db()
        assert req.status == 'completed'
        assert req.result == '95 mg/dL'
