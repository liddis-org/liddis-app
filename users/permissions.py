"""
Sistema de controle de acesso baseado em papéis (RBAC).

Recursos:
  consultation     — consulta principal
  anamnese         — anamnese / histórico clínico
  physical_exam    — exame físico
  diagnosis        — diagnósticos CID-10
  evolution        — evoluções multiprofissionais
  prescription     — prescrições (médica, nutricional, enfermagem, odonto, farmácia)
  exams            — exames laboratoriais (resultados existentes)
  lab_requests     — solicitações de exame + entrada de resultados
  vitals           — sinais vitais
  images           — imagens e laudos
  patient_data     — dados cadastrais do paciente

Ações:
  view   — visualizar
  create — criar / registrar
  edit   — editar
  delete — excluir

Regras especiais de evolução (qual categoria cada role pode visualizar / criar):
  Definidas em EVOLUTION_VIEW_CATEGORIES e EVOLUTION_CREATE_CATEGORY.

Tipos de prescrição que cada role pode criar:
  Definidos em PRESCRIPTION_ALLOWED_TYPES.
"""

from __future__ import annotations

_ALL  = frozenset({'view', 'create', 'edit', 'delete'})
_VCE  = frozenset({'view', 'create', 'edit'})
_VC   = frozenset({'view', 'create'})
_V    = frozenset({'view'})
_NONE = frozenset()

# ── Matriz principal ───────────────────────────────────────────────────────────
# Estrutura: { role: { resource: frozenset(actions) } }

