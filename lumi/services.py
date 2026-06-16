"""
LUMI — IA de apoio clínico e preventivo do LIDDIS.

Responsabilidades:
  - ClinicalContextBuilder: coleta e estrutura todos os dados clínicos
  - DocumentExtractor: extrai texto de PDFs e descreve imagens via OpenAI Vision
  - LumiService: orquestra chamadas à OpenAI e retorna relatório estruturado
"""
from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é a LUMI, assistente de inteligência artificial clínica e preventiva do sistema "
    "LIDDIS (Plataforma de Saúde Integrada). "
    "Seu papel: analisar prontuários eletrônicos, identificar padrões clínicos, "
    "destacar riscos e oferecer orientações preventivas baseadas em evidências. "
    "REGRAS ABSOLUTAS:\n"
    "• NUNCA forneça diagnóstico médico, prescrição farmacológica ou conduta terapêutica.\n"
    "• SEMPRE deixe claro que suas análises são informativas e preventivas.\n"
    "• Em caso de dados insuficientes, informe claramente ao invés de especular.\n"
    "• Seja analítica, empática e responsável com dados de saúde.\n"
    "RASTREABILIDADE DE ORIGEM:\n"
    "• O prontuário pode conter dois tipos de registros:\n"
    "  1) Consultas registradas por PROFISSIONAIS DE SAÚDE — dados clínicos validados.\n"
    "  2) Consultas inseridas pelo PRÓPRIO PACIENTE — informações auto-relatadas, não validadas clinicamente.\n"
    "• Ao analisar, diferencie claramente a origem e calibre o peso de cada informação.\n"
    "• Registros do paciente são valiosos para contexto histórico, mas devem ser interpretados "
    "em conjunto com avaliações profissionais, quando disponíveis."
)

_PATIENT_INSTRUCTION = """
Você está gerando um relatório de saúde para o PRÓPRIO PACIENTE.

LINGUAGEM: simples, acolhedora, motivadora. Sem jargões técnicos excessivos.
FOCO: prevenção, autocuidado, importância do acompanhamento profissional.
TOM: parceiro de saúde, não médico.

Use EXATAMENTE esta estrutura (inclua apenas seções com dados disponíveis):

## 1. 📋 Resumo Geral da Saúde
(Visão geral do estado de saúde com base nos dados disponíveis)

## 2. 🔍 Principais Condições Identificadas
(Condições de saúde registradas no histórico)

## 3. ⚠️ Fatores de Risco
(Hábitos, sinais vitais ou dados que merecem atenção)

## 4. 🔄 Doenças Crônicas ou Condições Persistentes
(Condições de longo prazo identificadas)

## 5. 📈 Evolução Clínica Observada
(Como sua saúde evoluiu ao longo do tempo com base nos registros)

## 6. 💊 Medicamentos em Uso
(Medicamentos contínuos registrados)

## 7. 🚨 Alertas Importantes
(Pontos que exigem atenção imediata ou acompanhamento urgente)

## 8. 💡 Recomendações Preventivas
(Orientações práticas de prevenção adequadas ao seu perfil)

## 9. 📅 Pontos que Merecem Acompanhamento
(Aspectos a discutir na próxima consulta)

## 10. 📝 Observações Gerais
(Outras informações relevantes e encorajamento.
Se houver registros inseridos por você mesmo, mencione: "Algumas informações
foram inseridas diretamente por você e complementam as avaliações profissionais.")

---
⚕️ *Este relatório é informativo. Consulte sempre um profissional de saúde habilitado.*
"""

