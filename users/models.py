import uuid
import secrets
from datetime import date
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta


# ── Organização (multi-tenant) ─────────────────────────────────────────────────

class Organization(models.Model):
    class Plan(models.TextChoices):
        FREE         = 'free',         'Grátis'
        PREMIUM      = 'premium',      'Premium'
        PROFESSIONAL = 'professional', 'Profissional'
        ENTERPRISE   = 'enterprise',   'Enterprise'

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name      = models.CharField(max_length=200, verbose_name='Nome')
    slug      = models.SlugField(max_length=100, unique=True)
    cnpj      = models.CharField(max_length=18, blank=True, verbose_name='CNPJ')
    email     = models.EmailField(blank=True, verbose_name='E-mail')
    phone     = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    address   = models.CharField(max_length=300, blank=True, verbose_name='Endereço')
    city      = models.CharField(max_length=100, blank=True, verbose_name='Cidade')
    state     = models.CharField(max_length=2, blank=True, verbose_name='Estado')
    plan      = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE, verbose_name='Plano')
    is_active = models.BooleanField(default=True, verbose_name='Ativa')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Excluída em')

    class Meta:
        db_table            = 'organizations'
        verbose_name        = 'Organização'
        verbose_name_plural = 'Organizações'
        ordering            = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['plan']),
            models.Index(fields=['deleted_at']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active'])


# ── Usuário ────────────────────────────────────────────────────────────────────

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        PATIENT      = 'PATIENT',      'Paciente'
        DOCTOR       = 'DOCTOR',       'Médico'
        NURSE        = 'NURSE',        'Enfermeiro'
        NUTRITIONIST = 'NUTRITIONIST', 'Nutricionista'
        PHYSIO       = 'PHYSIO',       'Fisioterapeuta'
        ADMIN        = 'ADMIN',        'Administrador'

    # Identificador público seguro (não expõe PK sequencial em APIs)
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID público')

    role          = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT, verbose_name='Perfil')
    phone         = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Data de nascimento')
    bio           = models.TextField(max_length=500, blank=True, verbose_name='Sobre mim')
    profession             = models.CharField(max_length=100, blank=True, verbose_name='Profissão')
    professional_specialty = models.CharField(max_length=50,  blank=True, verbose_name='Especialidade')
    email      = models.EmailField(unique=True, verbose_name='E-mail')
    updated_at = models.DateTimeField(auto_now=True)

    # Verificação de identidade
    is_email_verified = models.BooleanField(default=False, verbose_name='E-mail verificado')
    is_phone_verified = models.BooleanField(default=False, verbose_name='Celular verificado')

    # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Excluído em')

    # Organização principal (opcional — complementado por OrganizationMember)
    organization = models.ForeignKey(
        Organization,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='primary_users',
        verbose_name='Organização',
    )

    class Meta:
        db_table            = 'users'
        verbose_name        = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering            = ['-date_joined']
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['role']),
            models.Index(fields=['email']),
            models.Index(fields=['deleted_at']),
        ]

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
        return self.is_email_verified

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active'])


# ── Membro da Organização (multi-tenant) ───────────────────────────────────────

class OrganizationMember(models.Model):
    class Role(models.TextChoices):
        OWNER  = 'owner',  'Proprietário'
        ADMIN  = 'admin',  'Administrador'
        MEMBER = 'member', 'Membro'
        VIEWER = 'viewer', 'Visualizador'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='org_memberships')
    role         = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER, verbose_name='Papel')
    is_active    = models.BooleanField(default=True)
    joined_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = 'organization_members'
        unique_together     = [['organization', 'user']]
        verbose_name        = 'Membro da Organização'
        verbose_name_plural = 'Membros da Organização'
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user} → {self.organization} ({self.get_role_display()})'


# ── Perfil do Paciente ─────────────────────────────────────────────────────────

class PatientProfile(models.Model):
    class BloodType(models.TextChoices):
        A_POS   = 'A+',  'A+'
        A_NEG   = 'A-',  'A-'
        B_POS   = 'B+',  'B+'
        B_NEG   = 'B-',  'B-'
        AB_POS  = 'AB+', 'AB+'
        AB_NEG  = 'AB-', 'AB-'
        O_POS   = 'O+',  'O+'
        O_NEG   = 'O-',  'O-'
        UNKNOWN = '',    'Não informado'

    class RiskLevel(models.TextChoices):
        LOW      = 'low',      'Baixo'
        MEDIUM   = 'medium',   'Médio'
        HIGH     = 'high',     'Alto'
        CRITICAL = 'critical', 'Crítico'

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile',
        verbose_name='Usuário',
    )

    # Dados pessoais clínicos
    cpf        = models.CharField(max_length=14, blank=True, verbose_name='CPF')
    blood_type = models.CharField(max_length=3, blank=True, choices=BloodType.choices, verbose_name='Tipo sanguíneo')

    # Histórico clínico (estruturado para IA)
    chronic_conditions  = models.TextField(blank=True, verbose_name='Condições crônicas')
    allergies           = models.TextField(blank=True, verbose_name='Alergias')
    current_medications = models.TextField(blank=True, verbose_name='Medicamentos em uso')

    # Contato de emergência
    emergency_contact_name  = models.CharField(max_length=100, blank=True, verbose_name='Contato de emergência')
    emergency_contact_phone = models.CharField(max_length=20,  blank=True, verbose_name='Telefone de emergência')

    # Plano de saúde
    health_insurance        = models.CharField(max_length=100, blank=True, verbose_name='Plano de saúde')
    health_insurance_number = models.CharField(max_length=50,  blank=True, verbose_name='Número do plano')

    # Campos semânticos para IA / relatórios
    risk_level       = models.CharField(max_length=10, choices=RiskLevel.choices, blank=True, verbose_name='Nível de risco')
    ai_last_analysis = models.DateTimeField(null=True, blank=True, verbose_name='Última análise IA')
    ai_summary       = models.TextField(blank=True, verbose_name='Resumo gerado por IA')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'patient_profiles'
        verbose_name        = 'Perfil do Paciente'
        verbose_name_plural = 'Perfis dos Pacientes'
        indexes = [
            models.Index(fields=['cpf']),
            models.Index(fields=['risk_level']),
            models.Index(fields=['blood_type']),
        ]

    def __str__(self):
        return f'Perfil — {self.user.display_name}'


# ── Código de Verificação OTP ──────────────────────────────────────────────────

class VerificationCode(models.Model):
    PURPOSE_EMAIL = 'email'
    PURPOSE_PHONE = 'phone'
    PURPOSE_LOGIN = 'login'
    PURPOSE_RESET = 'reset'

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
        db_table            = 'verification_codes'
        ordering            = ['-created_at']
        verbose_name        = 'Código de Verificação'
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
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        return cls.objects.create(user=user, code=code, purpose=purpose)

    def __str__(self):
        return f'{self.user.username} — {self.get_purpose_display()} ({self.code})'
