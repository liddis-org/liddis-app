from django import forms
from .models import (
    Consultation, VitalSign, Anamnese, ExameLaboratorial,
    Evolution, Prescription, DiagnosisCID, PhysicalExam, LabRequest,
    PatientClinicalSummary,
)

_I = {'class': 'input'}
_TA = lambda rows=3: {'class': 'input', 'rows': rows}


class ConsultationForm(forms.ModelForm):
    # Campos obrigatórios que no model têm blank=True
    clinic_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Clínica São Lucas, Lab Fleury...'}),
        label='Nome do Local',
        error_messages={'required': 'Informe o nome do local (clínica ou laboratório).'},
    )
    clinic_neighborhood = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Centro, Vila Mariana...'}),
        label='Bairro',
        error_messages={'required': 'Informe o bairro do local.'},
    )
    clinic_city = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: São Paulo, Belo Horizonte...'}),
        label='Cidade',
        error_messages={'required': 'Informe a cidade do local.'},
    )

    class Meta:
        model = Consultation
        fields = [
            'date', 'professional_name', 'specialty', 'specialty_other',
            'clinic_name', 'clinic_neighborhood', 'clinic_city', 'clinic_address',
            'diagnosis', 'notes', 'prescription',
        ]
        widgets = {
            'date':              forms.DateInput(attrs={'type': 'date', **_I}),
            'professional_name': forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Dr. João Silva'}),
            'specialty':         forms.Select(attrs=_I),
            'specialty_other':   forms.TextInput(attrs={**_I, 'placeholder': 'Descreva a especialidade'}),
            'clinic_address':    forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Rua das Flores, 123 (opcional)'}),
            'diagnosis':         forms.Textarea(attrs={**_TA(3), 'placeholder': 'Diagnóstico informado pelo profissional'}),
            'notes':             forms.Textarea(attrs={**_TA(4), 'placeholder': 'Anotações, evolução clínica, observações...'}),
            'prescription':      forms.Textarea(attrs={**_TA(4), 'placeholder': 'Medicamentos prescritos, dosagem e frequência...'}),
        }


class AnamneseForm(forms.ModelForm):
    class Meta:
        model = Anamnese
        fields = [
            'chief_complaint', 'history', 'past_history',
            'family_history', 'medications', 'allergies',
        ]
        widgets = {
            'chief_complaint': forms.Textarea(attrs={**_TA(3), 'placeholder': 'Descreva a queixa principal do paciente'}),
            'history':         forms.Textarea(attrs={**_TA(4), 'placeholder': 'História da doença atual — início, duração, evolução...'}),
            'past_history':    forms.Textarea(attrs={**_TA(3), 'placeholder': 'Cirurgias, internações, doenças crônicas...'}),
            'family_history':  forms.Textarea(attrs={**_TA(3), 'placeholder': 'Doenças hereditárias, histórico familiar relevante...'}),
            'medications':     forms.Textarea(attrs={**_TA(3), 'placeholder': 'Medicamentos em uso contínuo com dosagem...'}),
            'allergies':       forms.Textarea(attrs={**_TA(2), 'placeholder': 'Alergias a medicamentos, alimentos ou substâncias...'}),
        }


class ExameLaboratorialForm(forms.ModelForm):
    class Meta:
        model = ExameLaboratorial
        fields = [
            'hemograma', 'glicemia', 'colesterol', 'funcao_renal',
            'funcao_hepatica', 'hormonal', 'urina', 'outros',
        ]
        widgets = {
            'hemograma':       forms.Textarea(attrs={**_TA(2), 'placeholder': 'Resultados do hemograma completo...'}),
            'glicemia':        forms.Textarea(attrs={**_TA(2), 'placeholder': 'Glicemia em jejum, HbA1c...'}),
            'colesterol':      forms.Textarea(attrs={**_TA(2), 'placeholder': 'Colesterol total, HDL, LDL, triglicerídeos...'}),
            'funcao_renal':    forms.Textarea(attrs={**_TA(2), 'placeholder': 'Creatinina, ureia, TFG estimada...'}),
            'funcao_hepatica': forms.Textarea(attrs={**_TA(2), 'placeholder': 'TGO, TGP, fosfatase alcalina, bilirrubinas...'}),
            'hormonal':        forms.Textarea(attrs={**_TA(2), 'placeholder': 'TSH, T4, cortisol, testosterona, estrogênio...'}),
            'urina':           forms.Textarea(attrs={**_TA(2), 'placeholder': 'Resultado do EAS / urocultura...'}),
            'outros':          forms.Textarea(attrs={**_TA(3), 'placeholder': 'Outros exames complementares (imagem, ECG, etc.)...'}),
        }