PERMISSIONS: dict[str, dict[str, frozenset[str]]] = {

    # ── Administrador ──────────────────────────────────────────────────────────
    'ADMIN': {
        'consultation': _ALL,
        'anamnese':     _ALL,
        'physical_exam':_ALL,
        'diagnosis':    _ALL,
        'evolution':    _ALL,
        'prescription': _ALL,
        'exams':        _ALL,
        'lab_requests': _ALL,
        'vitals':       _ALL,
        'images':       _ALL,
        'patient_data': _ALL,
    },

    # ── Médico(a) ──────────────────────────────────────────────────────────────
    # Acesso completo ao prontuário; prescreve; solicita exames; CID; alta.
    'DOCTOR': {
        'consultation': _ALL,
        'anamnese':     _ALL,
        'physical_exam':_ALL,
        'diagnosis':    _ALL,
        'evolution':    _ALL,
        'prescription': _ALL,
        'exams':        _VCE,           # visualiza resultados, pode editar notas
        'lab_requests': _ALL,           # solicita e pode ver resultados
        'vitals':       _VCE,
        'images':       _ALL,
        'patient_data': _VCE,
    },

    # ── Enfermeiro(a) ──────────────────────────────────────────────────────────
    # Diagnósticos de enfermagem (NANDA); prescrição de enfermagem; sinais vitais.
    'NURSE': {
        'consultation': _VC,
        'anamnese':     _VCE,           # histórico de enfermagem
        'physical_exam':_V,
        'diagnosis':    _V,             # visualiza diagnósticos médicos
        'evolution':    _VCE,
        'prescription': _VCE,           # prescrição de enfermagem
        'exams':        _V,
        'lab_requests': _V,
        'vitals':       _ALL,
        'images':       _VC,
        'patient_data': frozenset({'view', 'edit'}),
    },

    # ── Fisioterapeuta ─────────────────────────────────────────────────────────
    # Avaliação cinético-funcional; evolução fisioterapêutica; imagens.
    'PHYSIO': {
        'consultation': _VCE,
        'anamnese':     _VCE,           # avaliação fisioterapêutica
        'physical_exam':_VCE,           # avaliação funcional
        'diagnosis':    _V,
        'evolution':    _VCE,
        'prescription': _V,
        'exams':        _V,             # especialmente imagens de imagem
        'lab_requests': _V,
        'vitals':       _VCE,
        'images':       _ALL,           # fisio usa muito imagens (RX, RM)
        'patient_data': _V,
    },

    # ── Nutricionista ──────────────────────────────────────────────────────────
    # Avaliação nutricional; plano alimentar; dados antropométricos.
    'NUTRITIONIST': {
        'consultation': _VCE,
        'anamnese':     _VCE,           # avaliação nutricional
        'physical_exam':_V,
        'diagnosis':    _V,
        'evolution':    _VCE,
        'prescription': _VCE,           # prescrição dietética
        'exams':        _V,             # exames metabólicos e hormonais
        'lab_requests': _V,
        'vitals':       _ALL,           # peso, altura, IMC
        'images':       _VC,
        'patient_data': _V,
    },

    # ── Biomédico(a) ───────────────────────────────────────────────────────────
    # Recebe solicitações de exame; registra resultados; laudos técnicos.
    'BIOMEDICO': {
        'consultation': _V,
        'anamnese':     _NONE,          # não acessa histórico clínico
        'physical_exam':_NONE,
        'diagnosis':    _V,             # visualiza para contexto
        'evolution':    _NONE,          # não escreve evoluções clínicas
        'prescription': _V,             # apenas vê solicitações/prescrições
        'exams':        _VCE,           # resultado de exames = domínio do biomédico
        'lab_requests': _VCE,           # preenche resultado e laudo
        'vitals':       _V,
        'images':       _VC,            # imagens laboratoriais
        'patient_data': _V,             # apenas identificação
    },

    # ── Fonoaudiólogo(a) ───────────────────────────────────────────────────────
    # Avaliação fonoaudiológica; deglutição; linguagem; voz.
    'SPEECH_THERAPIST': {
        'consultation': _VCE,
        'anamnese':     _VCE,
        'physical_exam':_V,
        'diagnosis':    _V,
        'evolution':    _VCE,
        'prescription': _V,
        'exams':        _V,             # imagens (RX de deglutição, nasofibroscopia)
        'lab_requests': _V,
        'vitals':       _VC,
        'images':       _VC,
        'patient_data': _V,
    },

    # ── Educador(a) Físico(a) ──────────────────────────────────────────────────
    # Condicionamento físico; avaliação ergométrica; sinais vitais.
    'PHYSICAL_EDUCATOR': {
        'consultation': _V,
        'anamnese':     _V,             # somente leitura
        'physical_exam':_NONE,
        'diagnosis':    _NONE,
        'evolution':    _VCE,           # escreve evolução de educação física
        'prescription': _NONE,
        'exams':        _V,
        'lab_requests': _NONE,
        'vitals':       _ALL,           # domínio: aptidão física, FC, peso
        'images':       _V,
        'patient_data': _V,
    },

    # ── Psicólogo(a) ──────────────────────────────────────────────────────────
    # Avaliação psicológica; evolução; sem prescrição farmacológica.
    'PSYCHOLOGIST': {
        'consultation': _VCE,
        'anamnese':     _VCE,
        'physical_exam':_V,
        'diagnosis':    _V,             # visualiza — não registra CID farmacológico
        'evolution':    _VCE,
        'prescription': _NONE,          # psicólogo não prescreve medicamentos
        'exams':        _V,
        'lab_requests': _V,
        'vitals':       _V,
        'images':       _V,
        'patient_data': _V,
    },

    # ── Dentista ──────────────────────────────────────────────────────────────
    # Odontologia: diagnóstico odonto, prescrição odonto, imagens odonto.
    'DENTIST': {
        'consultation': _VCE,
        'anamnese':     _VCE,
        'physical_exam':_V,
        'diagnosis':    _VCE,           # diagnóstico odontológico
        'evolution':    _VCE,
        'prescription': _VCE,           # prescrição odontológica
        'exams':        _VCE,
        'lab_requests': _VC,
        'vitals':       _VC,
        'images':       _ALL,           # RX panorâmica, periapical, CBCT
        'patient_data': _V,
    },

    # ── Terapeuta Ocupacional ──────────────────────────────────────────────────
    'OCC_THERAPIST': {
        'consultation': _VCE,
        'anamnese':     _VCE,
        'physical_exam':_V,
        'diagnosis':    _V,
        'evolution':    _VCE,
        'prescription': _NONE,
        'exams':        _V,
        'lab_requests': _V,
        'vitals':       _VC,
        'images':       _VC,
        'patient_data': _V,
    },

    # ── Farmacêutico(a) ───────────────────────────────────────────────────────
    # Gestão de prescrições; conciliação medicamentosa; farmacovigilância.
    'PHARMACIST': {
        'consultation': _V,
        'anamnese':     _NONE,
        'physical_exam':_NONE,
        'diagnosis':    _V,
        'evolution':    _V,             # somente leitura (evol. médica e enfermagem)
        'prescription': _VCE,           # prescrição farmacêutica
        'exams':        _V,             # exames relevantes p/ farmacoterapia
        'lab_requests': _V,
        'vitals':       _V,
        'images':       _NONE,
        'patient_data': _V,             # identificação + alergias + medicamentos
    },

    # ── Paciente ──────────────────────────────────────────────────────────────
    'PATIENT': {
        'consultation': _V,
        'anamnese':     _V,
        'physical_exam':_V,
        'diagnosis':    _V,
        'evolution':    _V,             # somente evoluções is_visible_to_patient=True
        'prescription': _V,
        'exams':        _V,
        'lab_requests': _V,
        'vitals':       _ALL,           # controla seus próprios sinais vitais
        'images':       _V,
        'patient_data': frozenset({'view', 'edit'}),
    },
}


# ── Controle de categorias de evolução ────────────────────────────────────────
# Quais categorias de evolução cada role pode VISUALIZAR (além da própria).
# None = visualiza TODAS as categorias.

