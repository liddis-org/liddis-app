from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0006_intervention_evolution_new_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='vitalsign',
            name='other_signs',
            field=models.TextField(blank=True, verbose_name='Outros Sinais'),
        ),
        migrations.RemoveField(
            model_name='expectedevolution',
            name='prognosis',
        ),
    ]
