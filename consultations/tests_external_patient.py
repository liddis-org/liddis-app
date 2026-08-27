"""
7 testes de validação — funcionalidade: Pacientes sem conta LIDDIS.

Cenários:
  T1 — ExternalPatient é criado e salvo com campos obrigatórios
  T2 — Consultation com external_patient (sem patient LIDDIS) é válida
  T3 — VitalSign pode ser criado com external_patient (patient nullable)
  T4 — consultation_image_path usa consultation.id quando patient é null
  T5 — patient_display_name e patient_email_display retornam dados do paciente externo
  T6 — _accessible_consultations inclui consultas externas criadas pelo profissional
  T7 — external_consultation_create: POST válido → cria ExternalPatient + Consultation
"""

import django
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import CustomUser, ExternalPatient
from consultations.models import Consultation, VitalSign, ConsultationImage


_TEST_SETTINGS = dict(
    DEBUG=True,
    TEST_MODE=True,
    SECURE_SSL_REDIRECT=False,
)


def _make_professional(**extra):
    defaults = dict(
        username='prof_test',
        email='prof@test.com',
        role='DOCTOR',
        is_email_verified=True,
        profession='Médico',
        professional_specialty='clinico_geral',
    )
    defaults.update(extra)
    u = CustomUser(**defaults)
    u.set_password('Senha@1234')
    u.save()
    return u


def _make_patient(**extra):
    defaults = dict(
        username='paciente_test',
        email='paciente@test.com',
        role='PATIENT',
        is_email_verified=True,
    )
    defaults.update(extra)
    u = CustomUser(**defaults)
    u.set_password('Senha@1234')
    u.save()
    return u


@override_settings(**_TEST_SETTINGS)
class T1_ExternalPatientCreation(TestCase):
    def test_external_patient_created_with_required_fields(self):
        prof = _make_professional()
        ep = ExternalPatient.objects.create(
            name='Maria da Silva',
            phone='(11) 91234-5678',
            created_by=prof,
        )
        self.assertEqual(ep.name, 'Maria da Silva')
        self.assertEqual(ep.created_by, prof)
        self.assertIsNotNone(ep.id)
        self.assertEqual(str(ep), 'Maria da Silva (externo)')

    def test_external_patient_display_name_property(self):
        prof = _make_professional()
        ep = ExternalPatient.objects.create(name='João Costa', created_by=prof)
        self.assertEqual(ep.display_name, 'João Costa')

    def test_external_patient_age_property(self):
        from datetime import date
        prof = _make_professional()
        ep = ExternalPatient.objects.create(
            name='Ana Lima',
            birth_date=date(1990, 1, 1),
            created_by=prof,
        )
        today = date.today()
        expected_age = today.year - 1990 - ((today.month, today.day) < (1, 1))
        self.assertEqual(ep.age, expected_age)


@override_settings(**_TEST_SETTINGS)
class T2_ConsultationWithExternalPatient(TestCase):
    def setUp(self):
        self.prof = _make_professional()
        self.ep = ExternalPatient.objects.create(
            name='Carlos Souza', created_by=self.prof
        )

    def test_consultation_created_without_liddis_patient(self):
        c = Consultation.objects.create(
            external_patient=self.ep,
            date=timezone.now().date(),
            professional_name=self.prof.get_full_name() or self.prof.username,
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.EXTERNAL,
            created_by=self.prof,
            clinic_name='Consultório A',
            clinic_neighborhood='Centro',
            clinic_city='São Paulo',
        )
        self.assertIsNone(c.patient)
        self.assertEqual(c.external_patient, self.ep)
        self.assertEqual(c.record_origin, Consultation.RecordOrigin.EXTERNAL)
        self.assertTrue(c.is_external_patient)

    def test_record_origin_external_choice_exists(self):
        choices = dict(Consultation.RecordOrigin.choices)
        self.assertIn('external', choices)


@override_settings(**_TEST_SETTINGS)
class T3_VitalSignWithExternalPatient(TestCase):
    def test_vitalsign_created_with_external_patient(self):
        prof = _make_professional()
        ep = ExternalPatient.objects.create(name='Pedro Nunes', created_by=prof)
        vs = VitalSign.objects.create(
            external_patient=ep,
            date=timezone.now().date(),
            blood_pressure='120/80',
            recorded_by=prof,
        )
        self.assertIsNone(vs.patient)
        self.assertEqual(vs.external_patient, ep)
        self.assertIn('Pedro Nunes', str(vs))

    def test_vitalsign_patient_nullable(self):
        from django.db import models as dm
        field = VitalSign._meta.get_field('patient')
        self.assertTrue(field.null)
        self.assertTrue(field.blank)


