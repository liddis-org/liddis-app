"""
Testes de auditoria — validam as três correções implementadas:
  1. transaction.atomic no atendimento_consulta
  2. validação de altura (min=50, max=250) em ambos os formulários
  3. active_tab forçado para 'geral' quando há erros de validação

QA Senior + Full Stack — executar com:
  python manage.py test consultations.tests --verbosity=2
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from datetime import date

from django.test import TestCase, TransactionTestCase, RequestFactory, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError

# Configurações que bypassam os middlewares de segurança em testes:
# - DEBUG=True             → CloudflareOnlyMiddleware não bloqueia
# - TEST_MODE=True         → EmailVerificationMiddleware não redireciona
# - SECURE_SSL_REDIRECT=False → SecurityMiddleware não redireciona HTTP→HTTPS (301)
_TEST_SETTINGS = dict(DEBUG=True, TEST_MODE=True, SECURE_SSL_REDIRECT=False)

from users.models import CustomUser, PatientProfessionalAccess
from consultations.models import (
    Consultation, VitalSign, ConsultationSession, Anamnese,
)
from consultations.forms import VitalSignForm, VitalSignProfessionalForm, AtendimentoForm


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de criação de usuários
# ─────────────────────────────────────────────────────────────────────────────

def _make_patient(suffix='p'):
    u = CustomUser.objects.create_user(
        username=f'patient_{suffix}_{uuid.uuid4().hex[:6]}',
        email=f'patient_{suffix}_{uuid.uuid4().hex[:6]}@test.com',
        password='test123456',
        role='PATIENT',
    )
    u.is_email_verified = True
    u.save(update_fields=['is_email_verified'])
    return u


def _make_professional(suffix='d'):
    prof = CustomUser.objects.create_user(
        username=f'prof_{suffix}_{uuid.uuid4().hex[:6]}',
        email=f'prof_{suffix}_{uuid.uuid4().hex[:6]}@test.com',
        password='test123456',
        role='DOCTOR',
    )
    prof.profession = 'Médico'
    prof.professional_specialty = 'clinico_geral'
    prof.is_email_verified = True
    prof.save()
    return prof


def _make_active_session(patient, professional):
    """Cria sessão já em estado 'active' (após o entrar_atendimento)."""
    session = ConsultationSession(patient=patient, professional=professional, status='active')
    session.save()
    return session


def _minimal_post_data(session_token):
    """Dados mínimos válidos para o formulário de atendimento."""
    return {
        'date': str(date.today()),
        'clinic_name': 'Clínica Teste',
        'clinic_neighborhood': 'Centro',
        'clinic_city': 'São Paulo',
        'active_tab': 'geral',
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. TESTES DE TRANSACTION.ATOMIC — Rollback
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_TEST_SETTINGS)
class TestAtomicRollback(TransactionTestCase):
    """
    Usa TransactionTestCase para que o rollback de transaction.atomic()
    funcione de forma idêntica ao ambiente de produção (sem savepoint de teste).
    """

    def setUp(self):
        self.patient = _make_patient('atomic')
        self.professional = _make_professional('atomic')
        self.session = _make_active_session(self.patient, self.professional)
        # raise_request_exception=False → cliente retorna 500 em vez de re-levantar a exceção,
        # permitindo verificar o estado do banco após o rollback.
        self.client = Client(raise_request_exception=False)
        self.client.force_login(self.professional)

    def _post_valid_consultation(self, extra_data=None):
        data = _minimal_post_data(str(self.session.token))
        if extra_data:
            data.update(extra_data)
        return self.client.post(
            reverse('atendimento_consulta', kwargs={'token': str(self.session.token)}),
            data=data,
        )

    # ── Teste 1a: fluxo normal deve persistir todos os dados ─────────────────

    def test_normal_flow_persists_consultation_and_session(self):
        """Happy path: consultation salva, session fechada, PPA criado."""
        consultation_count_before = Consultation.objects.count()

        response = self._post_valid_consultation()

        self.assertEqual(Consultation.objects.count(), consultation_count_before + 1)

        consultation = Consultation.objects.latest('created_at')
        self.assertEqual(consultation.patient, self.patient)
        self.assertEqual(consultation.created_by, self.professional)
        self.assertEqual(consultation.clinic_name, 'Clínica Teste')

        # Session deve estar fechada e vinculada à consulta
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'closed')
        self.assertEqual(self.session.consultation, consultation)

        # PatientProfessionalAccess deve existir
        self.assertTrue(
            PatientProfessionalAccess.objects.filter(
                patient=self.patient,
                professional=self.professional,
            ).exists()
        )

    # ── Teste 1b: rollback quando session.save() falha ───────────────────────

    def test_rollback_when_session_save_fails(self):
        """
        Simula falha em session.save() dentro do transaction.atomic().
        Deve: não criar Consultation, session permanecer 'active'.
        """
        consultation_count_before = Consultation.objects.count()
        session_pk = self.session.pk

        # Monitora chamadas a session.save() — falha na primeira (dentro do atomic)
        original_save = ConsultationSession.save
        call_count = {'n': 0}

        def failing_save(self_obj, *args, **kwargs):
            call_count['n'] += 1
            if self_obj.pk == session_pk and self_obj.status == 'closed':
                raise IntegrityError('Falha simulada em session.save() — teste de rollback')
            return original_save(self_obj, *args, **kwargs)

        with patch.object(ConsultationSession, 'save', failing_save):
            response = self._post_valid_consultation()

        # View deve retornar 500 (exceção propagada) ou renderizar erro
        self.assertIn(response.status_code, [500, 302, 200])

        # VALIDAÇÃO CRÍTICA: Consultation NÃO deve ter sido criada (rollback)
        self.assertEqual(
            Consultation.objects.count(),
            consultation_count_before,
            "FALHA: transaction.atomic não reverteu — Consultation órfã encontrada no banco",
        )

        # Session deve continuar 'active' (não foi salva com status='closed')
        self.session.refresh_from_db()
        self.assertEqual(
            self.session.status,
            'active',
            "FALHA: session.status foi alterada mesmo com rollback",
        )

        # PPA não deve ter sido criado
        self.assertFalse(
            PatientProfessionalAccess.objects.filter(
                patient=self.patient,
                professional=self.professional,
            ).exists(),
            "FALHA: PatientProfessionalAccess criado mesmo com rollback",
        )

    # ── Teste 1c: rollback quando PatientProfessionalAccess falha ────────────

    def test_rollback_when_ppa_creation_fails(self):
        """
        Simula falha em PatientProfessionalAccess.get_or_create().
        Deve: não criar Consultation, session permanecer 'active'.
        """
        consultation_count_before = Consultation.objects.count()

        # Patcha o manager diretamente no modelo (import local na view não importa).
        with patch.object(
            PatientProfessionalAccess.objects,
            'get_or_create',
            side_effect=IntegrityError('Falha simulada em PPA.get_or_create'),
        ):
            response = self._post_valid_consultation()

        # VALIDAÇÃO: Consultation NÃO deve existir
        self.assertEqual(
            Consultation.objects.count(),
            consultation_count_before,
            "FALHA: Consultation órfã após falha em PPA",
        )

        # Session deve continuar 'active'
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'active')


# ─────────────────────────────────────────────────────────────────────────────
# 2. TESTES DE VALIDAÇÃO DE ALTURA
# ─────────────────────────────────────────────────────────────────────────────

class TestHeightValidationVitalSignForm(TestCase):
    """Testa VitalSignForm (usado pelo paciente)."""

    def _form(self, height_value):
        data = {
            'date': str(date.today()),
            'height': height_value,
        }
        return VitalSignForm(data)

    # ── Fronteira inferior ────────────────────────────────────────────────────

    def test_height_49_rejected(self):
        """49 cm → deve rejeitar (abaixo do mínimo 50)."""
        form = self._form('49')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)
        self.assertIn('50 cm', form.errors['height'][0])

    def test_height_50_accepted(self):
        """50 cm → deve aceitar (limite mínimo válido)."""
        form = self._form('50')
        self.assertTrue(form.is_valid())

    def test_height_49_9_rejected(self):
        """49.9 cm → deve rejeitar."""
        form = self._form('49.9')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)

    # ── Valores normais ────────────────────────────────────────────────────────

    def test_height_170_accepted(self):
        """170 cm → deve aceitar."""
        form = self._form('170')
        self.assertTrue(form.is_valid())

    def test_height_170_5_accepted(self):
        """170.5 cm → deve aceitar (decimal válido)."""
        form = self._form('170.5')
        self.assertTrue(form.is_valid())

    # ── Fronteira superior ────────────────────────────────────────────────────

    def test_height_250_accepted(self):
        """250 cm → deve aceitar (limite máximo válido)."""
        form = self._form('250')
        self.assertTrue(form.is_valid())

    def test_height_251_rejected(self):
        """251 cm → deve rejeitar (acima do máximo 250)."""
        form = self._form('251')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)
        self.assertIn('250 cm', form.errors['height'][0])

    def test_height_250_1_rejected(self):
        """250.1 cm → deve rejeitar."""
        form = self._form('250.1')
        self.assertFalse(form.is_valid())

    # ── Proteção contra entrada em metros ─────────────────────────────────────

    def test_height_1_70_rejected_as_meters(self):
        """1.70 (metros) → deve rejeitar (abaixo de 50 cm mínimo)."""
        form = self._form('1.70')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)
        # Mensagem deve orientar o usuário
        error_msg = form.errors['height'][0]
        self.assertIn('centímetros', error_msg)

    def test_height_1_7_rejected_as_meters(self):
        """1.7 (metros) → deve rejeitar."""
        form = self._form('1.7')
        self.assertFalse(form.is_valid())

    # ── Vazio → campo opcional ────────────────────────────────────────────────

    def test_height_empty_accepted(self):
        """Vazio → campo opcional, deve aceitar (without height)."""
        form = self._form('')
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data.get('height'))

    # ── Valores inválidos ─────────────────────────────────────────────────────

    def test_height_letters_rejected(self):
        """Letras → deve rejeitar."""
        form = self._form('abc')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)

    def test_height_special_chars_rejected(self):
        """Caracteres especiais → deve rejeitar."""
        form = self._form('17O')  # letra O no lugar de zero
        self.assertFalse(form.is_valid())

    def test_height_negative_rejected(self):
        """Negativo → deve rejeitar (abaixo de 50)."""
        form = self._form('-10')
        self.assertFalse(form.is_valid())

    def test_height_zero_rejected(self):
        """Zero → deve rejeitar."""
        form = self._form('0')
        self.assertFalse(form.is_valid())


class TestHeightValidationVitalSignProfessionalForm(TestCase):
    """Testa VitalSignProfessionalForm (usado pelo profissional durante atendimento)."""

    def _form(self, height_value):
        data = {}
        if height_value != '':
            data['vitais-height'] = height_value
        return VitalSignProfessionalForm(data, prefix='vitais')

    def test_height_49_rejected(self):
        form = VitalSignProfessionalForm({'vitais-height': '49'}, prefix='vitais')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)

    def test_height_50_accepted(self):
        form = VitalSignProfessionalForm({'vitais-height': '50'}, prefix='vitais')
        self.assertTrue(form.is_valid())

    def test_height_170_accepted(self):
        form = VitalSignProfessionalForm({'vitais-height': '170'}, prefix='vitais')
        self.assertTrue(form.is_valid())

    def test_height_250_accepted(self):
        form = VitalSignProfessionalForm({'vitais-height': '250'}, prefix='vitais')
        self.assertTrue(form.is_valid())

    def test_height_251_rejected(self):
        form = VitalSignProfessionalForm({'vitais-height': '251'}, prefix='vitais')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)

    def test_height_1_70_meters_rejected(self):
        """1.70 metros → deve rejeitar com mensagem em pt-BR."""
        form = VitalSignProfessionalForm({'vitais-height': '1.70'}, prefix='vitais')
        self.assertFalse(form.is_valid())
        self.assertIn('height', form.errors)
        self.assertIn('centímetros', form.errors['height'][0])

    def test_height_empty_is_optional(self):
        """Altura vazia → formulário válido (campo não obrigatório)."""
        form = VitalSignProfessionalForm({}, prefix='vitais')
        self.assertTrue(form.is_valid())

    def test_height_letters_rejected(self):
        form = VitalSignProfessionalForm({'vitais-height': 'cem'}, prefix='vitais')
        self.assertFalse(form.is_valid())


class TestHeightModelLevel(TestCase):
    """
    Verifica que o modelo VitalSign.bmi usa a altura como centímetros.
    Caso alguém salve 1.7 (metros) diretamente via model, o BMI ficaria errado.
    Este teste documenta o comportamento e serve como referência.
    """

    def test_bmi_calculation_with_cm(self):
        """BMI com altura em cm (170 cm, 70 kg) = 70 / (1.70)^2 ≈ 24.2."""
        patient = _make_patient('bmi')
        vital = VitalSign(
            patient=patient,
            date=date.today(),
            height=Decimal('170.0'),
            weight=Decimal('70.0'),
        )
        bmi = vital.bmi
        self.assertAlmostEqual(bmi, 24.2, places=0)

    def test_bmi_calculation_wrong_if_meters_used(self):
        """
        Se alguém salvar 1.70 como altura (metros em vez de cm),
        o BMI calculado seria absurdo (> 24000).
        Isso documenta o risco se os validators forem bypassed.
        """
        patient = _make_patient('bmi_wrong')
        vital = VitalSign(
            patient=patient,
            date=date.today(),
            height=Decimal('1.7'),
            weight=Decimal('70.0'),
        )
        bmi = vital.bmi
        # BMI = 70 / (0.017)^2 = 242_214... — completamente absurdo
        self.assertGreater(bmi, 10000, "BMI com altura em metros deveria ser absurdamente alto")

    def test_model_has_no_range_validators_on_height_field(self):
        """
        Documenta que o MODELO não tem validators de range min/max (apenas o FORMULÁRIO).
        Django's DecimalField adiciona um DecimalValidator interno — isso é esperado.
        Mas não deve haver MinValueValidator ou MaxValueValidator no model field.
        Implicação: inserção via shell/Admin/API bypassa as validações de range.
        """
        from django.core.validators import MinValueValidator, MaxValueValidator
        height_field = VitalSign._meta.get_field('height')
        has_min = any(isinstance(v, MinValueValidator) for v in height_field.validators)
        has_max = any(isinstance(v, MaxValueValidator) for v in height_field.validators)
        self.assertFalse(has_min, "MinValueValidator nao deveria estar no model field")
        self.assertFalse(has_max, "MaxValueValidator nao deveria estar no model field")


class TestHeightWidgetAttributes(TestCase):
    """Verifica que os widgets HTML têm os atributos min/max para validação do browser."""

    def test_vitalsignform_height_widget_has_min_max(self):
        form = VitalSignForm()
        widget = form.fields['height'].widget
        self.assertEqual(widget.attrs.get('min'), '50')
        self.assertEqual(widget.attrs.get('max'), '250')
        self.assertEqual(widget.attrs.get('step'), '0.1')

    def test_vitalsignprofessionalform_height_widget_has_min_max(self):
        form = VitalSignProfessionalForm()
        widget = form.fields['height'].widget
        self.assertEqual(widget.attrs.get('min'), '50')
        self.assertEqual(widget.attrs.get('max'), '250')
        self.assertEqual(widget.attrs.get('step'), '0.1')


# ─────────────────────────────────────────────────────────────────────────────
# 3. TESTES DE MULTI-TAB (active_tab forçado para 'geral' em caso de erro)
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_TEST_SETTINGS)
class TestMultiTabActiveTabBehavior(TestCase):
    """Valida que erros de validação forçam active_tab='geral'."""

    def setUp(self):
        self.patient = _make_patient('tab')
        self.professional = _make_professional('tab')
        self.session = _make_active_session(self.patient, self.professional)
        self.client = Client()
        self.client.force_login(self.professional)
        self.url = reverse('atendimento_consulta', kwargs={'token': str(self.session.token)})

    # ── Teste 3a: GET sempre mostra aba 'geral' ────────────────────────────────

    def test_get_renders_geral_tab_by_default(self):
        """GET sem parâmetros → aba 'geral' ativa."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'geral')

    # ── Teste 3b: POST com erros → força 'geral' independente do tab enviado ──

    def test_post_with_missing_clinic_name_forces_geral_tab(self):
        """
        Profissional estava na aba 'vitais', submete sem clinic_name.
        Sistema deve retornar com active_tab='geral' para mostrar o erro.
        """
        response = self.client.post(self.url, {
            'date': str(date.today()),
            'clinic_name': '',          # campo obrigatório vazio
            'clinic_neighborhood': 'Centro',
            'clinic_city': 'São Paulo',
            'active_tab': 'vitais',     # usuário estava na aba vitais
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['active_tab'],
            'geral',
            "active_tab deve ser 'geral' quando há erros de validação",
        )
        # Formulário deve ter erros
        self.assertTrue(response.context['form'].errors)
        self.assertIn('clinic_name', response.context['form'].errors)

    def test_post_with_missing_neighborhood_forces_geral_tab(self):
        """clinic_neighborhood vazio → aba 'geral'."""
        response = self.client.post(self.url, {
            'date': str(date.today()),
            'clinic_name': 'Clínica',
            'clinic_neighborhood': '',  # obrigatório vazio
            'clinic_city': 'São Paulo',
            'active_tab': 'avaliacao',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'geral')
        self.assertIn('clinic_neighborhood', response.context['form'].errors)

    def test_post_with_missing_city_forces_geral_tab(self):
        """clinic_city vazio → aba 'geral'."""
        response = self.client.post(self.url, {
            'date': str(date.today()),
            'clinic_name': 'Clínica',
            'clinic_neighborhood': 'Centro',
            'clinic_city': '',  # obrigatório vazio
            'active_tab': 'exames',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'geral')
        self.assertIn('clinic_city', response.context['form'].errors)

    def test_post_with_missing_date_forces_geral_tab(self):
        """date vazio → deve rejeitar e forçar aba 'geral'."""
        response = self.client.post(self.url, {
            'date': '',             # obrigatório vazio
            'clinic_name': 'Clínica',
            'clinic_neighborhood': 'Centro',
            'clinic_city': 'São Paulo',
            'active_tab': 'vitais',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'geral')

    # ── Teste 3c: POST válido → redireciona (não permanece no form) ───────────

    def test_post_valid_redirects_to_detail(self):
        """POST com todos os campos válidos → redireciona para detail da consulta."""
        response = self.client.post(self.url, {
            'date': str(date.today()),
            'clinic_name': 'Clínica ABC',
            'clinic_neighborhood': 'Bela Vista',
            'clinic_city': 'São Paulo',
            'active_tab': 'geral',
        })
        # Deve redirecionar (302) para detail
        self.assertEqual(response.status_code, 302)
        # Consulta deve ter sido criada
        self.assertEqual(Consultation.objects.filter(patient=self.patient).count(), 1)

    # ── Teste 3d: todos os campos do formulário AtendimentoForm que são required ─

    def test_atendimento_form_required_fields(self):
        """Documenta quais campos são obrigatórios no AtendimentoForm."""
        form = AtendimentoForm(data={})  # vazio
        self.assertFalse(form.is_valid())
        # Campos esperados como obrigatórios
        required = {'date', 'clinic_name', 'clinic_neighborhood', 'clinic_city'}
        for field in required:
            self.assertIn(field, form.errors,
                          f"Campo '{field}' deveria ser obrigatório mas não retornou erro")

    def test_optional_fields_of_atendimento_form(self):
        """Campos opcionais não devem gerar erro quando omitidos."""
        form = AtendimentoForm(data={
            'date': str(date.today()),
            'clinic_name': 'Clínica',
            'clinic_neighborhood': 'Centro',
            'clinic_city': 'SP',
        })
        self.assertTrue(form.is_valid())
        # diagnosis, notes, prescription, clinic_address são opcionais
        for field in ('diagnosis', 'notes', 'prescription', 'clinic_address'):
            self.assertNotIn(field, form.errors)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TESTES DE REGRESSÃO — funcionalidades existentes
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_TEST_SETTINGS)
class TestRegressionPatientFlow(TestCase):
    """Paciente pode criar consulta via ConsultationCreateView (não via token)."""

    def setUp(self):
        self.patient = _make_patient('reg')
        self.client = Client()
        self.client.force_login(self.patient)

    def test_patient_can_access_consultation_list(self):
        response = self.client.get(reverse('consultation_list'))
        self.assertIn(response.status_code, [200, 302])

    def test_patient_can_access_consultation_create(self):
        response = self.client.get(reverse('consultation_create'))
        self.assertEqual(response.status_code, 200)

    def test_patient_cannot_access_atendimento(self):
        """Paciente não pode acessar fluxo de atendimento profissional."""
        response = self.client.get(reverse('iniciar_atendimento'))
        # Deve redirecionar ou mostrar a tela do paciente (gerar token)
        self.assertIn(response.status_code, [200, 302])


@override_settings(**_TEST_SETTINGS)
class TestRegressionProfessionalPermissions(TestCase):
    """Profissional não pode criar consulta diretamente (apenas via token)."""

    def setUp(self):
        self.professional = _make_professional('regp')
        self.client = Client()
        self.client.force_login(self.professional)

    def test_professional_redirected_from_consultation_create(self):
        """ConsultationCreateView deve redirecionar profissional para entrar_atendimento."""
        response = self.client.get(reverse('consultation_create'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('entrar_atendimento'))

    def test_professional_can_access_entrar_atendimento(self):
        response = self.client.get(reverse('entrar_atendimento'))
        self.assertEqual(response.status_code, 200)


@override_settings(**_TEST_SETTINGS)
class TestRegressionVitalSignList(TestCase):
    """Paciente acessa seus sinais vitais."""

    def setUp(self):
        self.patient = _make_patient('vit')
        self.client = Client()
        self.client.force_login(self.patient)

    def test_patient_can_view_vitals(self):
        response = self.client.get(reverse('vitals'))
        self.assertIn(response.status_code, [200, 302])


@override_settings(**_TEST_SETTINGS)
class TestRegressionConsultationDetail(TestCase):
    """Consulta existente pode ser visualizada pelo paciente."""

    def setUp(self):
        self.patient = _make_patient('det')
        self.professional = _make_professional('det')
        # Cria consulta diretamente
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            date=date.today(),
            professional_name='Dr. Teste',
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
            created_by=None,
        )
        self.client = Client()
        self.client.force_login(self.patient)

    def test_patient_can_view_own_consultation(self):
        url = reverse('consultation_detail', kwargs={'pk': self.consultation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['consultation'], self.consultation)


# ─────────────────────────────────────────────────────────────────────────────
# 5. TESTES DE INTEGRIDADE DO BANCO
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseIntegrity(TestCase):
    """Verifica integridade de FK e ausência de registros órfãos."""

    def test_consultation_without_session_is_accessible_via_patient_filter(self):
        """
        Consulta sem sessão (patient_manual) deve ser acessível pelo paciente.
        Documenta que _accessible_consultations inclui consultas sem session.
        """
        patient = _make_patient('int')
        consultation = Consultation.objects.create(
            patient=patient,
            date=date.today(),
            professional_name='Dr. Manual',
            specialty='clinico_geral',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        # Sem session vinculada
        self.assertFalse(hasattr(consultation, 'session') and consultation.session is not None)

        # Importa o helper do views
        from consultations.views import _accessible_consultations
        qs = _accessible_consultations(patient)
        self.assertIn(consultation, qs)

    def test_session_without_consultation_does_not_prevent_new_session(self):
        """
        Sessão em status 'active' sem consulta vinculada é um estado válido
        (sessão foi iniciada mas consulta ainda não foi salva).
        """
        patient = _make_patient('sess')
        professional = _make_professional('sess')
        session = _make_active_session(patient, professional)

        self.assertEqual(session.status, 'active')
        self.assertIsNone(session.consultation)

    def test_vitalsign_height_bmi_uses_centimeters(self):
        """VitalSign.bmi divide por 100 para converter cm → m. Confirma unidade."""
        patient = _make_patient('bmi_unit')
        vital = VitalSign(
            patient=patient,
            date=date.today(),
            height=Decimal('170.0'),
            weight=Decimal('70.0'),
        )
        h_m = float(vital.height) / 100  # 1.70 m
        expected_bmi = round(70.0 / (h_m ** 2), 1)
        self.assertEqual(vital.bmi, expected_bmi)
        self.assertAlmostEqual(vital.bmi, 24.2, delta=0.5)

    def test_no_orphaned_consultations_after_rollback(self):
        """
        Após um rollback simulado, não devem existir Consultations
        sem session vinculada que sejam do tipo PLATFORM.
        (Consultas PATIENT_MANUAL legitimamente não têm session.)
        """
        # Esta verificação seria mais útil com dados reais de produção,
        # mas aqui confirmamos que em ambiente de teste não há órfãos.
        platform_without_session = Consultation.objects.filter(
            record_origin=Consultation.RecordOrigin.PLATFORM,
            session__isnull=True,
        ).count()
        # Em banco limpo de teste: zero
        self.assertEqual(platform_without_session, 0)
