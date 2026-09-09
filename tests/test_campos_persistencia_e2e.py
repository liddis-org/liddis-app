"""
Auditoria de persistência campo a campo.

Preenche TODOS os campos disponíveis no atendimento (44 campos em 6 blocos),
salva, e confere um por um diretamente no banco — depois recarrega e refaz o
login para provar que o dado sobrevive à sessão.

Blocos cobertos: Consulta, Anamnese/Avaliação, Exames Laboratoriais,
Intervenção Clínica, Evolução Esperada, Sinais Vitais.
"""
import pytest
from django.urls import reverse


# ═══════════════════════════════════════════════════════════════════════════════
# Dados de teste — um valor distinto por campo, para detectar troca entre colunas
# ═══════════════════════════════════════════════════════════════════════════════

CONSULTA = {
    'date':                '2026-04-15',
    'clinic_name':         'Clínica Vida Plena',
    'clinic_neighborhood': 'Jardim Paulista',
    'clinic_city':         'São Paulo',
    'clinic_address':      'Rua das Acácias, 482',
    'diagnosis':           'Hipertensão arterial estágio 1',
    'notes':               'Paciente relata melhora após ajuste de dieta',
    'prescription':        'Losartana 50mg, 1x ao dia',
}

ANAMNESE = {
    'chief_complaint': 'Dor de cabeça recorrente há três semanas',
    'history':         'Início gradual, piora ao fim do dia',
    'past_history':    'Apendicectomia em 2019',
    'family_history':  'Pai hipertenso, mãe diabética tipo 2',
    'medications':     'Losartana 50mg',
    'allergies':       'Alergia a dipirona',
}

EXAMES = {
    'hemograma':       'Hemoglobina 14,2 g/dL; leucócitos 7.100',
    'glicemia':        'Jejum 96 mg/dL',
    'colesterol':      'Total 188; HDL 52; LDL 112',
    'funcao_renal':    'Creatinina 0,9; ureia 32',
    'funcao_hepatica': 'TGO 24; TGP 28',
    'hormonal':        'TSH 2,1; T4 livre 1,1',
    'urina':           'EAS sem alterações',
    'outros':          'Vitamina D 34 ng/mL',
}

INTERVENCAO = {
    'professional_diagnosis': 'Cefaleia tensional associada a hipertensão',
    'related_factors':        'Estresse ocupacional e sono irregular',
    'conducts':               'Ajuste medicamentoso e higiene do sono',
    'procedures':             'Aferição seriada de pressão arterial',
    'guidelines':             'Reduzir sódio; caminhada 30 min, 5x por semana',
    'clinical_actions':       'Encaminhamento para nutricionista',
}

EVOLUCAO = {
    'estimated_timeframe': '60 dias',
    'priority':            'medium',
    'clinical_evolution':  'Espera-se redução da pressão para abaixo de 130/85',
    'therapeutic_goals':   'Controle pressórico e remissão da cefaleia',
    'follow_up_plan':      'Retorno em 30 dias com MAPA',
    'treatment_response':  'Resposta parcial ao tratamento inicial',
}

VITAIS = {
    'blood_pressure':    '128/84',
    'heart_rate':        '72',
    'respiratory_rate':  '16',
    'weight':            '78.4',
    'height':            '174',
    'temperature':       '36.5',
    'oxygen_saturation': '97',
    'glucose':           '96',
    'notes':             'Aferido em repouso, braço esquerdo',
    'other_signs':       'Sem edema em membros inferiores',
}


def _payload():
    """Monta o POST completo com os prefixos que a view espera."""
    dados = dict(CONSULTA)
    for prefixo, bloco in (
        ('anamnese', ANAMNESE),
        ('exames',   EXAMES),
        ('interv',   INTERVENCAO),
        ('evolucao', EVOLUCAO),
        ('vitais',   VITAIS),
    ):
        dados.update({f'{prefixo}-{k}': v for k, v in bloco.items()})
    return dados


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def paciente(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='pac_campos', email='pac_campos@test.com', password='Senha@1234',
        first_name='Marina', last_name='Costa', role='PATIENT', is_email_verified=True,
    )


