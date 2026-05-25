import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0004_clinical_summary_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── ClinicalIntervention ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='ClinicalIntervention',
            fields=[
                ('id',               models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('conducts',         models.TextField(blank=True, verbose_name='Condutas clínicas')),
                ('procedures',       models.TextField(blank=True, verbose_name='Procedimentos realizados')),
                ('guidelines',       models.TextField(blank=True, verbose_name='Orientações ao paciente')),
                ('clinical_actions', models.TextField(blank=True, verbose_name='Ações clínicas executadas')),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
                ('consultation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='clinical_interventions',
                    to='consultations.consultation',
                    verbose_name='Consulta',
                )),
                ('professional', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='interventions_written',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Profissional',
                )),
            ],
            options={
                'verbose_name':        'Intervenção Clínica',
                'verbose_name_plural': 'Intervenções Clínicas',
                'db_table':            'clinical_interventions',
                'ordering':            ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='clinicalintervention',
            index=models.Index(fields=['consultation'], name='intervention_consultation_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicalintervention',
            index=models.Index(fields=['professional'], name='intervention_professional_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicalintervention',
            index=models.Index(fields=['created_at'], name='intervention_created_at_idx'),
        ),

        # ── ExpectedEvolution ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ExpectedEvolution',
            fields=[
                ('id',                 models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('clinical_evolution', models.TextField(blank=True, verbose_name='Evolução clínica esperada')),
                ('therapeutic_goals',  models.TextField(blank=True, verbose_name='Metas terapêuticas')),
                ('follow_up_plan',     models.TextField(blank=True, verbose_name='Plano de acompanhamento')),
                ('prognosis',          models.TextField(blank=True, verbose_name='Prognóstico')),
                ('treatment_response', models.TextField(blank=True, verbose_name='Resposta esperada ao tratamento')),
                ('created_at',         models.DateTimeField(auto_now_add=True)),
                ('updated_at',         models.DateTimeField(auto_now=True)),
                ('consultation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='expected_evolutions',
                    to='consultations.consultation',
                    verbose_name='Consulta',
                )),
                ('professional', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='expected_evolutions_written',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Profissional',
                )),
            ],
            options={
                'verbose_name':        'Evolução Esperada',
                'verbose_name_plural': 'Evoluções Esperadas',
                'db_table':            'expected_evolutions',
                'ordering':            ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='expectedevolution',
            index=models.Index(fields=['consultation'], name='exp_evolution_consultation_idx'),
        ),
        migrations.AddIndex(
            model_name='expectedevolution',
            index=models.Index(fields=['professional'], name='exp_evolution_professional_idx'),
        ),
        migrations.AddIndex(
            model_name='expectedevolution',
            index=models.Index(fields=['created_at'], name='exp_evolution_created_at_idx'),
        ),
    ]