class VitalSignForm(forms.ModelForm):
    """Formulário de sinais vitais para o próprio paciente."""
    class Meta:
        model = VitalSign
        fields = ['date', 'blood_pressure', 'heart_rate', 'weight', 'height', 'temperature', 'oxygen_saturation', 'glucose', 'notes']
        widgets = {
            'date':              forms.DateInput(attrs={'type': 'date', **_I}),
            'blood_pressure':    forms.TextInput(attrs={**_I, 'placeholder': '120/80 mmHg'}),
            'heart_rate':        forms.NumberInput(attrs={**_I, 'placeholder': '72 bpm'}),
            'weight':            forms.NumberInput(attrs={**_I, 'placeholder': '70.5', 'step': '0.1'}),
            'height':            forms.NumberInput(attrs={**_I, 'placeholder': '170', 'step': '0.1'}),
            'temperature':       forms.NumberInput(attrs={**_I, 'placeholder': '36.5', 'step': '0.1'}),
            'oxygen_saturation': forms.NumberInput(attrs={**_I, 'placeholder': '98'}),
            'glucose':           forms.NumberInput(attrs={**_I, 'placeholder': '100', 'step': '0.1'}),
            'notes':             forms.TextInput(attrs={**_I, 'placeholder': 'Observações opcionais'}),
        }


class VitalSignProfessionalForm(forms.ModelForm):
    """Formulário de sinais vitais preenchido pelo profissional durante a consulta."""
    class Meta:
        model = VitalSign
        fields = [
            'date', 'blood_pressure', 'heart_rate', 'respiratory_rate',
            'weight', 'height', 'temperature', 'oxygen_saturation', 'glucose', 'notes',
        ]
        widgets = {
            'date':              forms.DateInput(attrs={'type': 'date', **_I}),
            'blood_pressure':    forms.TextInput(attrs={**_I, 'placeholder': '120/80 mmHg'}),
            'heart_rate':        forms.NumberInput(attrs={**_I, 'placeholder': 'bpm'}),
            'respiratory_rate':  forms.NumberInput(attrs={**_I, 'placeholder': 'irpm'}),
            'weight':            forms.NumberInput(attrs={**_I, 'placeholder': 'kg', 'step': '0.1'}),
            'height':            forms.NumberInput(attrs={**_I, 'placeholder': 'cm', 'step': '0.1'}),
            'temperature':       forms.NumberInput(attrs={**_I, 'placeholder': '°C', 'step': '0.1'}),
            'oxygen_saturation': forms.NumberInput(attrs={**_I, 'placeholder': '%'}),
            'glucose':           forms.NumberInput(attrs={**_I, 'placeholder': 'mg/dL', 'step': '0.1'}),
            'notes':             forms.TextInput(attrs={**_I, 'placeholder': 'Observações clínicas'}),
        }
        labels = {
            'blood_pressure':    'Pressão Arterial (PA)',
            'heart_rate':        'Freq. Cardíaca (FC)',
            'respiratory_rate':  'Freq. Respiratória (FR)',
            'weight':            'Peso (kg)',
            'height':            'Altura (cm)',
            'temperature':       'Temperatura (°C)',
            'oxygen_saturation': 'Saturação O₂ (%)',
            'glucose':           'Glicemia (mg/dL)',
        }


