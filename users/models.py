import secrets
from datetime import date
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        PATIENT      = 'PATIENT',      'Paciente'
        DOCTOR       = 'DOCTOR',       'Médico'
        NURSE        = 'NURSE',        'Enfermeiro'
        NUTRITIONIST = 'NUTRITIONIST', 'Nutricionista'
        PHYSIO       = 'PHYSIO',       'Fisioterapeuta'
        ADMIN        = 'ADMIN',        'Administrador'

    role          = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    phone         = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Data de nascimento')
    bio           = models.TextField(max_length=500, blank=True, verbose_name='Sobre mim')
    email         = models.EmailField(unique=True, verbose_name='E-mail')
    updated_at    = models.DateTimeField(auto_now=True)

    # Verificação de identidade
    is_email_verified = models.BooleanField(default=False, verbose_name='E-mail verificado')
    is_phone_verified = models.BooleanField(default=False, verbose_name='Celular verificado')

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_verified(self):
        """Verdadeiro se o e-mail foi confirmado."""
        return self.is_email_verified


class VerificationCode(models.Model):
    """
    Código OTP de 6 dígitos enviado por e-mail ou SMS.
    Expira em 10 minutos. Cada novo envio invalida os anteriores.
    """
    PURPOSE_EMAIL  = 'email'
    PURPOSE_PHONE  = 'phone'
    PURPOSE_LOGIN  = 'login'   # 2FA no login (futuro)
    PURPOSE_RESET  = 'reset'   # redefinição de senha (futuro)

    PURPOSE_CHOICES = [
        (PURPOSE_EMAIL, 'Verificação de e-mail'),
        (PURPOSE_PHONE, 'Verificação de celular'),
        (PURPOSE_LOGIN, 'Login por código'),
        (PURPOSE_RESET, 'Redefinição de senha'),
    ]

    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='verification_codes')
    code       = models.CharField(max_length=6)
    purpose    = models.CharField(max_length=10, choices=PURPOSE_CHOICES, default=PURPOSE_EMAIL)
    is_used    = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Código de Verificação'
        verbose_name_plural = 'Códigos de Verificação'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    @classmethod
    def generate(cls, user, purpose=PURPOSE_EMAIL):
        """
        Invalida códigos anteriores do mesmo tipo e gera um novo
        usando secrets para garantia criptográfica.
        """
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        return cls.objects.create(user=user, code=code, purpose=purpose)

    def __str__(self):
        return f'{self.user.username} — {self.get_purpose_display()} ({self.code})'
