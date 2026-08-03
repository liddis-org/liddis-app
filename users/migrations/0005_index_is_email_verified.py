from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_add_user_plan'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='customuser',
            index=models.Index(fields=['is_email_verified'], name='users_email_verified_idx'),
        ),
    ]
