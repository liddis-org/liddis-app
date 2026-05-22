from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0003_vitalsign_clinical_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='patientclinicalsummary',
            index=models.Index(fields=['updated_at'], name='clinical_updated_at_idx'),
        ),
        migrations.AddIndex(
            model_name='patientclinicalsummary',
            index=models.Index(fields=['smokes', 'drinks'], name='clinical_habits_idx'),
        ),
    ]
