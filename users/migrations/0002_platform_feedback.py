from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformFeedback',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('role_at_time', models.CharField(blank=True, max_length=20, verbose_name='Papel na época')),
                ('score_usability', models.PositiveSmallIntegerField(
                    choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
                    verbose_name='Facilidade de uso (1-5)',
                )),
                ('score_performance', models.PositiveSmallIntegerField(
                    choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
                    verbose_name='Velocidade/Desempenho (1-5)',
                )),
                ('score_care_quality', models.PositiveSmallIntegerField(
                    choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
                    verbose_name='Qualidade do atendimento (1-5)',
                )),
                ('comment', models.TextField(blank=True, verbose_name='Comentário livre')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='feedbacks',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuário',
                )),
            ],
            options={
                'verbose_name': 'Feedback da Plataforma',
                'verbose_name_plural': 'Feedbacks da Plataforma',
                'db_table': 'platform_feedbacks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='platformfeedback',
            index=models.Index(fields=['created_at'], name='feedback_created_idx'),
        ),
        migrations.AddIndex(
            model_name='platformfeedback',
            index=models.Index(fields=['role_at_time'], name='feedback_role_idx'),
        ),
    ]
