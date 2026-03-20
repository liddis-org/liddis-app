from django import forms
from .models import Consultation, VitalSign


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ['date', 'professional_name', 'specialty', 'diagnosis', 'notes', 'prescription']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'professional_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Ex: Dr. João Silva'}),
            'specialty': forms.Select(attrs={'class': 'input'}),
            'diagnosis': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'placeholder': 'Diagnóstico informado pelo profissional'}),
            'notes': forms.Textarea(attrs={'class': 'input', 'rows': 4, 'placeholder': 'Anotações, evolução clínica, observações...'}),
            'prescription': forms.Textarea(attrs={'class': 'input', 'rows': 4, 'placeholder': 'Medicamentos prescritos, dosagem e frequência...'}),
        }


class VitalSignForm(forms.ModelForm):
    class Meta:
        model = VitalSign
        fields = ['date', 'blood_pressure', 'heart_rate', 'weight', 'temperature', 'oxygen_saturation', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'blood_pressure': forms.TextInput(attrs={'class': 'input', 'placeholder': '120/80'}),
            'heart_rate': forms.NumberInput(attrs={'class': 'input', 'placeholder': '72'}),
            'weight': forms.NumberInput(attrs={'class': 'input', 'placeholder': '70.5', 'step': '0.1'}),
            'temperature': forms.NumberInput(attrs={'class': 'input', 'placeholder': '36.5', 'step': '0.1'}),
            'oxygen_saturation': forms.NumberInput(attrs={'class': 'input', 'placeholder': '98'}),
            'notes': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Observações opcionais'}),
        }
