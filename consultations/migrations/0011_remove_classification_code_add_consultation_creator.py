import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_created_by(apps, schema_editor):
    """Backfill created_by from ConsultationSession.professional for existing records."""
    ConsultationSession = apps.get_model('consultations', 'ConsultationSession')
    for session in ConsultationSession.objects.filter(
        consultation__isnull=False,
        professional__isnull=False,
    ).select_related('consultation', 'professional'):
        c = session.consultation
        if c.created_by_id is None:
            c.created_by_id = session.professional_id
            c.save(update_fields=['created_by_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0010_patientclinicalsummary_weight'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Remover campo NANDA da tabela de intervenções clínicas
        migrations.RemoveField(
            model_name='clinicalintervention',
            name='classification_code',
        ),

        # 2. Adicionar FK de autoria na consulta (audit trail + RBAC de edição)
        migrations.AddField(
            model_name='consultation',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='consultations_created',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Criado por',
            ),
        ),

        # 3. Backfill created_by a partir das sessões existentes
        migrations.RunPython(populate_created_by, migrations.RunPython.noop),
    ]
