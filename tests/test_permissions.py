"""
Testes do sistema RBAC (Role-Based Access Control).
Cobre: has_permission, get_allowed_actions, can_access_patient,
       filter_evolutions_for_user, get_prescription_allowed_types.
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# has_permission
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestHasPermission:

    def test_medico_pode_criar_consulta(self, doctor_user):
        from users.permissions import has_permission
        assert has_permission(doctor_user, 'consultation', 'create') is True

    def test_paciente_nao_pode_criar_consulta_via_rbac(self, patient_user):
        from users.permissions import has_permission
        # Paciente só pode VIEW de consultation (conforme matrix)
        assert has_permission(patient_user, 'consultation', 'create') is False

    def test_admin_tem_todas_permissoes(self, admin_user):
        from users.permissions import has_permission
        recursos = ['consultation', 'anamnese', 'diagnosis', 'prescription', 'vitals']
        acoes = ['view', 'create', 'edit', 'delete']
        for recurso in recursos:
            for acao in acoes:
                assert has_permission(admin_user, recurso, acao) is True, \
                    f'Admin deveria ter {acao} em {recurso}'

    def test_enfermeira_nao_pode_deletar_consulta(self, nurse_user):
        from users.permissions import has_permission
        assert has_permission(nurse_user, 'consultation', 'delete') is False

    def test_enfermeira_pode_ver_consulta(self, nurse_user):
        from users.permissions import has_permission
        assert has_permission(nurse_user, 'consultation', 'view') is True

    def test_permissao_recurso_invalido(self, doctor_user):
        from users.permissions import has_permission
        # Recurso que não existe retorna False sem exceção
        assert has_permission(doctor_user, 'recurso_inexistente', 'view') is False

    def test_acao_invalida(self, doctor_user):
        from users.permissions import has_permission
        assert has_permission(doctor_user, 'consultation', 'voar') is False


# ═══════════════════════════════════════════════════════════════════════════════
# get_allowed_actions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGetAllowedActions:

    def test_medico_acoes_em_consulta(self, doctor_user):
        from users.permissions import get_allowed_actions
        acoes = get_allowed_actions(doctor_user, 'consultation')
        assert 'view' in acoes
        assert 'create' in acoes
        assert 'edit' in acoes
        assert 'delete' in acoes

    def test_paciente_acoes_em_vitals(self, patient_user):
        from users.permissions import get_allowed_actions
        acoes = get_allowed_actions(patient_user, 'vitals')
        # Paciente tem ALL em vitals (ver matrix em permissions.py)
        assert 'view' in acoes
        assert 'create' in acoes


# ═══════════════════════════════════════════════════════════════════════════════
# can_access_patient
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCanAccessPatient:

    def test_medico_com_vinculo_ativo(self, patient_access, doctor_user, patient_user):
        from users.permissions import can_access_patient
        assert can_access_patient(doctor_user, patient_user) is True

    def test_medico_sem_vinculo(self, doctor_user, patient_user):
        from users.permissions import can_access_patient
        assert can_access_patient(doctor_user, patient_user) is False

    def test_medico_vinculo_revogado(self, patient_access, doctor_user, patient_user):
        from users.permissions import can_access_patient
        patient_access.revoke()
        assert can_access_patient(doctor_user, patient_user) is False

    def test_admin_acessa_qualquer_paciente(self, admin_user, patient_user):
        from users.permissions import can_access_patient
        # Admin não precisa de vínculo
        assert can_access_patient(admin_user, patient_user) is True


# ═══════════════════════════════════════════════════════════════════════════════
# get_prescription_allowed_types
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPrescriptionTypes:

    def test_medico_pode_prescricao_medica(self, doctor_user):
        from users.permissions import get_prescription_allowed_types
        tipos = get_prescription_allowed_types(doctor_user)
        assert 'medical' in tipos

    def test_nutricionista_prescricao_dietetica(self, db):
        from users.models import CustomUser
        from users.permissions import get_prescription_allowed_types
        nutri = CustomUser.objects.create_user(
            username='nutri', email='nutri@teste.com',
            password='Senha@123', role='NUTRITIONIST',
        )
        tipos = get_prescription_allowed_types(nutri)
        assert 'dietary' in tipos
        assert 'medical' not in tipos

    def test_paciente_nao_tem_tipos(self, patient_user):
        from users.permissions import get_prescription_allowed_types
        tipos = get_prescription_allowed_types(patient_user)
        assert tipos == []


# ═══════════════════════════════════════════════════════════════════════════════
# filter_evolutions_for_user
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFilterEvolutions:

    def test_medico_ve_todas_evolucoes(self, consultation, doctor_user, nurse_user):
        from consultations.models import Evolution
        from users.permissions import filter_evolutions_for_user

        Evolution.objects.create(consultation=consultation, professional=doctor_user,
                                  category='medical', content='Nota médica')
        Evolution.objects.create(consultation=consultation, professional=nurse_user,
                                  category='nursing', content='Nota de enfermagem', is_visible_to_patient=False)

        qs = Evolution.objects.filter(consultation=consultation)
        filtrado = filter_evolutions_for_user(qs, doctor_user)
        assert filtrado.count() == 2

    def test_paciente_ve_apenas_visiveis(self, consultation, doctor_user, patient_user):
        from consultations.models import Evolution
        from users.permissions import filter_evolutions_for_user

        Evolution.objects.create(consultation=consultation, professional=doctor_user,
                                  category='medical', content='Visível', is_visible_to_patient=True)
        Evolution.objects.create(consultation=consultation, professional=doctor_user,
                                  category='medical', content='Oculta', is_visible_to_patient=False)

        qs = Evolution.objects.filter(consultation=consultation)
        filtrado = filter_evolutions_for_user(qs, patient_user)
        assert filtrado.count() == 1
        assert filtrado.first().content == 'Visível'
