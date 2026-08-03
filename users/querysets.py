"""
Querysets reutilizáveis — fonte única de verdade para filtros críticos de negócio.
Importar daqui garante consistência entre views, APIs, forms e management commands.
"""
from django.contrib.auth import get_user_model

PROFESSIONAL_ROLES = frozenset({
    'DOCTOR', 'NURSE', 'NUTRITIONIST', 'PHYSIO',
    'SPEECH_THERAPIST', 'PHYSICAL_EDUCATOR', 'PSYCHOLOGIST',
    'DENTIST', 'OCC_THERAPIST', 'PHARMACIST', 'BIOMEDICO', 'ADMIN',
})


def verified_professionals(select_related=None):
    """
    Retorna QuerySet de profissionais com conta ativa e e-mail verificado.
    Regra de negócio: profissional invisível ao sistema enquanto não verificar o e-mail.

    Usado em: agendamentos, vínculos paciente-profissional, listagens e buscas.
    """
    User = get_user_model()
    qs = User.objects.filter(
        role__in=PROFESSIONAL_ROLES,
        is_active=True,
        is_email_verified=True,
    )
    if select_related:
        qs = qs.select_related(*select_related)
    return qs


def is_verified_professional(user) -> bool:
    """Verifica se um usuário específico é um profissional com e-mail verificado."""
    return (
        user is not None
        and user.is_authenticated
        and user.is_active
        and user.is_email_verified
        and user.role in PROFESSIONAL_ROLES
    )
