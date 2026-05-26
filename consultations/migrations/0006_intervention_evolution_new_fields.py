from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0005_clinical_intervention_expected_evolution'),
    ]

    operations = [
        # ── ClinicalIntervention: diagnóstico + classificação + fatores ──────────
        migrations.AddField(
            model_name='clinicalintervention',
            name='professional_diagnosis',
            field=models.TextField(blank=True, verbose_name='Diagnóstico clínico do profissional'),
        ),
        migrations.AddField(
            model_name='clinicalintervention',
            name='classification_code',
            field=models.CharField(blank=True, max_length=50, verbose_name='Código de classificação (NANDA, CID-10, DSM…)'),
        ),
        migrations.AddField(
            model_name='clinicalintervention',
            name='related_factors',
            field=models.TextField(blank=True, verbose_name='Fatores relacionados / etiologia'),
        ),
        migrations.AlterField(
            model_name='clinicalintervention',
            name='conducts',
            field=models.TextField(blank=True, verbose_name='Condutas clínicas (uma por linha)'),
        ),
        migrations.AlterField(
            model_name='clinicalintervention',
            name='clinical_actions',
            field=models.TextField(blank=True, verbose_name='Outras ações clínicas'),
        ),

        # ── ExpectedEvolution: prazo + prioridade ────────────────────────────────
        migrations.AddField(
            model_name='expectedevolution',
            name='estimated_timeframe',
            field=models.CharField(blank=True, max_length=100, verbose_name='Prazo estimado'),
        ),
        migrations.AddField(
            model_name='expectedevolution',
            name='priority',
            field=models.CharField(
                blank=True, max_length=10,
                choices=[('high', 'Alta'), ('medium', 'Média'), ('low', 'Baixa')],
                verbose_name='Prioridade',
            ),
        ),
        migrations.AlterField(
            model_name='expectedevolution',
            name='clinical_evolution',
            field=models.TextField(blank=True, verbose_name='Resultados esperados'),
        ),
    ]
