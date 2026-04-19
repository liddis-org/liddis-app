from django import forms
from .models import Consultation, VitalSign, Anamnese, ExameLaboratorial

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
    class Meta:
        model = VitalSign
        fields = ['date', 'blood_pressure', 'heart_rate', 'weight', 'temperature', 'oxygen_saturation', 'notes']
        widgets = {
            'date':              forms.DateInput(attrs={'type': 'date', **_I}),
            'blood_pressure':    forms.TextInput(attrs={**_I, 'placeholder': '120/80'}),
            'heart_rate':        forms.NumberInput(attrs={**_I, 'placeholder': '72'}),
            'weight':            forms.NumberInput(attrs={**_I, 'placeholder': '70.5', 'step': '0.1'}),
            'temperature':       forms.NumberInput(attrs={**_I, 'placeholder': '36.5', 'step': '0.1'}),
            'oxygen_saturation': forms.NumberInput(attrs={**_I, 'placeholder': '98'}),
            'notes':             forms.TextInput(attrs={**_I, 'placeholder': 'Observações opcionais'}),
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
