"""
LUMI — IA de apoio clínico e preventivo do HDI.

Responsabilidades:
  - ClinicalContextBuilder: coleta e estrutura dados do paciente
  - LumiService: orquestra a chamada à OpenAI e retorna o relatório
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é a LUMI, uma assistente de inteligência artificial de apoio clínico e preventivo "
    "do sistema HDI (HealthData Hub). "
    "Seu papel é resumir informações clínicas, destacar riscos preventivos e sugerir "
    "acompanhamento profissional. "
    "NUNCA forneça diagnóstico médico, prescrição ou tratamento. "
    "SEMPRE deixe claro que suas análises são de caráter informativo e preventivo, "
    "e que o paciente deve sempre consultar um profissional de saúde habilitado. "
    "Seja precisa, empática e responsável."
)

_PATIENT_INSTRUCTION = (
    "Você está gerando um relatório para o próprio paciente. "
    "Use linguagem simples, acolhedora e motivadora. "
    "Evite jargões técnicos excessivos. "
    "Foque em prevenção, hábitos saudáveis e a importância do acompanhamento médico. "
    "Estruture a resposta em seções curtas com títulos claros. "
    "Termine sempre incentivando o paciente a consultar um profissional."
)

_PROFESSIONAL_INSTRUCTION = (
    "Você está gerando um resumo clínico para um profissional de saúde. "
    "Use linguagem técnica objetiva. "
    "Estruture em: 1) Resumo geral, 2) Alertas clínicos e riscos, "
    "3) Padrões relevantes identificados, 4) Sugestões de acompanhamento. "
    "Seja direto e conciso — o profissional precisa de uma leitura rápida durante o atendimento."
)


# ──────────────────────────────────────────────────────────────────────────────
# Context Builder
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ClinicalContext:
    patient_name: str
    patient_age: Optional[int]
    patient_gender: str

    # Perfil clínico permanente
    comorbidities: str
    allergies: str
    continuous_medications: str
    smokes: str
    drinks: str

    # Sinais vitais (últimos 5 registros)
    vitals: list = field(default_factory=list)

    # Anamneses (últimas 3 consultas)
    anamneses: list = field(default_factory=list)

    # Intervenções e evoluções (últimas 3 consultas)
    interventions: list = field(default_factory=list)

    # Exames laboratoriais (últimos 3)
    lab_exams: list = field(default_factory=list)


class ClinicalContextBuilder:
    """Coleta dados clínicos do paciente de forma segura e estruturada."""

    def build(self, patient) -> ClinicalContext:
        from consultations.models import (
            VitalSign, Anamnese, ClinicalIntervention,
            ExpectedEvolution, ExameLaboratorial,
        )

        # Perfil clínico permanente
        try:
            summary = patient.clinical_summary
            comorbidities          = summary.comorbidities or ''
            allergies              = summary.allergies or ''
            continuous_medications = summary.continuous_medications or ''
            smokes                 = summary.get_smokes_display() if summary.smokes else ''
            drinks                 = summary.get_drinks_display() if summary.drinks else ''
        except Exception:
            comorbidities = allergies = continuous_medications = smokes = drinks = ''

        # Sinais vitais recentes
        raw_vitals = VitalSign.objects.filter(patient=patient).order_by('-date', '-created_at')[:5]
        vitals = [self._format_vital(v) for v in raw_vitals]

        # Anamneses recentes
        raw_anamneses = (
            Anamnese.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:3]
        )
        anamneses = [self._format_anamnese(a) for a in raw_anamneses]

        # Intervenções clínicas recentes
        raw_interventions = (
            ClinicalIntervention.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:3]
        )
        interventions = [self._format_intervention(i) for i in raw_interventions]

        # Exames laboratoriais recentes
        raw_exams = (
            ExameLaboratorial.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:3]
        )
        lab_exams = [self._format_exam(e) for e in raw_exams]

        return ClinicalContext(
            patient_name=patient.display_name,
            patient_age=getattr(patient, 'age', None),
            patient_gender=getattr(patient, 'gender_display', ''),
            comorbidities=comorbidities,
            allergies=allergies,
            continuous_medications=continuous_medications,
            smokes=smokes,
            drinks=drinks,
            vitals=vitals,
            anamneses=anamneses,
            interventions=interventions,
            lab_exams=lab_exams,
        )

    # ── formatters ────────────────────────────────────────────────────────────

    def _format_vital(self, v) -> str:
        parts = [f"Data: {v.date}"]
        if v.blood_pressure:      parts.append(f"PA: {v.blood_pressure}")
        if v.heart_rate:          parts.append(f"FC: {v.heart_rate} bpm")
        if v.temperature:         parts.append(f"T°: {v.temperature}°C")
        if v.oxygen_saturation:   parts.append(f"SpO₂: {v.oxygen_saturation}%")
        if v.weight:              parts.append(f"Peso: {v.weight} kg")
        if v.height:              parts.append(f"Altura: {v.height} cm")
        if v.glucose:             parts.append(f"Glicemia: {v.glucose} mg/dL")
        if v.respiratory_rate:    parts.append(f"FR: {v.respiratory_rate} irpm")
        if v.notes:               parts.append(f"Obs: {v.notes}")
        if v.other_signs:         parts.append(f"Outros sinais: {v.other_signs}")
        return " | ".join(parts)

    def _format_anamnese(self, a) -> str:
        parts = [f"Consulta {a.consultation.date}"]
        if a.chief_complaint: parts.append(f"Queixa: {a.chief_complaint}")
        if a.history:         parts.append(f"HDA: {a.history}")
        if a.past_history:    parts.append(f"Antecedentes: {a.past_history}")
        if a.family_history:  parts.append(f"Hist. familiar: {a.family_history}")
        if a.medications:     parts.append(f"Medicamentos: {a.medications}")
        if a.allergies:       parts.append(f"Alergias: {a.allergies}")
        return "\n".join(parts)

    def _format_intervention(self, i) -> str:
        parts = [f"Consulta {i.consultation.date}"]
        if i.professional_diagnosis: parts.append(f"Diagnóstico: {i.professional_diagnosis}")
        if i.classification_code:    parts.append(f"Classificação: {i.classification_code}")
        if i.conducts:               parts.append(f"Condutas: {i.conducts}")
        if i.clinical_actions:       parts.append(f"Ações: {i.clinical_actions}")
        return "\n".join(parts)

    def _format_exam(self, e) -> str:
        parts = [f"Exame consulta {e.consultation.date}"]
        fields_map = [
            ('hemograma', 'Hemograma'),
            ('glicemia', 'Glicemia'),
            ('colesterol', 'Colesterol'),
            ('funcao_renal', 'Função renal'),
            ('funcao_hepatica', 'Função hepática'),
            ('tireoide', 'Tireoide'),
            ('infeccao', 'Infecção'),
            ('outros', 'Outros'),
        ]
        for attr, label in fields_map:
            val = getattr(e, attr, '')
            if val:
                parts.append(f"{label}: {val}")
        return "\n".join(parts)

    def to_prompt_text(self, ctx: ClinicalContext) -> str:
        """Serializa o contexto em texto estruturado para o prompt."""
        lines = [
            "=== DADOS DO PACIENTE ===",
            f"Nome: {ctx.patient_name}",
        ]
        if ctx.patient_age:
            lines.append(f"Idade: {ctx.patient_age} anos")
        if ctx.patient_gender:
            lines.append(f"Sexo: {ctx.patient_gender}")

        lines.append("\n=== PERFIL CLÍNICO PERMANENTE ===")
        if ctx.comorbidities:
            lines.append(f"Comorbidades: {ctx.comorbidities}")
        if ctx.allergies:
            lines.append(f"Alergias: {ctx.allergies}")
        if ctx.continuous_medications:
            lines.append(f"Medicamentos contínuos: {ctx.continuous_medications}")
        if ctx.smokes:
            lines.append(f"Tabagismo: {ctx.smokes}")
        if ctx.drinks:
            lines.append(f"Etilismo: {ctx.drinks}")

        if ctx.vitals:
            lines.append("\n=== SINAIS VITAIS RECENTES ===")
            for v in ctx.vitals:
                lines.append(f"• {v}")

        if ctx.anamneses:
            lines.append("\n=== HISTÓRICO CLÍNICO ===")
            for a in ctx.anamneses:
                lines.append(a)
                lines.append("")

        if ctx.interventions:
            lines.append("\n=== INTERVENÇÕES E DIAGNÓSTICOS ===")
            for i in ctx.interventions:
                lines.append(i)
                lines.append("")

        if ctx.lab_exams:
            lines.append("\n=== EXAMES LABORATORIAIS ===")
            for e in ctx.lab_exams:
                lines.append(e)
                lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# LUMI Service
# ──────────────────────────────────────────────────────────────────────────────

class LumiService:
    """Orquestra geração de relatório clínico pela LUMI usando OpenAI."""

    MODEL = "gpt-4o-mini"
    MAX_TOKENS = 1200
    TEMPERATURE = 0.4

    def __init__(self):
        self._context_builder = ClinicalContextBuilder()

    def generate_report(self, patient, is_professional: bool) -> str:
        """
        Gera o relatório LUMI para o paciente dado.
        Lança LumiServiceError em caso de falha controlada.
        """
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            raise LumiServiceError("Chave de API não configurada. Contate o administrador.")

        ctx = self._context_builder.build(patient)
        clinical_text = self._context_builder.to_prompt_text(ctx)

        instruction = _PROFESSIONAL_INSTRUCTION if is_professional else _PATIENT_INSTRUCTION
        user_message = f"{instruction}\n\n{clinical_text}"

        return self._call_openai(api_key, user_message)

    def _call_openai(self, api_key: str, user_message: str) -> str:
        try:
            import httpx
            import openai
            from decouple import config as _cfg
            # OPENAI_SSL_VERIFY=false no .env local contorna SSL interceptado por antivírus.
            # Em produção (Cloud Run) a variável não existe → padrão True.
            ssl_verify = _cfg('OPENAI_SSL_VERIFY', default='true', cast=str).lower() != 'false'
            http_client = httpx.Client(verify=ssl_verify)
            client = openai.OpenAI(api_key=api_key, http_client=http_client)
            response = client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("LUMI OpenAI error: %s", exc, exc_info=True)
            raise LumiServiceError(
                "Não foi possível gerar o relatório no momento. Tente novamente em instantes."
            ) from exc


class LumiServiceError(Exception):
    """Erro controlado do serviço LUMI — mensagem segura para exibir ao usuário."""
