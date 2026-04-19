from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from consultations.models import SPECIALTY_CHOICES

_INPUT = {'class': 'input'}
_INPUT_DATE = {'class': 'input', 'type': 'date'}


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=80, required=True,
        widget=forms.TextInput(attrs={**_INPUT, 'placeholder': 'Seu nome'}),
        label='Nome',
    )
    last_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**_INPUT, 'placeholder': 'Sobrenome'}),
        label='Sobrenome',
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={**_INPUT, 'placeholder': 'seu@email.com'}),
        label='E-mail',
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'username', 'email', 'role', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={**_INPUT, 'placeholder': 'ex: joao.silva'}),
            'role': forms.Select(attrs=_INPUT),
        }
        labels = {
            'username': 'Usuário (login)',
            'role': 'Tipo de conta',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={**_INPUT, 'placeholder': 'Mínimo 8 caracteres'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={**_INPUT, 'placeholder': 'Repita a senha'})
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirmar senha'
        # Remove textos de ajuda confusos
        for field in ('username', 'password1', 'password2'):
            self.fields[field].help_text = ''

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'bio', 'role', 'profession', 'professional_specialty')
        widgets = {
            'first_name':             forms.TextInput(attrs=_INPUT),
            'last_name':              forms.TextInput(attrs=_INPUT),
            'email':                  forms.EmailInput(attrs=_INPUT),
            'phone':                  forms.TextInput(attrs={**_INPUT, 'placeholder': '(11) 99999-9999'}),
            'date_of_birth':          forms.DateInput(attrs=_INPUT_DATE),
            'bio':                    forms.Textarea(attrs={**_INPUT, 'rows': 3, 'placeholder': 'Conte um pouco sobre você...'}),
            'role':                   forms.Select(attrs=_INPUT),
            'profession':             forms.TextInput(attrs={**_INPUT, 'placeholder': 'Ex: Médico, Fisioterapeuta...'}),
            'professional_specialty': forms.Select(attrs=_INPUT, choices=[('', '— Selecione —')] + SPECIALTY_CHOICES),
        }
        labels = {
            'first_name':             'Nome',
            'last_name':              'Sobrenome',
            'email':                  'E-mail',
            'phone':                  'Telefone',
            'date_of_birth':          'Data de nascimento',
            'bio':                    'Sobre mim',
            'role':                   'Tipo de conta',
            'profession':             'Profissão',
            'professional_specialty': 'Especialidade',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        qs = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email