_PROFESSIONAL_INSTRUCTION = """
Você está gerando um RELATÓRIO CLÍNICO ESPECIALIZADO para um PROFISSIONAL DE SAÚDE durante o atendimento.

LINGUAGEM: técnica, objetiva, concisa.
FOCO: apoiar a tomada de decisão clínica — síntese de informações, destaque de riscos, facilitar o atendimento.
TOM: colega de equipe multidisciplinar experiente.
RESTRIÇÕES ABSOLUTAS: NUNCA forneça diagnóstico médico, NUNCA prescreva medicamentos,
NUNCA indique condutas terapêuticas. Atue como ferramenta de síntese e apoio ao profissional.
Quando informações forem extraídas de documentos ou anexos, cite explicitamente a origem.

Use EXATAMENTE esta estrutura (inclua apenas seções com dados disponíveis):

## 1. 📋 Resumo Geral do Paciente
(Síntese do perfil — idade, gênero, comorbidades principais, contexto clínico geral, total de consultas registradas)

## 2. 🔍 Principais Condições Identificadas
(Condições de saúde registradas no prontuário, incluindo diagnósticos CID quando disponíveis,
diferenciando registros profissionais de auto-relatos do paciente)

## 3. 🔄 Doenças Crônicas Encontradas
(Condições persistentes ou de longo prazo identificadas nos registros clínicos e no perfil permanente)

## 4. 🧪 Alterações Relevantes em Exames
(Valores fora da normalidade, tendências preocupantes nos exames laboratoriais e sinais vitais.
Se informação veio de documento anexado, cite: "identificado no anexo: [nome do arquivo]")

## 5. 💊 Medicamentos Registrados
(Medicamentos contínuos do perfil permanente e prescrições recentes.
Aponte possíveis interações ou lacunas terapêuticas se identificadas nos dados)

## 6. ⚠️ Fatores de Risco
(Tabagismo, etilismo, hipertensão, glicemia elevada, histórico familiar — dados presentes nos registros)

## 7. 🚨 Alertas Importantes
(Sinais de alerta prioritários, valores críticos, dados que exigem atenção imediata neste atendimento.
PRIORIDADE MÁXIMA — liste primeiro os mais urgentes)

## 8. 📈 Evolução Histórica do Paciente
(Comparativo entre consultas anteriores, progressão de condições,
resposta a tratamentos anteriores, tendências ao longo do tempo)

## 9. 👁️ Pontos que Merecem Atenção Durante o Atendimento
(Aspectos específicos a investigar, questionar ou monitorar neste atendimento,
com base nas lacunas ou inconsistências identificadas no prontuário)

## 10. 💡 Recomendações Preventivas
(Sugestões de acompanhamento, exames complementares sugeridos, frequência de retorno,
encaminhamentos recomendados — baseados nos dados disponíveis)

---
## ℹ️ Qualidade e Origem dos Dados
(Proporção de registros profissionais vs. auto-relatos do paciente.
Impacto na confiabilidade da análise. Lacunas importantes no prontuário)

---
⚕️ *Relatório informativo da LUMI — ferramenta de apoio clínico. Não substitui avaliação do profissional.*
"""


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
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

    # Sinais vitais (últimos 5)
    vitals: list = field(default_factory=list)

    # Histórico de consultas (anamneses últimas 5)
    anamneses: list = field(default_factory=list)

    # Intervenções clínicas (últimas 5)
    interventions: list = field(default_factory=list)

    # Evoluções esperadas (últimas 3)
    evolutions: list = field(default_factory=list)

    # Exames laboratoriais (últimos 3)
    lab_exams: list = field(default_factory=list)

    # Prescrições (últimas 3)
    prescriptions: list = field(default_factory=list)

    # Diagnósticos CID-10 registrados (últimos 5)
    diagnoses: list = field(default_factory=list)

    # Evoluções multiprofissionais (últimas 5)
    professional_evolutions: list = field(default_factory=list)

    # Conteúdo extraído de documentos anexados
    document_extracts: list = field(default_factory=list)

    # Consultas registradas manualmente pelo paciente
    patient_records: list = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Document Extractor
# ──────────────────────────────────────────────────────────────────────────────