class PatientClinicalSummaryForm(forms.ModelForm):
    """Perfil clínico permanente do paciente — editado pelos profissionais."""
    class Meta:
        model = PatientClinicalSummary
        fields = ['allergies', 'continuous_medications', 'comorbidities', 'smokes', 'drinks']
        widgets = {
            'allergies':              forms.Textarea(attrs={**_TA(3), 'placeholder': 'Penicilina, dipirona, látex, amendoim...'}),
            'continuous_medications': forms.Textarea(attrs={**_TA(3), 'placeholder': 'Metformina 850mg 2x/dia, Losartana 50mg...'}),
            'comorbidities':          forms.Textarea(attrs={**_TA(3), 'placeholder': 'DM2, HAS, Hipotireoidismo, Asma...'}),
            'smokes':                 forms.Select(attrs=_I),
            'drinks':                 forms.Select(attrs=_I),
        }
        labels = {
            'allergies':              'Alergias conhecidas',
            'continuous_medications': 'Medicamentos de uso contínuo',
            'comorbidities':          'Comorbidades / Condições crônicas',
            'smokes':                 'Tabagismo',
            'drinks':                 'Etilismo',
        }


class AtendimentoForm(forms.ModelForm):
    """Formulário do profissional — campos de identidade são auto-preenchidos na view."""
    clinic_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Clínica São Lucas, Lab Fleury...'}),
        label='Nome do Local',
        error_messages={'required': 'Informe o nome do local onde ocorreu o atendimento.'},
    )
    clinic_neighborhood = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Centro, Vila Mariana...'}),
        label='Bairro',
        error_messages={'required': 'Informe o bairro do local.'},
    )
    clinic_city = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={**_I, 'placeholder': 'Ex: São Paulo, Belo Horizonte...'}),
        label='Cidade',
        error_messages={'required': 'Informe a cidade do local.'},
    )

    class Meta:
        model = Consultation
        fields = ['date', 'clinic_name', 'clinic_neighborhood', 'clinic_city', 'clinic_address', 'diagnosis', 'notes', 'prescription']
        widgets = {
            'date':           forms.DateInput(attrs={'type': 'date', **_I}),
            'clinic_address': forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Rua das Flores, 123 (opcional)'}),
            'diagnosis':      forms.Textarea(attrs={**_TA(3), 'placeholder': 'Diagnóstico'}),
            'notes':          forms.Textarea(attrs={**_TA(4), 'placeholder': 'Anotações, evolução clínica...'}),
            'prescription':   forms.Textarea(attrs={**_TA(4), 'placeholder': 'Medicamentos prescritos...'}),
        }


# ── Formulários dos novos modelos clínicos ────────────────────────────────────