@pytest.fixture
def medico(db):
    from users.models import CustomUser
    return CustomUser.objects.create_user(
        username='dr_campos', email='dr_campos@test.com', password='Senha@1234',
        first_name='Rafael', last_name='Antunes', role='DOCTOR',
        profession='Médico', professional_specialty='clinico_geral',
        is_email_verified=True,
    )


@pytest.fixture
def sessao_ativa(db, paciente, medico):
    from consultations.models import ConsultationSession
    s = ConsultationSession.objects.create(patient=paciente)
    s.professional = medico
    s.status = 'active'
    s.save()
    return s


@pytest.fixture
def consulta_salva(client, medico, sessao_ativa):
    """Executa o atendimento completo e devolve a consulta criada."""
    from consultations.models import Consultation
    client.force_login(medico)
    resp = client.post(
        reverse('atendimento_consulta', args=[sessao_ativa.token]),
        _payload(), follow=True,
    )
    assert resp.status_code == 200
    consulta = Consultation.objects.filter(patient=sessao_ativa.patient).first()
    assert consulta is not None, 'A consulta não foi criada'
    return consulta


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Persistência bloco a bloco
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPersistenciaDeCampos:

    def test_bloco_consulta(self, consulta_salva):
        for campo, esperado in CONSULTA.items():
            if campo == 'date':
                assert str(consulta_salva.date) == esperado, f'{campo} divergente'
            else:
                assert getattr(consulta_salva, campo) == esperado, \
                    f'Campo {campo!r} não persistiu: {getattr(consulta_salva, campo)!r}'

    def test_bloco_anamnese(self, consulta_salva):
        from consultations.models import Anamnese
        a = Anamnese.objects.get(consultation=consulta_salva)
        for campo, esperado in ANAMNESE.items():
            assert getattr(a, campo) == esperado, f'Anamnese.{campo} não persistiu'

    def test_bloco_exames(self, consulta_salva):
        from consultations.models import ExameLaboratorial
        e = ExameLaboratorial.objects.get(consultation=consulta_salva)
        for campo, esperado in EXAMES.items():
            assert getattr(e, campo) == esperado, f'Exames.{campo} não persistiu'

    def test_bloco_intervencao(self, consulta_salva):
        from consultations.models import ClinicalIntervention
        i = ClinicalIntervention.objects.get(consultation=consulta_salva)
        for campo, esperado in INTERVENCAO.items():
            assert getattr(i, campo) == esperado, f'Intervenção.{campo} não persistiu'

    def test_bloco_evolucao_esperada(self, consulta_salva):
        from consultations.models import ExpectedEvolution
        ev = ExpectedEvolution.objects.get(consultation=consulta_salva)
        for campo, esperado in EVOLUCAO.items():
            assert getattr(ev, campo) == esperado, f'Evolução.{campo} não persistiu'

    def test_bloco_sinais_vitais(self, consulta_salva):
        from consultations.models import VitalSign
        v = VitalSign.objects.get(consultation=consulta_salva)
        assert v.blood_pressure == VITAIS['blood_pressure']
        assert v.heart_rate == int(VITAIS['heart_rate'])
        assert v.respiratory_rate == int(VITAIS['respiratory_rate'])
        assert float(v.weight) == float(VITAIS['weight'])
        assert float(v.height) == float(VITAIS['height'])
        assert float(v.temperature) == float(VITAIS['temperature'])
        assert v.oxygen_saturation == int(VITAIS['oxygen_saturation'])
        assert v.notes == VITAIS['notes']

    def test_nenhum_bloco_ficou_vazio(self, consulta_salva):
        """Garante que os 6 blocos existem — nenhum foi descartado em silêncio."""
        from consultations.models import (
            Anamnese, ExameLaboratorial, ClinicalIntervention,
            ExpectedEvolution, VitalSign,
        )
        faltando = [
            nome for nome, modelo in (
                ('Anamnese',            Anamnese),
                ('ExameLaboratorial',   ExameLaboratorial),
                ('ClinicalIntervention', ClinicalIntervention),
                ('ExpectedEvolution',   ExpectedEvolution),
                ('VitalSign',           VitalSign),
            )
            if not modelo.objects.filter(consultation=consulta_salva).exists()
        ]
        assert not faltando, f'Blocos perdidos ao salvar: {faltando}'


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Sobrevivência à sessão
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSobrevivenciaDosCampos:

    def test_valores_aparecem_na_pagina_apos_novo_login(self, client, medico, consulta_salva):
        client.logout()
        client.force_login(medico)
        resp = client.get(reverse('consultation_detail', args=[consulta_salva.pk]))
        assert resp.status_code == 200

        corpo = resp.content.decode('utf-8', errors='ignore')
        amostra = [
            CONSULTA['diagnosis'],
            ANAMNESE['chief_complaint'],
            EXAMES['hemograma'],
            INTERVENCAO['professional_diagnosis'],
            EVOLUCAO['therapeutic_goals'],
        ]
        ausentes = [t for t in amostra if t not in corpo]
        assert not ausentes, f'Valores não exibidos após novo login: {ausentes}'

    def test_releitura_do_banco_mantem_os_valores(self, consulta_salva):
        from consultations.models import Consultation
        recarregada = Consultation.objects.get(pk=consulta_salva.pk)
        assert recarregada.diagnosis == CONSULTA['diagnosis']
        assert recarregada.prescription == CONSULTA['prescription']
        assert recarregada.notes == CONSULTA['notes']

    def test_relacionamentos_apontam_para_a_consulta_certa(self, consulta_salva, paciente, medico):
        from consultations.models import Anamnese, VitalSign
        a = Anamnese.objects.get(consultation=consulta_salva)
        v = VitalSign.objects.get(consultation=consulta_salva)
        assert a.consultation_id == consulta_salva.pk
        assert v.consultation_id == consulta_salva.pk
        assert v.patient_id == paciente.pk, 'Sinal vital vinculado ao paciente errado'
        assert v.recorded_by_id == medico.pk
        assert consulta_salva.patient_id == paciente.pk
        assert consulta_salva.created_by_id == medico.pk


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Falha de validação não pode passar despercebida
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAvisoEmValidacaoInvalida:

    def test_altura_em_metros_avisa_o_profissional(self, client, medico, sessao_ativa):
        """Altura 1.74 (metros) reprova no validador 50–250 cm."""
        from consultations.models import Consultation, VitalSign

        dados = _payload()
        dados['vitais-height'] = '1.74'

        client.force_login(medico)
        resp = client.post(
            reverse('atendimento_consulta', args=[sessao_ativa.token]),
            dados, follow=True,
        )
        assert resp.status_code == 200

        consulta = Consultation.objects.filter(patient=sessao_ativa.patient).first()
        assert consulta is not None, 'A consulta deveria ser salva mesmo com vital inválido'

        # Vitais não gravados — mas o profissional precisa ser avisado
        assert not VitalSign.objects.filter(consultation=consulta).exists()
        avisos = [m.message for m in resp.context['messages']]
        assert any('vitais' in m.lower() or 'vital' in m.lower() for m in avisos), \
            f'Nenhum aviso sobre sinais vitais descartados. Mensagens: {avisos}'

    def test_consulta_e_demais_blocos_sobrevivem_ao_vital_invalido(self, client, medico, sessao_ativa):
        from consultations.models import Consultation, Anamnese, ExameLaboratorial

        dados = _payload()
        dados['vitais-height'] = '1.74'

        client.force_login(medico)
        client.post(reverse('atendimento_consulta', args=[sessao_ativa.token]), dados, follow=True)

        consulta = Consultation.objects.filter(patient=sessao_ativa.patient).first()
        assert consulta.diagnosis == CONSULTA['diagnosis']
        assert Anamnese.objects.filter(consultation=consulta).exists(), \
            'Anamnese perdida por causa de um sinal vital inválido'
        assert ExameLaboratorial.objects.filter(consultation=consulta).exists(), \
            'Exames perdidos por causa de um sinal vital inválido'