class DocumentExtractor:
    """Extrai texto de PDFs (pypdf) e descreve imagens (OpenAI Vision)."""

    MAX_PDF_CHARS  = 3000  # Limite por PDF para não explodir o contexto
    MAX_DOCS       = 8     # Máximo de documentos analisados por relatório
    IMAGE_EXTS     = {'.jpg', '.jpeg', '.png', '.webp'}

    def extract_from_attachments(
        self, patient, api_key: str, ssl_verify: bool = True
    ) -> list[str]:
        """
        Coleta os anexos mais recentes do paciente e extrai conteúdo útil.
        Retorna lista de strings descritivas para incluir no contexto.
        """
        from consultations.models import ConsultationImage

        attachments = (
            ConsultationImage.objects
            .filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-uploaded_at')[:self.MAX_DOCS]
        )

        results = []
        for attachment in attachments:
            try:
                content = self._process(attachment, api_key, ssl_verify)
                if content:
                    results.append(content)
            except Exception as exc:
                logger.warning("LUMI doc extract failed | %s | %s", attachment.pk, exc)

        return results

    def _process(self, attachment, api_key: str, ssl_verify: bool) -> Optional[str]:
        name = (attachment.image.name or '').lower()
        ext  = os.path.splitext(name)[1]

        if ext == '.pdf':
            return self._extract_pdf(attachment)
        elif ext in self.IMAGE_EXTS:
            return self._describe_image(attachment, api_key, ssl_verify)
        return None

    # ── PDF ──────────────────────────────────────────────────────────────────

    def _extract_pdf(self, attachment) -> Optional[str]:
        try:
            import pypdf
        except ImportError:
            logger.warning("pypdf não instalado — PDF ignorado")
            return None

        data = self._read_bytes(attachment)
        if not data:
            return None

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages_text = []
            for page in reader.pages:
                text = page.extract_text() or ''
                pages_text.append(text)
            full_text = '\n'.join(pages_text).strip()
            if not full_text:
                return f"PDF '{attachment.filename}': sem texto extraível (possivelmente escaneado)"
            return (
                f"PDF '{attachment.filename}' "
                f"(consulta {attachment.consultation.date}):\n"
                f"{full_text[:self.MAX_PDF_CHARS]}"
            )
        except Exception as exc:
            logger.warning("pypdf error | %s | %s", attachment.filename, exc)
            return None

    # ── Imagem ───────────────────────────────────────────────────────────────

    def _describe_image(
        self, attachment, api_key: str, ssl_verify: bool
    ) -> Optional[str]:
        # Se tem legenda, usa direto — economiza chamada de API
        if attachment.caption and len(attachment.caption) > 10:
            return (
                f"Imagem '{attachment.filename}' "
                f"(consulta {attachment.consultation.date}): {attachment.caption}"
            )

        data = self._read_bytes(attachment)
        if not data:
            return None

        ext  = os.path.splitext(attachment.filename)[1].lstrip('.').lower()
        mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        b64  = base64.b64encode(data).decode()

        try:
            import httpx, openai
            http_client = httpx.Client(verify=ssl_verify)
            client = openai.OpenAI(api_key=api_key, http_client=http_client)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Este é um documento médico/exame/laudo. "
                                "Descreva de forma objetiva o que contém: "
                                "valores de exames, diagnósticos, medicamentos ou informações clínicas relevantes. "
                                "Seja conciso (máximo 3 parágrafos)."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }],
            )
            description = resp.choices[0].message.content.strip()
            return (
                f"Imagem '{attachment.filename}' "
                f"(consulta {attachment.consultation.date}):\n{description}"
            )
        except Exception as exc:
            logger.warning("Vision API error | %s | %s", attachment.filename, exc)
            # Fallback: retorna só metadados
            return f"Imagem anexada: {attachment.filename} (consulta {attachment.consultation.date})"

    # ── Storage helper ────────────────────────────────────────────────────────

    def _read_bytes(self, attachment) -> Optional[bytes]:
        """Lê o arquivo via storage configurado (GCS em produção, filesystem em dev) —
        delega ao backend ativo em STORAGES['default'] em vez de acessar GCS/disco diretamente."""
        try:
            with attachment.image.open('rb') as f:
                return f.read()
        except Exception as exc:
            logger.warning("Leitura de anexo falhou | %s | %s", attachment.image.name, exc)
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Clinical Context Builder
# ──────────────────────────────────────────────────────────────────────────────