class EvolutionForm(forms.ModelForm):
    class Meta:
        model  = Evolution
        fields = ['category', 'content', 'is_visible_to_patient']
        widgets = {
            'category': forms.Select(attrs=_I),
            'content':  forms.Textarea(attrs={**_TA(6), 'placeholder': 'Registre a evolução clínica aqui...'}),
        }
        labels = {
            'category':             'Categoria',
            'content':              'Evolução',
            'is_visible_to_patient':'Visível ao paciente',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from users.permissions import get_evolution_create_category
            cat = get_evolution_create_category(user)
            if cat:
                # Pré-seleciona e desabilita a categoria — profissional só cria a própria
                self.fields['category'].initial = cat
                self.fields['category'].widget.attrs['disabled'] = True
                self.fields['category'].choices = [
                    c for c in Evolution.CATEGORY_CHOICES if c[0] == cat
                ]


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model  = Prescription
        fields = [
            'prescription_type', 'medication_name', 'dosage',
            'frequency', 'duration', 'route', 'content', 'is_active',
        ]
        widgets = {
            'prescription_type': forms.Select(attrs=_I),
            'medication_name':   forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Amoxicilina 500mg'}),
            'dosage':            forms.TextInput(attrs={**_I, 'placeholder': 'Ex: 500mg'}),
            'frequency':         forms.TextInput(attrs={**_I, 'placeholder': 'Ex: 8/8h'}),
            'duration':          forms.TextInput(attrs={**_I, 'placeholder': 'Ex: 7 dias'}),
            'route':             forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Via oral'}),
            'content':           forms.Textarea(attrs={**_TA(4), 'placeholder': 'Prescrição completa / orientações...'}),
        }
        labels = {
            'prescription_type': 'Tipo de prescrição',
            'medication_name':   'Medicamento / Item',
            'dosage':            'Dose',
            'frequency':         'Frequência',
            'duration':          'Duração',
            'route':             'Via de administração',
            'content':           'Prescrição completa',
            'is_active':         'Ativa',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from users.permissions import get_prescription_allowed_types
            allowed = get_prescription_allowed_types(user)
            self.fields['prescription_type'].choices = [
                (k, v) for k, v in Prescription.TYPE_CHOICES if k in allowed
            ]


class DiagnosisCIDForm(forms.ModelForm):
    class Meta:
        model  = DiagnosisCID
        fields = ['icd_code', 'description', 'notes', 'is_primary', 'certainty']
        widgets = {
            'icd_code':    forms.TextInput(attrs={**_I, 'placeholder': 'Ex: J18.9'}),
            'description': forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Pneumonia não especificada'}),
            'notes':       forms.Textarea(attrs={**_TA(3), 'placeholder': 'Observações clínicas adicionais...'}),
            'certainty':   forms.Select(attrs=_I),
        }
        labels = {
            'icd_code':    'Código CID-10',
            'description': 'Descrição',
            'notes':       'Observações',
            'is_primary':  'Diagnóstico principal',
            'certainty':   'Certeza diagnóstica',
        }


class PhysicalExamForm(forms.ModelForm):
    class Meta:
        model  = PhysicalExam
        fields = [
            'general_state', 'cardiovascular', 'respiratory', 'abdomen',
            'neurological', 'musculoskeletal', 'skin', 'orl', 'other_systems',
        ]
        widgets = {
            'general_state':   forms.Textarea(attrs={**_TA(2), 'placeholder': 'Estado geral, nível de consciência, hidratação...'}),
            'cardiovascular':  forms.Textarea(attrs={**_TA(2), 'placeholder': 'Bulhas cardíacas, ritmo, sopros...'}),
            'respiratory':     forms.Textarea(attrs={**_TA(2), 'placeholder': 'MV, ruídos adventícios, expansibilidade...'}),
            'abdomen':         forms.Textarea(attrs={**_TA(2), 'placeholder': 'Indolor, peristalse, hepatoesplenomegalia...'}),
            'neurological':    forms.Textarea(attrs={**_TA(2), 'placeholder': 'Orientado, pupilas, reflexos...'}),
            'musculoskeletal': forms.Textarea(attrs={**_TA(2), 'placeholder': 'Força muscular, amplitude de movimento, dor...'}),
            'skin':            forms.Textarea(attrs={**_TA(2), 'placeholder': 'Coloração, turgor, lesões...'}),
            'orl':             forms.Textarea(attrs={**_TA(2), 'placeholder': 'Orofaringe, linfonodos, tireoide...'}),
            'other_systems':   forms.Textarea(attrs={**_TA(2), 'placeholder': 'Outros achados relevantes...'}),
        }


class LabRequestForm(forms.ModelForm):
    class Meta:
        model  = LabRequest
        fields = ['exam_type', 'exam_description', 'urgency']
        widgets = {
            'exam_type':        forms.TextInput(attrs={**_I, 'placeholder': 'Ex: Hemograma completo, PCR, HbA1c...'}),
            'exam_description': forms.Textarea(attrs={**_TA(3), 'placeholder': 'Parâmetros específicos, contexto clínico...'}),
        }
        labels = {
            'exam_type':        'Tipo de exame',
            'exam_description': 'Descrição / parâmetros',
            'urgency':          'Urgência',
        }


class LabResultForm(forms.ModelForm):
    """Preenchimento de resultado — exclusivo para biomédico / laboratorista."""
    class Meta:
        model  = LabRequest
        fields = ['result', 'result_date', 'reference_values', 'status']
        widgets = {
            'result':           forms.Textarea(attrs={**_TA(5), 'placeholder': 'Resultado completo do exame...'}),
            'result_date':      forms.DateInput(attrs={'type': 'date', **_I}),
            'reference_values': forms.Textarea(attrs={**_TA(3), 'placeholder': 'Valores de referência utilizados...'}),
            'status':           forms.Select(attrs=_I),
        }
        labels = {
            'result':           'Resultado',
            'result_date':      'Data do resultado',
            'reference_values': 'Valores de referência',
            'status':           'Status',
        }
