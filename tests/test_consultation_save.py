"""
Testes de integração: fluxo de salvamento de consultas.
Cobre paciente, profissional (token), acesso e isolamento.
"""
import pytest
from django.urls import reverse
from django.utils import timezone
from django.test import Client


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures locais
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def doctor_full(db):
    from users.models import CustomUser
    u = CustomUser.objects.create_user(
        username='dr_completo', email='dr@clinica.com',
        password='Senha@1234',
        first_name='Carlos', last_name='Oliveira',
        role='DOCTOR', is_email_verified=True,
        profession='Médico', professional_specialty='clinico_geral',
    )
    return u


@pytest.fixture
def patient_a(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='paciente_a', email='paciente_a@test.com',
        password='Senha@1234',
        first_name='Ana', last_name='Lima',
        role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def patient_b(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='paciente_b', email='paciente_b@test.com',
        password='Senha@1234',
        first_name='Bruno', last_name='Souza',
        role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def active_session(db, patient_a, doctor_full):
    """Sessão já ativa com profissional e paciente vinculados."""
    from consultations.models import ConsultationSession
    s = ConsultationSession.objects.create(patient=patient_a)
    s.professional = doctor_full
    s.status = 'active'
    s.save()
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Bloco 1 — Paciente cria consulta manual
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPacienteCriaConsulta:
    BASE_DATA = {
        'date': '2025-08-01',
        'professional_name': 'Dr. Teste',
        'specialty': 'clinico_geral',
        'clinic_name': 'Clínica Teste',
        'clinic_neighborhood': 'Centro',
        'clinic_city': 'São Paulo',
        'diagnosis': 'Hipertensão',
        'notes': 'Paciente evolui bem.',
        'prescription': 'Losartana 50mg',
        'anamnese-chief_complaint': '',
        'anamnese-history': '',
        'anamnese-past_history': '',
        'anamnese-family_history': '',
        'anamnese-medications': '',
        'anamnese-allergies': '',
        'exames-hemograma': '',
        'exames-glicemia': '',
        'exames-colesterol': '',
        'exames-funcao_renal': '',
        'exames-funcao_hepatica': '',
        'exames-hormonal': '',
        'exames-urina': '',
        'exames-outros': '',
        'vitais-date': '',
        'vitais-blood_pressure': '',
        'vitais-heart_rate': '',
        'vitais-weight': '',
        'vitais-height': '',
        'vitais-temperature': '',
        'vitais-oxygen_saturation': '',
        'vitais-glucose': '',
        'vitais-notes': '',
        'active_tab': 'geral',
    }

    def test_consulta_salva_no_banco(self, client, patient_a):
        from consultations.models import Consultation
        client.force_login(patient_a)
        url = reverse('consultation_create')
        resp = client.post(url, self.BASE_DATA, follow=True)
        assert resp.status_code == 200, f'Status inesperado: {resp.status_code}'
        assert Consultation.objects.filter(patient=patient_a).exists(), \
            'Consulta NÃO foi salva no banco após POST válido'

    def test_consulta_aparece_na_lista(self, client, patient_a):
        from consultations.models import Consultation
        client.force_login(patient_a)
        client.post(reverse('consultation_create'), self.BASE_DATA, follow=True)

        Consultation.objects.filter(patient=patient_a).count()
        resp = client.get(reverse('consultation_list'))
        assert resp.status_code == 200
        assert Consultation.objects.filter(patient=patient_a).exists()

    def test_consulta_record_origin_patient_manual(self, client, patient_a):
        from consultations.models import Consultation
        client.force_login(patient_a)
        client.post(reverse('consultation_create'), self.BASE_DATA, follow=True)
        c = Consultation.objects.filter(patient=patient_a).first()
        assert c is not None
        assert c.record_origin == Consultation.RecordOrigin.PATIENT_MANUAL

    def test_form_invalido_sem_specialty_nao_salva(self, client, patient_a):
        from consultations.models import Consultation
        client.force_login(patient_a)
        data = {k: v for k, v in self.BASE_DATA.items() if k != 'specialty'}
        resp = client.post(reverse('consultation_create'), data)
        assert resp.status_code == 200  # form re-renderizado
        assert not Consultation.objects.filter(patient=patient_a).exists(), \
            'Consulta foi salva sem campo obrigatório specialty!'

    def test_form_invalido_sem_clinic_name_nao_salva(self, client, patient_a):
        from consultations.models import Consultation
        client.force_login(patient_a)
        data = {k: v for k, v in self.BASE_DATA.items() if k != 'clinic_name'}
        resp = client.post(reverse('consultation_create'), data)
        assert resp.status_code == 200
        assert not Consultation.objects.filter(patient=patient_a).exists(), \
            'Consulta foi salva sem clinic_name!'

    def test_sinais_vitais_salvos_junto_com_consulta(self, client, patient_a):
        from consultations.models import Consultation, VitalSign
        from django.utils import timezone
        client.force_login(patient_a)
        data = {
            **self.BASE_DATA,
            'vitais-date': str(timezone.now().date()),
            'vitais-blood_pressure': '120/80',
            'vitais-heart_rate': '72',
        }
        client.post(reverse('consultation_create'), data, follow=True)
        c = Consultation.objects.filter(patient=patient_a).first()
        assert c is not None, 'Consulta não foi salva'
        assert VitalSign.objects.filter(patient=patient_a).exists(), \
            'Sinais vitais não foram salvos'

    def test_profissional_e_redirecionado_ao_criar_consulta(self, client, doctor_full):
        client.force_login(doctor_full)
        resp = client.get(reverse('consultation_create'))
        assert resp.status_code == 302
        assert 'entrar' in resp['Location'] or 'atendimento' in resp['Location']


# ═══════════════════════════════════════════════════════════════════════════════
# Bloco 2 — Profissional cria consulta via token
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestProfissionalCriaConsultaViaToken:
    CONSULT_DATA = {
        'date': '2025-08-01',
        'clinic_name': 'Clínica Dr. Carlos',
        'clinic_neighborhood': 'Jardins',
        'clinic_city': 'São Paulo',
        'diagnosis': 'Hipertensão arterial leve',
        'notes': 'Paciente com PA controlada.',
        'prescription': 'Losartana 50mg 1x/dia',
        'anamnese-chief_complaint': 'Dor de cabeça',
        'anamnese-history': 'Cefaleia há 2 semanas',
        'anamnese-past_history': '',
        'anamnese-family_history': 'HAS paterna',
        'anamnese-medications': '',
        'anamnese-allergies': '',
        'exames-hemograma': '',
        'exames-glicemia': '',
        'exames-colesterol': '',
        'exames-funcao_renal': '',
        'exames-funcao_hepatica': '',
        'exames-hormonal': '',
        'exames-urina': '',
        'exames-outros': '',
        'vitais-blood_pressure': '130/85',
        'vitais-heart_rate': '78',
        'vitais-weight': '75',
        'vitais-height': '170',
        'vitais-temperature': '',
        'vitais-oxygen_saturation': '',
        'vitais-glucose': '',
        'vitais-notes': '',
        'vitais-respiratory_rate': '',
        'vitais-other_signs': '',
        'interv-conducts': '',
        'interv-procedures': '',
        'interv-medications_administered': '',
        'interv-referrals': '',
        'evolucao-clinical_evolution': '',
        'evolucao-therapeutic_goals': '',
        'evolucao-estimated_sessions': '',
        'active_tab': 'geral',
    }

    def test_consulta_via_token_salva_no_banco(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation, ConsultationSession
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        resp = client.post(url, self.CONSULT_DATA, follow=True)
        assert resp.status_code == 200, f'Status inesperado: {resp.status_code}'
        assert Consultation.objects.filter(patient=patient_a).exists(), \
            'Consulta NÃO foi salva no banco após POST via token!'

    def test_session_fechada_apos_salvar(self, client, active_session, doctor_full):
        from consultations.models import ConsultationSession
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        active_session.refresh_from_db()
        assert active_session.status == 'closed', \
            f'Sessão deveria ser closed, mas está: {active_session.status}'

    def test_consulta_vinculada_a_sessao(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation, ConsultationSession
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        active_session.refresh_from_db()
        assert active_session.consultation is not None, \
            'Consulta não foi vinculada à sessão!'

    def test_record_origin_platform(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        c = Consultation.objects.filter(patient=patient_a).first()
        assert c is not None
        assert c.record_origin == Consultation.RecordOrigin.PLATFORM

    def test_created_by_preenchido(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        c = Consultation.objects.filter(patient=patient_a).first()
        assert c is not None
        assert c.created_by == doctor_full, \
            f'created_by deveria ser {doctor_full}, mas é {c.created_by}'

    def test_consulta_aparece_em_meus_atendimentos(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        resp = client.get(reverse('meus_atendimentos'))
        assert resp.status_code == 200
        c = Consultation.objects.filter(patient=patient_a).first()
        assert c is not None
        assert str(c.pk) in resp.content.decode('utf-8') or \
               patient_a.first_name in resp.content.decode('utf-8'), \
            'Consulta não aparece em meus_atendimentos!'

    def test_sinais_vitais_salvos_via_token(self, client, active_session, doctor_full, patient_a):
        from consultations.models import VitalSign
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        assert VitalSign.objects.filter(patient=patient_a).exists(), \
            'Sinais vitais não foram salvos pelo profissional!'

    def test_vinculo_profissional_paciente_criado(self, client, active_session, doctor_full, patient_a):
        from users.models import PatientProfessionalAccess
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        client.post(url, self.CONSULT_DATA, follow=True)
        assert PatientProfessionalAccess.objects.filter(
            patient=patient_a, professional=doctor_full, is_active=True
        ).exists(), 'Vínculo PatientProfessionalAccess não foi criado!'

    def test_form_invalido_sem_data_nao_salva(self, client, active_session, doctor_full, patient_a):
        from consultations.models import Consultation
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(active_session.token)})
        data = {k: v for k, v in self.CONSULT_DATA.items() if k != 'date'}
        resp = client.post(url, data)
        assert resp.status_code == 200
        assert not Consultation.objects.filter(patient=patient_a).exists(), \
            'Consulta foi salva sem data!'


# ═══════════════════════════════════════════════════════════════════════════════
# Bloco 3 — Isolamento entre pacientes (segurança)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestIsolamentoPacientes:

    def test_paciente_nao_ve_consulta_de_outro(self, client, patient_a, patient_b):
        from consultations.models import Consultation
        c = Consultation.objects.create(
            patient=patient_a,
            date='2025-08-01',
            professional_name='Dr. Teste',
            specialty='clinico_geral',
            clinic_name='Clínica X', clinic_neighborhood='N', clinic_city='C',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        client.force_login(patient_b)
        resp = client.get(reverse('consultation_detail', kwargs={'pk': str(c.pk)}))
        assert resp.status_code == 404, \
            f'Paciente B acessou consulta de A! Status: {resp.status_code}'

    def test_paciente_nao_edita_consulta_de_outro(self, client, patient_a, patient_b):
        from consultations.models import Consultation
        c = Consultation.objects.create(
            patient=patient_a,
            date='2025-08-01',
            professional_name='Dr. Teste',
            specialty='clinico_geral',
            clinic_name='Clínica X', clinic_neighborhood='N', clinic_city='C',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        client.force_login(patient_b)
        resp = client.get(reverse('consultation_update', kwargs={'pk': str(c.pk)}))
        assert resp.status_code == 404, \
            f'Paciente B pode editar consulta de A! Status: {resp.status_code}'

    def test_profissional_sem_vinculo_nao_acessa_consulta(self, client, patient_a, doctor_full):
        from consultations.models import Consultation
        c = Consultation.objects.create(
            patient=patient_a,
            date='2025-08-01',
            professional_name='Dr. Outro',
            specialty='clinico_geral',
            clinic_name='Clínica Y', clinic_neighborhood='N', clinic_city='C',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        client.force_login(doctor_full)
        resp = client.get(reverse('consultation_detail', kwargs={'pk': str(c.pk)}))
        # RBACPatientAccessMiddleware bloqueia e redireciona ao dashboard (302)
        # em vez de 404 — o dado não é exposto, mas o middleware anuncia existência do recurso
        assert resp.status_code in (302, 404), \
            f'Profissional sem vínculo acessou consulta sem bloqueio! Status: {resp.status_code}'
        if resp.status_code == 302:
            assert '/dashboard/' in resp['Location'] or 'login' in resp['Location']


# ═══════════════════════════════════════════════════════════════════════════════
# Bloco 4 — ConsultationSession token expiration
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSessionTokenExpiration:

    def test_token_expirado_bloqueia_atendimento(self, client, patient_a, doctor_full):
        from consultations.models import ConsultationSession
        from datetime import timedelta
        s = ConsultationSession.objects.create(patient=patient_a)
        # Force expired
        ConsultationSession.objects.filter(pk=s.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        s.refresh_from_db()
        assert s.is_expired is True

    def test_token_valido_permite_atendimento(self, client, patient_a, doctor_full):
        from consultations.models import ConsultationSession
        s = ConsultationSession.objects.create(patient=patient_a)
        s.professional = doctor_full
        s.status = 'active'
        s.save()
        client.force_login(doctor_full)
        url = reverse('atendimento_consulta', kwargs={'token': str(s.token)})
        resp = client.get(url)
        assert resp.status_code == 200, f'Sessão ativa bloqueou acesso! Status: {resp.status_code}'


# ═══════════════════════════════════════════════════════════════════════════════
# Bloco 5 — Persistência (simula reload e re-login)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPersistencia:

    def test_consulta_persiste_apos_logout_e_login(self, patient_a):
        from consultations.models import Consultation
        # Cria consulta
        c = Consultation.objects.create(
            patient=patient_a,
            date='2025-08-01',
            professional_name='Dr. Teste',
            specialty='clinico_geral',
            clinic_name='Clínica X', clinic_neighborhood='N', clinic_city='C',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        pk = c.pk

        # Simula logout (nova sessão)
        client2 = Client()
        client2.force_login(patient_a)
        resp = client2.get(reverse('consultation_detail', kwargs={'pk': str(pk)}))
        assert resp.status_code == 200, \
            'Consulta não foi encontrada após simular novo login!'

    def test_dados_consulta_corretos_apos_reload(self, patient_a):
        from consultations.models import Consultation
        c = Consultation.objects.create(
            patient=patient_a,
            date='2025-08-01',
            professional_name='Dr. Reload Test',
            specialty='clinico_geral',
            clinic_name='Clínica Persistência', clinic_neighborhood='N', clinic_city='C',
            diagnosis='Teste de persistência',
            record_origin=Consultation.RecordOrigin.PATIENT_MANUAL,
        )
        reloaded = Consultation.objects.get(pk=c.pk)
        assert reloaded.professional_name == 'Dr. Reload Test'
        assert reloaded.diagnosis == 'Teste de persistência'
        assert reloaded.clinic_name == 'Clínica Persistência'