class ClinicalContextBuilder:
    """Coleta e estrutura todos os dados clínicos do paciente."""

    def build(self, patient, api_key: str = '', ssl_verify: bool = True) -> ClinicalContext:
        from consultations.models import (
            VitalSign, Anamnese, ClinicalIntervention,
            ExpectedEvolution, ExameLaboratorial, Consultation,
        )

        # ── Perfil clínico permanente ─────────────────────────────────────────
        try:
            summary = patient.clinical_summary
            comorbidities          = summary.comorbidities or ''
            allergies              = summary.allergies or ''
            continuous_medications = summary.continuous_medications or ''
            smokes                 = summary.get_smokes_display() if summary.smokes else ''
            drinks                 = summary.get_drinks_display() if summary.drinks else ''
        except Exception:
            comorbidities = allergies = continuous_medications = smokes = drinks = ''

        # ── Sinais vitais ─────────────────────────────────────────────────────
        raw_vitals = (
            VitalSign.objects.filter(patient=patient)
            .order_by('-date', '-created_at')[:5]
        )
        vitals = [self._format_vital(v) for v in raw_vitals]

        # ── Anamneses ─────────────────────────────────────────────────────────
        raw_anamneses = (
            Anamnese.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:5]
        )
        anamneses = [self._format_anamnese(a) for a in raw_anamneses]

        # ── Intervenções clínicas ─────────────────────────────────────────────
        raw_interventions = (
            ClinicalIntervention.objects.filter(consultation__patient=patient)
            .select_related('consultation', 'professional')
            .order_by('-consultation__date')[:5]
        )
        interventions = [self._format_intervention(i) for i in raw_interventions]

        # ── Evoluções esperadas ───────────────────────────────────────────────
        raw_evolutions = (
            ExpectedEvolution.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:3]
        )
        evolutions = [self._format_evolution(e) for e in raw_evolutions]

        # ── Exames laboratoriais ──────────────────────────────────────────────
        raw_exams = (
            ExameLaboratorial.objects.filter(consultation__patient=patient)
            .select_related('consultation')
            .order_by('-consultation__date')[:3]
        )
        lab_exams = [self._format_exam(e) for e in raw_exams]

        # ── Prescrições (campo da consulta) ───────────────────────────────────
        raw_prescriptions = (
            Consultation.objects.filter(patient=patient)
            .exclude(prescription='')
            .order_by('-date')[:3]
        )
        prescriptions = [
            f"{c.date}: {c.prescription[:300]}" for c in raw_prescriptions
        ]

        # ── Diagnósticos CID-10 ───────────────────────────────────────────────
        from consultations.models import DiagnosisCID, Evolution as EvolutionMulti
        raw_diagnoses = (
            DiagnosisCID.objects.filter(consultation__patient=patient)
            .select_related('consultation', 'professional')
            .order_by('-consultation__date', '-created_at')[:5]
        )
        diagnoses = [self._format_diagnosis(d) for d in raw_diagnoses]

        # ── Evoluções multiprofissionais ──────────────────────────────────────
        raw_pro_evolutions = (
            EvolutionMulti.objects.filter(consultation__patient=patient)
            .select_related('consultation', 'professional')
            .order_by('-consultation__date', '-created_at')[:5]
        )
        professional_evolutions = [self._format_professional_evolution(e) for e in raw_pro_evolutions]

        # ── Consultas inseridas manualmente pelo paciente ─────────────────────
        raw_patient_records = (
            Consultation.objects.filter(
                patient=patient, record_origin='patient_manual'
            ).order_by('-date')[:5]
        )
        patient_records = [self._format_patient_record(c) for c in raw_patient_records]

        # ── Documentos anexados ───────────────────────────────────────────────
        document_extracts: list[str] = []
        if api_key:
            try:
                extractor = DocumentExtractor()
                document_extracts = extractor.extract_from_attachments(
                    patient, api_key, ssl_verify
                )
            except Exception as exc:
                logger.warning("LUMI: document extraction skipped | %s", exc)

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
            evolutions=evolutions,
            lab_exams=lab_exams,
            prescriptions=prescriptions,
            diagnoses=diagnoses,
            professional_evolutions=professional_evolutions,
            document_extracts=document_extracts,
            patient_records=patient_records,
        )

    # ── Formatters ────────────────────────────────────────────────────────────

    def _format_vital(self, v) -> str:
        parts = [f"Data: {v.date}"]
        if v.blood_pressure:    parts.append(f"PA: {v.blood_pressure}")
        if v.heart_rate:        parts.append(f"FC: {v.heart_rate} bpm")
        if v.temperature:       parts.append(f"T°: {v.temperature}°C")
        if v.oxygen_saturation: parts.append(f"SpO₂: {v.oxygen_saturation}%")
        if v.weight:            parts.append(f"Peso: {v.weight} kg")
        if v.height:            parts.append(f"Altura: {v.height} cm")
        if v.glucose:           parts.append(f"Glicemia: {v.glucose} mg/dL")
        if v.respiratory_rate:  parts.append(f"FR: {v.respiratory_rate} irpm")
        if v.notes:             parts.append(f"Obs: {v.notes}")
        if v.other_signs:       parts.append(f"Outros: {v.other_signs}")
        return " | ".join(parts)

    def _format_anamnese(self, a) -> str:
        parts = [f"[Consulta {a.consultation.date} — {a.consultation.specialty_label}]"]
        if a.chief_complaint: parts.append(f"Queixa: {a.chief_complaint}")
        if a.history:         parts.append(f"HDA: {a.history}")
        if a.past_history:    parts.append(f"Antecedentes pessoais: {a.past_history}")
        if a.family_history:  parts.append(f"Hist. familiar: {a.family_history}")
        if a.medications:     parts.append(f"Medicamentos: {a.medications}")
        if a.allergies:       parts.append(f"Alergias: {a.allergies}")
        return "\n".join(parts)

    def _format_intervention(self, i) -> str:
        parts = [
            f"[Consulta {i.consultation.date} — "
            f"{getattr(i.professional, 'display_name', 'Profissional') if i.professional else 'Profissional'}]"
        ]
        if i.professional_diagnosis: parts.append(f"Diagnóstico: {i.professional_diagnosis}")
        if i.classification_code:    parts.append(f"Classificação: {i.classification_code}")
        if i.related_factors:        parts.append(f"Fatores relacionados: {i.related_factors}")
        if i.conducts:               parts.append(f"Condutas: {i.conducts}")
        if i.procedures:             parts.append(f"Procedimentos: {i.procedures}")
        if i.guidelines:             parts.append(f"Orientações: {i.guidelines}")
        if i.clinical_actions:       parts.append(f"Ações clínicas: {i.clinical_actions}")
        return "\n".join(parts)

    def _format_evolution(self, e) -> str:
        parts = [f"[Evolução — Consulta {e.consultation.date}]"]
        if e.estimated_timeframe: parts.append(f"Prazo: {e.estimated_timeframe}")
        if e.priority:            parts.append(f"Prioridade: {e.get_priority_display()}")
        if e.clinical_evolution:  parts.append(f"Resultados esperados: {e.clinical_evolution}")
        if e.therapeutic_goals:   parts.append(f"Metas: {e.therapeutic_goals}")
        if e.follow_up_plan:      parts.append(f"Acompanhamento: {e.follow_up_plan}")
        if e.treatment_response:  parts.append(f"Resposta ao tratamento: {e.treatment_response}")
        return "\n".join(parts)

    def _format_exam(self, e) -> str:
        parts = [f"[Exames — Consulta {e.consultation.date}]"]
        for attr, label in [
            ('hemograma', 'Hemograma'), ('glicemia', 'Glicemia'),
            ('colesterol', 'Colesterol'), ('funcao_renal', 'Função renal'),
            ('funcao_hepatica', 'Função hepática'), ('hormonal', 'Hormonal'),
            ('urina', 'Urina'), ('outros', 'Outros'),
        ]:
            val = getattr(e, attr, '')
            if val:
                parts.append(f"{label}: {val}")
        return "\n".join(parts)

    def _format_diagnosis(self, d) -> str:
        parts = [f"[Diagnóstico CID — Consulta {d.consultation.date}]"]
        parts.append(f"CID: {d.icd_code}")
        if d.description:  parts.append(f"Descrição: {d.description}")
        if d.notes:        parts.append(f"Notas clínicas: {d.notes[:300]}")
        parts.append(f"Certeza: {d.get_certainty_display()}")
        if d.is_primary:   parts.append("(Diagnóstico principal)")
        if d.professional: parts.append(f"Registrado por: {getattr(d.professional, 'display_name', 'Profissional')}")
        return "\n".join(parts)

    def _format_professional_evolution(self, e) -> str:
        prof = getattr(e.professional, 'display_name', 'Profissional') if e.professional else 'Profissional'
        parts = [f"[Evolução {e.get_category_display()} — Consulta {e.consultation.date} | {prof}]"]
        if e.content: parts.append(e.content[:500])
        return "\n".join(parts)

    def _format_patient_record(self, c) -> str:
        parts = [
            f"[Registro Manual — {c.date} | {c.specialty_label} | Prof.: {c.professional_name}]"
        ]
        if c.diagnosis: parts.append(f"Diagnóstico informado: {c.diagnosis}")
        if c.notes:     parts.append(f"Notas: {c.notes[:400]}")
        if c.prescription: parts.append(f"Prescrição: {c.prescription[:300]}")
        return "\n".join(parts)

    def to_prompt_text(self, ctx: ClinicalContext) -> str:
        """Serializa o contexto clínico completo em texto estruturado."""
        lines = [
            "═══════════════════════════════════════",
            "PRONTUÁRIO CLÍNICO — LIDDIS",
            "═══════════════════════════════════════",
            f"Paciente: {ctx.patient_name}",
        ]
        if ctx.patient_age:   lines.append(f"Idade: {ctx.patient_age} anos")
        if ctx.patient_gender: lines.append(f"Sexo: {ctx.patient_gender}")

        lines.append("\n─── PERFIL CLÍNICO PERMANENTE ───")
        if ctx.comorbidities:          lines.append(f"Comorbidades: {ctx.comorbidities}")
        if ctx.allergies:              lines.append(f"Alergias: {ctx.allergies}")
        if ctx.continuous_medications: lines.append(f"Medicamentos contínuos: {ctx.continuous_medications}")
        if ctx.smokes:                 lines.append(f"Tabagismo: {ctx.smokes}")
        if ctx.drinks:                 lines.append(f"Etilismo: {ctx.drinks}")
        if not any([ctx.comorbidities, ctx.allergies, ctx.continuous_medications]):
            lines.append("(Perfil clínico permanente não preenchido)")

        if ctx.vitals:
            lines.append("\n─── SINAIS VITAIS RECENTES ───")
            for v in ctx.vitals:
                lines.append(f"• {v}")

        if ctx.anamneses:
            lines.append("\n─── HISTÓRICO DE CONSULTAS / ANAMNESES ───")
            lines.append("[FONTE: Profissionais de saúde — dados clinicamente registrados na plataforma]")
            for a in ctx.anamneses:
                lines.append(a)
                lines.append("")

        if ctx.interventions:
            lines.append("\n─── INTERVENÇÕES CLÍNICAS REGISTRADAS ───")
            lines.append("[FONTE: Profissionais de saúde — dados clinicamente validados]")
            for i in ctx.interventions:
                lines.append(i)
                lines.append("")

        if ctx.evolutions:
            lines.append("\n─── EVOLUÇÕES ESPERADAS ───")
            for e in ctx.evolutions:
                lines.append(e)
                lines.append("")

        if ctx.lab_exams:
            lines.append("\n─── EXAMES LABORATORIAIS ───")
            for e in ctx.lab_exams:
                lines.append(e)
                lines.append("")

        if ctx.prescriptions:
            lines.append("\n─── PRESCRIÇÕES RECENTES ───")
            for p in ctx.prescriptions:
                lines.append(f"• {p}")

        if ctx.diagnoses:
            lines.append("\n─── DIAGNÓSTICOS CID-10 REGISTRADOS ───")
            lines.append("[FONTE: Profissionais de saúde — diagnósticos clinicamente registrados]")
            for d in ctx.diagnoses:
                lines.append(d)
                lines.append("")

        if ctx.professional_evolutions:
            lines.append("\n─── EVOLUÇÕES MULTIPROFISSIONAIS ───")
            lines.append("[FONTE: Evoluções registradas por profissionais de saúde na plataforma]")
            for e in ctx.professional_evolutions:
                lines.append(e)
                lines.append("")

        if ctx.patient_records:
            lines.append("\n─── CONSULTAS CADASTRADAS PELO PRÓPRIO PACIENTE ───")
            lines.append(
                "[FONTE: Auto-relato do paciente | Não validado clinicamente por profissional.\n"
                " Pode incluir: consultas externas, atendimentos particulares, exames anteriores.\n"
                " Interpretar em conjunto com avaliações profissionais quando disponíveis.]"
            )
            for r in ctx.patient_records:
                lines.append(r)
                lines.append("")

        if ctx.document_extracts:
            lines.append("\n─── DOCUMENTOS E ANEXOS ANALISADOS ───")
            for d in ctx.document_extracts:
                lines.append(d)
                lines.append("")

        # Metadados de qualidade — orientam a LUMI sobre confiabilidade dos dados
        has_professional = bool(ctx.anamneses or ctx.interventions or ctx.evolutions)
        has_patient_self = bool(ctx.patient_records)
        lines.append("\n─── QUALIDADE E ORIGEM DOS DADOS ───")
        if has_professional and has_patient_self:
            lines.append(
                "CLASSIFICAÇÃO: PRONTUÁRIO MISTO\n"
                "Contém registros de PROFISSIONAIS DE SAÚDE (clinicamente validados) "
                "E AUTO-RELATOS DO PACIENTE (informações complementares, não validadas).\n"
                "Ao elaborar o relatório: distingua as fontes; mencione que parte das informações "
                "foi inserida pelo paciente e deve ser interpretada em conjunto com avaliações profissionais."
            )
        elif has_professional:
            lines.append(
                "CLASSIFICAÇÃO: PRONTUÁRIO PROFISSIONAL\n"
                "Registros gerados exclusivamente por profissionais de saúde via plataforma LIDDIS."
            )
        elif has_patient_self:
            lines.append(
                "CLASSIFICAÇÃO: REGISTROS AUTO-RELATADOS\n"
                "Dados inseridos pelo próprio paciente. Sem avaliações de profissionais disponíveis.\n"
                "Deixe claro no relatório que todas as informações são auto-relatadas "
                "e recomende avaliação profissional para validação clínica."
            )
        else:
            lines.append(
                "CLASSIFICAÇÃO: DADOS BÁSICOS\n"
                "Apenas perfil clínico e sinais vitais. Sem histórico de consultas registrado."
            )

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# LUMI Service
# ──────────────────────────────────────────────────────────────────────────────

