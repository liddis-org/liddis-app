from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── VitalSign: novos campos e FKs ────────────────────────────────────────
        migrations.AddField(
            model_name='vitalsign',
            name='consultation',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vitals',
                to='consultations.consultation',
                verbose_name='Consulta',
            ),
        ),
        migrations.AddField(
            model_name='vitalsign',
            name='recorded_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vitals_recorded',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Registrado por',
            ),
        ),
        migrations.AddField(
            model_name='vitalsign',
            name='respiratory_rate',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Frequência respiratória (irpm)'),
        ),
        migrations.AddField(
            model_name='vitalsign',
            name='height',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True, verbose_name='Altura (cm)'),
        ),
        migrations.AddField(
            model_name='vitalsign',
            name='glucose',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Glicemia (mg/dL)'),
        ),
        migrations.AlterModelOptions(
            name='vitalsign',
            options={
                'ordering': ['-date', '-created_at'],
                'verbose_name': 'Sinal Vital',
                'verbose_name_plural': 'Sinais Vitais',
            },
        ),
        migrations.AddIndex(
            model_name='vitalsign',
            index=models.Index(fields=['patient', 'date'], name='vitals_patient_date_idx'),
        ),
        migrations.AddIndex(
            model_name='vitalsign',
            index=models.Index(fields=['consultation'], name='vitals_consultation_idx'),
        ),

        # ── PatientClinicalSummary ────────────────────────────────────────────────
        migrations.CreateModel(
            name='PatientClinicalSummary',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('allergies', models.TextField(blank=True, verbose_name='Alergias conhecidas')),
                ('continuous_medications', models.TextField(blank=True, verbose_name='Medicamentos de uso contínuo')),
                ('comorbidities', models.TextField(blank=True, verbose_name='Comorbidades / Condições crônicas')),
                ('smokes', models.CharField(
                    blank=True, max_length=10,
                    choices=[('no', 'Não'), ('yes', 'Sim'), ('former', 'Ex-fumante')],
                    verbose_name='Tabagismo',
                )),
                ('drinks', models.CharField(
                    blank=True, max_length=15,
                    choices=[('no', 'Não'), ('yes', 'Sim'), ('occasionally', 'Ocasionalmente')],
                    verbose_name='Etilismo',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='clinical_summary',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Paciente',
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='clinical_summaries_updated',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Última atualização por',
                )),
            ],
            options={
                'verbose_name': 'Perfil Clínico do Paciente',
                'verbose_name_plural': 'Perfis Clínicos dos Pacientes',
                'db_table': 'patient_clinical_summaries',
            },
        ),
    ]