@override_settings(**_TEST_SETTINGS)
class T4_ConsultationImagePath(TestCase):
    def test_image_path_uses_consultation_id_when_no_patient(self):
        from consultations.models import consultation_image_path
        from unittest.mock import MagicMock
        import uuid

        consultation_id = uuid.uuid4()
        ep_id = uuid.uuid4()

        instance = MagicMock()
        instance.consultation.patient_id = None
        instance.consultation.external_patient_id = ep_id
        instance.consultation_id = consultation_id
        instance.tab = 'anamnese'

        path = consultation_image_path(instance, 'photo.jpg')
        self.assertIn(f'ext_{ep_id}', path)
        self.assertIn(str(consultation_id), path)
        self.assertIn('anamnese', path)
        self.assertNotIn('None', path)


@override_settings(**_TEST_SETTINGS)
class T5_PatientDisplayProperties(TestCase):
    def setUp(self):
        self.prof = _make_professional()
        self.ep = ExternalPatient.objects.create(
            name='Fernanda Lima',
            email='fernanda@email.com',
            created_by=self.prof,
        )
        self.c = Consultation.objects.create(
            external_patient=self.ep,
            date=timezone.now().date(),
            professional_name=self.prof.username,
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.EXTERNAL,
            created_by=self.prof,
            clinic_name='Clínica B',
            clinic_neighborhood='Pinheiros',
            clinic_city='São Paulo',
        )

    def test_patient_display_name_returns_external_name(self):
        self.assertEqual(self.c.patient_display_name, 'Fernanda Lima')

    def test_patient_email_display_returns_external_email(self):
        self.assertEqual(self.c.patient_email_display, 'fernanda@email.com')

    def test_patient_display_name_liddis_patient(self):
        patient = _make_patient()
        c = Consultation.objects.create(
            patient=patient,
            date=timezone.now().date(),
            professional_name=self.prof.username,
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.PLATFORM,
            created_by=self.prof,
            clinic_name='Clínica C',
            clinic_neighborhood='Moema',
            clinic_city='São Paulo',
        )
        self.assertEqual(c.patient_display_name, patient.display_name)
        self.assertFalse(c.is_external_patient)


@override_settings(**_TEST_SETTINGS)
class T6_AccessibleConsultations(TestCase):
    def test_professional_sees_external_consultations_they_created(self):
        from consultations.views import _accessible_consultations

        prof = _make_professional()
        other_prof = _make_professional(
            username='other_prof', email='other@test.com'
        )
        ep = ExternalPatient.objects.create(name='Rui Barbosa', created_by=prof)

        c_own = Consultation.objects.create(
            external_patient=ep,
            date=timezone.now().date(),
            professional_name=prof.username,
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.EXTERNAL,
            created_by=prof,
            clinic_name='Clínica D',
            clinic_neighborhood='Liberdade',
            clinic_city='São Paulo',
        )
        c_other = Consultation.objects.create(
            external_patient=ep,
            date=timezone.now().date(),
            professional_name=other_prof.username,
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.EXTERNAL,
            created_by=other_prof,
            clinic_name='Clínica E',
            clinic_neighborhood='Perdizes',
            clinic_city='São Paulo',
        )

        qs = _accessible_consultations(prof)
        pks = list(qs.values_list('pk', flat=True))
        self.assertIn(c_own.pk, pks)
        self.assertNotIn(c_other.pk, pks)


@override_settings(**_TEST_SETTINGS)
class T7_ExternalConsultationCreateView(TestCase):
    def setUp(self):
        self.prof = _make_professional()
        self.client = Client()
        self.client.force_login(self.prof)

    def test_post_valid_data_creates_external_patient_and_consultation(self):
        url = reverse('external_consultation_create')
        data = {
            'name': 'Lucia Pereira',
            'cpf': '123.456.789-09',
            'phone': '(21) 98765-4321',
            'email': 'lucia@email.com',
            'date': timezone.now().date().isoformat(),
            'clinic_name': 'UBS Centro',
            'clinic_neighborhood': 'Centro',
            'clinic_city': 'Rio de Janeiro',
            'diagnosis': 'Hipertensão arterial',
        }
        response = self.client.post(url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ExternalPatient.objects.filter(name='Lucia Pereira').exists())
        ep = ExternalPatient.objects.get(name='Lucia Pereira')
        self.assertEqual(ep.created_by, self.prof)
        c = Consultation.objects.get(external_patient=ep)
        self.assertEqual(c.record_origin, Consultation.RecordOrigin.EXTERNAL)
        self.assertIsNone(c.patient)
        self.assertEqual(c.created_by, self.prof)

    def test_get_returns_200(self):
        url = reverse('external_consultation_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dados do Paciente')

    def test_patient_role_redirected(self):
        patient = _make_patient(username='pat2', email='pat2@test.com')
        c = Client()
        c.force_login(patient)
        url = reverse('external_consultation_create')
        response = c.get(url, follow=True)
        # Patient is redirected away from this view
        self.assertNotContains(response, 'Atendimento Externo', msg_prefix='Patient should not access external consultation view')
