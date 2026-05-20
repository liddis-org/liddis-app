import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import EmailValidator
from .models import CustomUser, PlatformFeedback
from consultations.models import SPECIALTY_CHOICES

_INPUT      = {'class': 'input'}
_INPUT_DATE = {'class': 'input', 'type': 'date'}

# Roles considerados "profissionais" (não-paciente)
PROFESSIONAL_ROLES = {
    'DOCTOR', 'NURSE', 'NUTRITIONIST', 'PHYSIO',
    'SPEECH_THERAPIST', 'PHYSICAL_EDUCATOR', 'PSYCHOLOGIST',
    'DENTIST', 'OCC_THERAPIST', 'PHARMACIST', 'ADMIN',
}


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=80, required=True,
        widget=forms.TextInput(attrs={**_INPUT, 'placeholder': 'Seu nome', 'autocomplete': 'given-name'}),
        label='Nome',
        error_messages={'required': 'O nome é obrigatório.'},
    )
    last_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**_INPUT, 'placeholder': 'Sobrenome', 'autocomplete': 'family-name'}),
        label='Sobrenome',
    )
    email = forms.EmailField(
        required=True,
        validators=[EmailValidator(message='Informe um e-mail válido.')],
        widget=forms.EmailInput(attrs={**_INPUT, 'placeholder': 'seu@email.com', 'autocomplete': 'email'}),
        label='E-mail',
        error_messages={'required': 'O e-mail é obrigatório.', 'invalid': 'Informe um e-mail válido.'},
    )

    class Meta:
        model  = CustomUser
        fields = ('first_name', 'last_name', 'username', 'email', 'role', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                **_INPUT,
                'placeholder': 'ex: joao.silva',
                'autocomplete': 'username',
                'pattern': '[a-zA-Z0-9._]+',
            }),
            'role': forms.Select(attrs=_INPUT),
        }
        labels = {
            'username': 'Usuário (login)',
            'role':     'Tipo de conta',
        }
        error_messages = {
            'username': {
                'required': 'Escolha um nome de usuário.',
                'unique':   'Este nome de usuário já está em uso.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            **_INPUT, 'placeholder': 'Mínimo 8 caracteres', 'autocomplete': 'new-password',
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            **_INPUT, 'placeholder': 'Repita a senha', 'autocomplete': 'new-password',
        })
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirmar senha'
        self.fields['password1'].error_messages = {
            'required': 'A senha é obrigatória.',
        }
        self.fields['password2'].error_messages = {
            'required': 'Confirme a senha.',
            'password_mismatch': 'As senhas não coincidem.',
        }
        for field in ('username', 'password1', 'password2'):
            self.fields[field].help_text = ''

    # ── Validações de campo ────────────────────────────────────────────────

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if not name:
            raise forms.ValidationError('O nome é obrigatório.')
        if len(name) < 2:
            raise forms.ValidationError('O nome deve ter ao menos 2 caracteres.')
        if re.search(r'[0-9]', name):
            raise forms.ValidationError('O nome não pode conter números.')
        return name

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not username:
            raise forms.ValidationError('O usuário é obrigatório.')
        if len(username) < 3:
            raise forms.ValidationError('O usuário deve ter ao menos 3 caracteres.')
        if len(username) > 30:
            raise forms.ValidationError('O usuário deve ter no máximo 30 caracteres.')
        if not re.match(r'^[a-zA-Z0-9._]+$', username):
            raise forms.ValidationError(
                'Use apenas letras, números, pontos (.) e underscores (_).'
            )
        if username.startswith('.') or username.startswith('_') or username.endswith('.') or username.endswith('_'):
            raise forms.ValidationError('O usuário não pode começar ou terminar com ponto ou underscore.')
        if '..' in username or '__' in username:
            raise forms.ValidationError('O usuário não pode ter dois pontos ou underscores consecutivos.')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Este usuário já está em uso. Escolha outro.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('O e-mail é obrigatório.')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail já está cadastrado. Faça login ou recupere sua senha.')
        return email

    def clean_role(self):
        role = self.cleaned_data.get('role', '').strip()
        valid_roles = {r for r, _ in CustomUser.Role.choices}
        if role not in valid_roles:
            raise forms.ValidationError('Selecione um tipo de conta válido.')
        return role

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')
        if not password:
            raise forms.ValidationError('A senha é obrigatória.')
        if len(password) < 8:
            raise forms.ValidationError('A senha deve ter ao menos 8 caracteres.')
        if password.isdigit():
            raise forms.ValidationError('A senha não pode ser apenas números.')
        if password.lower() in ('password', 'senha', '12345678', 'qwerty123', 'liddis123'):
            raise forms.ValidationError('Escolha uma senha mais segura.')
        return password

    def clean(self):
        cleaned = super().clean()
        # Garante que username não seja idêntico ao e-mail inteiro ou à senha
        username = cleaned.get('username')
        email    = cleaned.get('email', '')
        password = cleaned.get('password1', '')
        if username and email and username == email.split('@')[0].lower():
            # Aviso leve — não bloqueia
            pass
        if username and password and username in password.lower():
            self.add_error('password1', 'A senha não deve conter seu nome de usuário.')
        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = (
            'first_name', 'last_name', 'email', 'phone',
            'date_of_birth', 'bio', 'role', 'profession', 'professional_specialty',
        )
        widgets = {
            'first_name':             forms.TextInput(attrs={**_INPUT, 'autocomplete': 'given-name'}),
            'last_name':              forms.TextInput(attrs={**_INPUT, 'autocomplete': 'family-name'}),
            'email':                  forms.EmailInput(attrs={**_INPUT, 'autocomplete': 'email'}),
            'phone':                  forms.TextInput(attrs={**_INPUT, 'placeholder': '(11) 99999-9999', 'autocomplete': 'tel', 'inputmode': 'tel'}),
            'date_of_birth':          forms.DateInput(attrs={**_INPUT_DATE, 'autocomplete': 'bday'}),
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
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Este e-mail já está em uso por outra conta.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        # Normaliza: remove tudo que não é dígito
        digits = re.sub(r'\D', '', phone)
        if phone and len(digits) < 10:
            raise forms.ValidationError('Informe um telefone válido com DDD (ex: (11) 99999-9999).')
        return phone

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if not name:
            raise forms.ValidationError('O nome é obrigatório.')
        return name


_SCORE_WIDGET = forms.RadioSelect(attrs={'class': 'score-radio'})

SCORE_CHOICES = [(i, str(i)) for i in range(1, 6)]


class PlatformFeedbackForm(forms.ModelForm):
    score_usability = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=_SCORE_WIDGET,
        label='Facilidade de uso',
    )
    score_performance = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=_SCORE_WIDGET,
        label='Velocidade / Desempenho',
    )
    score_care_quality = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=_SCORE_WIDGET,
        label='Qualidade do atendimento',
    )

    class Meta:
        model  = PlatformFeedback
        fields = ['score_usability', 'score_performance', 'score_care_quality', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'input', 'rows': 4,
                'placeholder': 'Compartilhe sua experiência, sugestões ou críticas construtivas...',
            }),
        }
        labels = {
            'comment': 'Comentário (opcional)',
        }