class LumiService:
    """Orquestra geração de relatório clínico pela LUMI usando OpenAI."""

    MODEL       = "gpt-4o-mini"
    MAX_TOKENS  = 2500   # Relatórios mais detalhados
    TEMPERATURE = 0.35

    def __init__(self):
        self._context_builder = ClinicalContextBuilder()

    def generate_report(
        self,
        patient,
        is_professional: bool,
        consultation=None,   # Consulta ativa (atendimento em curso)
    ) -> str:
        """
        Gera o relatório LUMI para o paciente.
        Se `consultation` for fornecida, inclui dados completos da consulta em andamento
        e analisa seus anexos via OCR/Vision.
        Lança LumiServiceError em caso de falha.
        """
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            raise LumiServiceError("Chave de API não configurada. Contate o administrador.")

        ssl_verify = self._get_ssl_verify()

        ctx = self._context_builder.build(patient, api_key=api_key, ssl_verify=ssl_verify)
        clinical_text = self._context_builder.to_prompt_text(ctx)

        # Se atendimento ativo, injeta dados completos da consulta corrente
        if consultation:
            clinical_text += self._format_active_consultation(consultation)
            active_docs = self._analyze_active_consultation_attachments(consultation, api_key, ssl_verify)
            if active_docs:
                clinical_text += "\n\n─── ANEXOS DA CONSULTA ATUAL (OCR/Vision) ───\n"
                clinical_text += "[Conteúdo extraído dos documentos e imagens desta consulta]\n"
                for doc in active_docs:
                    clinical_text += doc + "\n\n"

        instruction = _PROFESSIONAL_INSTRUCTION if is_professional else _PATIENT_INSTRUCTION
        user_message = f"{instruction}\n\n{clinical_text}"

        return self._call_openai(api_key, user_message, ssl_verify)

    def _analyze_active_consultation_attachments(
        self, consultation, api_key: str, ssl_verify: bool
    ) -> list[str]:
        """Analisa os anexos da consulta em andamento via OCR/Vision para incluir no relatório."""
        try:
            extractor = DocumentExtractor()
            results = []
            attachments = list(consultation.images.all()[:5])
            for attachment in attachments:
                try:
                    content = extractor._process(attachment, api_key, ssl_verify)
                    if content:
                        results.append(content)
                except Exception as exc:
                    logger.warning(
                        "LUMI: anexo da consulta ativa falhou | img=%s | %s",
                        attachment.pk, exc,
                    )
            return results
        except Exception as exc:
            logger.warning("LUMI: análise de anexos da consulta ativa ignorada | %s", exc)
            return []

    def _format_active_consultation(self, consultation) -> str:
        """Formata dados completos da consulta em andamento para incluir no contexto."""
        lines = [
            "\n═══════════════════════════════════════",
            "CONSULTA EM ANDAMENTO",
            "═══════════════════════════════════════",
            f"Data: {consultation.date}",
            f"Especialidade: {consultation.specialty_label}",
        ]
        if consultation.professional_name:
            lines.append(f"Profissional: {consultation.professional_name}")
        if consultation.diagnosis:    lines.append(f"Diagnóstico registrado: {consultation.diagnosis}")
        if consultation.notes:        lines.append(f"Evolução / Notas: {consultation.notes}")
        if consultation.prescription: lines.append(f"Prescrição: {consultation.prescription}")

        # Sinais vitais registrados nesta consulta
        try:
            vitals = list(consultation.vitals.all()[:3])
            if vitals:
                lines.append("\n── Sinais Vitais desta Consulta ──")
                for v in vitals:
                    parts = []
                    if v.blood_pressure:    parts.append(f"PA: {v.blood_pressure}")
                    if v.heart_rate:        parts.append(f"FC: {v.heart_rate} bpm")
                    if v.temperature:       parts.append(f"T°: {v.temperature}°C")
                    if v.oxygen_saturation: parts.append(f"SpO₂: {v.oxygen_saturation}%")
                    if v.glucose:           parts.append(f"Glicemia: {v.glucose} mg/dL")
                    if v.weight:            parts.append(f"Peso: {v.weight} kg")
                    if parts:
                        lines.append(f"• {' | '.join(parts)}")
        except Exception:
            pass

        # Diagnósticos CID desta consulta
        try:
            diagnoses = list(consultation.diagnoses.all()[:5])
            if diagnoses:
                lines.append("\n── Diagnósticos CID desta Consulta ──")
                for d in diagnoses:
                    flag = " [PRINCIPAL]" if d.is_primary else ""
                    lines.append(f"• {d.icd_code} — {d.description} ({d.get_certainty_display()}){flag}")
                    if d.notes: lines.append(f"  Notas: {d.notes[:200]}")
        except Exception:
            pass

        # Anamnese desta consulta
        try:
            anamnese = consultation.anamnese
            lines.append("\n── Anamnese desta Consulta ──")
            if anamnese.chief_complaint: lines.append(f"Queixa principal: {anamnese.chief_complaint}")
            if anamnese.history:         lines.append(f"HDA: {anamnese.history[:300]}")
            if anamnese.medications:     lines.append(f"Medicamentos: {anamnese.medications}")
            if anamnese.allergies:       lines.append(f"Alergias: {anamnese.allergies}")
        except Exception:
            pass

        # Intervenção clínica desta consulta
        try:
            ci = consultation.clinical_interventions.first()
            if ci:
                lines.append("\n── Intervenção Clínica ──")
                if ci.professional_diagnosis: lines.append(f"Diagnóstico clínico: {ci.professional_diagnosis}")
                if ci.classification_code:    lines.append(f"Classificação: {ci.classification_code}")
                if ci.conducts:               lines.append(f"Condutas: {ci.conducts[:400]}")
                if ci.procedures:             lines.append(f"Procedimentos: {ci.procedures[:300]}")
                if ci.guidelines:             lines.append(f"Orientações: {ci.guidelines[:300]}")
        except Exception:
            pass

        # Evoluções multiprofissionais desta consulta
        try:
            evolutions = list(consultation.evolutions.all()[:4])
            if evolutions:
                lines.append("\n── Evoluções desta Consulta ──")
                for e in evolutions:
                    prof = getattr(e.professional, 'display_name', 'Prof.') if e.professional else 'Prof.'
                    lines.append(f"[{e.get_category_display()} — {prof}]: {e.content[:300]}")
        except Exception:
            pass

        # Exames laboratoriais desta consulta
        try:
            exames = consultation.exames
            parts = []
            if exames.hemograma:      parts.append(f"Hemograma: {exames.hemograma}")
            if exames.glicemia:       parts.append(f"Glicemia: {exames.glicemia}")
            if exames.colesterol:     parts.append(f"Colesterol: {exames.colesterol}")
            if exames.funcao_renal:   parts.append(f"Função renal: {exames.funcao_renal}")
            if exames.outros:         parts.append(f"Outros: {exames.outros[:200]}")
            if parts:
                lines.append("\n── Exames desta Consulta ──")
                lines.extend(parts)
        except Exception:
            pass

        return "\n".join(lines)

    def _get_ssl_verify(self) -> bool:
        try:
            from decouple import config as _cfg
            return _cfg('OPENAI_SSL_VERIFY', default='true', cast=str).lower() != 'false'
        except Exception:
            return True

    def _call_openai(self, api_key: str, user_message: str, ssl_verify: bool = True) -> str:
        try:
            import httpx
            import openai
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