EVOLUTION_VIEW_CATEGORIES: dict[str, list[str] | None] = {
    'ADMIN':            None,
    'DOCTOR':           None,     # médico vê tudo
    'NURSE':            ['medical', 'nursing', 'physio', 'nutrition', 'speech',
                         'occupational', 'dental', 'pharmacy', 'physical_ed', 'other'],
    'PHYSIO':           ['medical', 'nursing', 'physio', 'nutrition', 'speech',
                         'occupational', 'other'],
    'NUTRITIONIST':     ['medical', 'nursing', 'nutrition', 'physio', 'other'],
    'BIOMEDICO':        [],       # biomédico não lê evoluções clínicas
    'SPEECH_THERAPIST': ['medical', 'nursing', 'speech', 'physio', 'occupational', 'other'],
    'PHYSICAL_EDUCATOR':['medical', 'nursing', 'physical_ed'],
    'PSYCHOLOGIST':     ['medical', 'nursing', 'psychology', 'occupational', 'other'],
    'DENTIST':          ['medical', 'nursing', 'dental', 'other'],
    'OCC_THERAPIST':    ['medical', 'nursing', 'occupational', 'physio', 'speech', 'other'],
    'PHARMACIST':       ['medical', 'nursing', 'pharmacy'],
    'PATIENT':          [],       # paciente vê apenas is_visible_to_patient=True (filtro separado)
}

# Qual categoria de evolução cada role CRIA (apenas uma por role)
EVOLUTION_CREATE_CATEGORY: dict[str, str | None] = {
    'ADMIN':            'other',
    'DOCTOR':           'medical',
    'NURSE':            'nursing',
    'PHYSIO':           'physio',
    'NUTRITIONIST':     'nutrition',
    'BIOMEDICO':        None,         # biomédico não escreve evolução
    'SPEECH_THERAPIST': 'speech',
    'PHYSICAL_EDUCATOR':'physical_ed',
    'PSYCHOLOGIST':     'psychology',
    'DENTIST':          'dental',
    'OCC_THERAPIST':    'occupational',
    'PHARMACIST':       'pharmacy',
    'PATIENT':          None,
}

# Tipos de prescrição que cada role pode CRIAR
PRESCRIPTION_ALLOWED_TYPES: dict[str, list[str]] = {
    'ADMIN':            ['medical', 'nursing', 'dental', 'dietary', 'pharmacy'],
    'DOCTOR':           ['medical'],
    'NURSE':            ['nursing'],
    'PHYSIO':           [],
    'NUTRITIONIST':     ['dietary'],
    'BIOMEDICO':        [],
    'SPEECH_THERAPIST': [],
    'PHYSICAL_EDUCATOR':[],
    'PSYCHOLOGIST':     [],
    'DENTIST':          ['dental'],
    'OCC_THERAPIST':    [],
    'PHARMACIST':       ['pharmacy'],
    'PATIENT':          [],
}


# ── Funções de consulta ────────────────────────────────────────────────────────

def has_permission(user, resource: str, action: str) -> bool:
    """Retorna True se o usuário tem permissão para a ação no recurso."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return action in PERMISSIONS.get(user.role, {}).get(resource, _NONE)


def get_allowed_actions(user, resource: str) -> frozenset[str]:
    """Retorna o conjunto de ações permitidas para o usuário no recurso."""
    if not user or not user.is_authenticated:
        return _NONE
    if user.is_superuser:
        return _ALL
    return PERMISSIONS.get(user.role, {}).get(resource, _NONE)


def get_evolution_view_categories(user) -> list[str] | None:
    """
    Retorna lista de categorias de evolução que o usuário pode visualizar.
    None significa "todas as categorias".
    """
    if user.is_superuser:
        return None
    return EVOLUTION_VIEW_CATEGORIES.get(user.role, [])


def get_evolution_create_category(user) -> str | None:
    """Retorna a categoria de evolução que o role do usuário pode criar, ou None."""
    if user.is_superuser:
        return 'other'
    return EVOLUTION_CREATE_CATEGORY.get(user.role)


def get_prescription_allowed_types(user) -> list[str]:
    """Retorna os tipos de prescrição que o usuário pode criar."""
    if user.is_superuser:
        return ['medical', 'nursing', 'dental', 'dietary', 'pharmacy']
    return PRESCRIPTION_ALLOWED_TYPES.get(user.role, [])


def can_access_patient(professional, patient) -> bool:
    """
    Verifica se o profissional tem vínculo ativo com o paciente
    ou se é ADMIN/superuser. Importação local evita importação circular.
    """
    if professional.role == 'ADMIN' or professional.is_superuser:
        return True
    from users.models import PatientProfessionalAccess
    return PatientProfessionalAccess.objects.filter(
        professional=professional,
        patient=patient,
        is_active=True,
    ).exists()


def filter_evolutions_for_user(queryset, user):
    """
    Aplica filtro de categorias de evolução ao queryset de Evolution.
    Para pacientes, filtra adicionalmente por is_visible_to_patient.
    """
    if user.is_superuser or user.role == 'ADMIN':
        return queryset

    if user.role == 'PATIENT':
        return queryset.filter(is_visible_to_patient=True)

    cats = get_evolution_view_categories(user)
    if cats is None:
        return queryset
    if len(cats) == 0:
        return queryset.none()
    return queryset.filter(category__in=cats)
