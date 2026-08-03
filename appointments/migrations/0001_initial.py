import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('consultations', '0011_remove_classification_code_add_consultation_creator'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfessionalAvailability',
            fields=[
                ('id',                   models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('weekday',              models.IntegerField(choices=[(0,'Segunda-feira'),(1,'Terça-feira'),(2,'Quarta-feira'),(3,'Quinta-feira'),(4,'Sexta-feira'),(5,'Sábado'),(6,'Domingo')], verbose_name='Dia da semana')),
                ('start_time',           models.TimeField(verbose_name='Início')),
                ('end_time',             models.TimeField(verbose_name='Fim')),
                ('slot_duration_minutes',models.PositiveIntegerField(default=30, verbose_name='Duração do slot (min)')),
                ('is_active',            models.BooleanField(default=True, verbose_name='Ativo')),
                ('professional',         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availabilities', to=settings.AUTH_USER_MODEL, verbose_name='Profissional')),
            ],
            options={
                'verbose_name':        'Disponibilidade',
                'verbose_name_plural': 'Disponibilidades',
                'db_table':            'professional_availability',
                'ordering':            ['weekday', 'start_time'],
                'unique_together':     {('professional', 'weekday', 'start_time')},
            },
        ),
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id',                   models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scheduled_date',       models.DateField(verbose_name='Data')),
                ('scheduled_time',       models.TimeField(verbose_name='Horário')),
                ('duration_minutes',     models.PositiveIntegerField(default=30, verbose_name='Duração (min)')),
                ('appointment_type',     models.CharField(choices=[('first_visit','Primeira consulta'),('follow_up','Retorno'),('procedure','Procedimento'),('exam','Exame'),('emergency','Urgência'),('other','Outro')], default='follow_up', max_length=15, verbose_name='Tipo')),
                ('specialty',            models.CharField(blank=True, choices=[('clinico_geral','Clínico Geral'),('cardiologia','Cardiologia'),('neurologia','Neurologia'),('ortopedia','Ortopedia'),('nutricao','Nutrição'),('fisioterapia','Fisioterapia'),('enfermagem','Enfermagem'),('psicologia','Psicologia'),('dermatologia','Dermatologia'),('ginecologia','Ginecologia'),('pediatria','Pediatria'),('outro','Outro')], max_length=50, verbose_name='Especialidade')),
                ('status',               models.CharField(choices=[('scheduled','Agendado'),('confirmed','Confirmado'),('cancelled','Cancelado'),('completed','Realizado'),('no_show','Não compareceu'),('rescheduled','Remarcado')], db_index=True, default='scheduled', max_length=15, verbose_name='Status')),
                ('location',             models.CharField(blank=True, max_length=200, verbose_name='Local')),
                ('notes',                models.TextField(blank=True, verbose_name='Observações')),
                ('booked_by_role',       models.CharField(choices=[('patient','Paciente'),('professional','Profissional')], max_length=15, verbose_name='Origem do agendamento')),
                ('cancelled_at',         models.DateTimeField(blank=True, null=True)),
                ('cancellation_reason',  models.TextField(blank=True, verbose_name='Motivo do cancelamento')),
                ('confirmation_sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Confirmação enviada em')),
                ('reminder_sent_at',     models.DateTimeField(blank=True, null=True, verbose_name='Lembrete enviado em')),
                ('created_at',           models.DateTimeField(auto_now_add=True)),
                ('updated_at',           models.DateTimeField(auto_now=True)),
                ('patient',              models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appointments_as_patient', to=settings.AUTH_USER_MODEL, verbose_name='Paciente')),
                ('professional',         models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments_as_professional', to=settings.AUTH_USER_MODEL, verbose_name='Profissional')),
                ('booked_by',            models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments_booked', to=settings.AUTH_USER_MODEL, verbose_name='Agendado por')),
                ('cancelled_by',         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments_cancelled', to=settings.AUTH_USER_MODEL, verbose_name='Cancelado por')),
                ('rescheduled_from',     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rescheduled_to', to='appointments.appointment', verbose_name='Remarcado de')),
                ('consultation',         models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointment', to='consultations.consultation', verbose_name='Consulta realizada')),
            ],
            options={
                'verbose_name':        'Agendamento',
                'verbose_name_plural': 'Agendamentos',
                'db_table':            'appointments',
                'ordering':            ['scheduled_date', 'scheduled_time'],
            },
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['patient', 'scheduled_date'], name='appt_patient_date_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['professional', 'scheduled_date'], name='appt_prof_date_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['status', 'scheduled_date'], name='appt_status_date_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['scheduled_date'], name='appt_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=['scheduled', 'confirmed']),
                fields=['professional', 'scheduled_date', 'scheduled_time'],
                name='unique_active_appointment_slot',
            ),
        ),
        migrations.CreateModel(
            name='AppointmentHistory',
            fields=[
                ('id',              models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action',          models.CharField(choices=[('created','Criado'),('confirmed','Confirmado'),('cancelled','Cancelado'),('rescheduled','Remarcado'),('completed','Marcado como realizado'),('no_show','Não compareceu')], max_length=15, verbose_name='Ação')),
                ('previous_date',   models.DateField(blank=True, null=True, verbose_name='Data anterior')),
                ('previous_time',   models.TimeField(blank=True, null=True, verbose_name='Horário anterior')),
                ('previous_status', models.CharField(blank=True, max_length=15, verbose_name='Status anterior')),
                ('notes',           models.TextField(blank=True, verbose_name='Observações')),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('appointment',     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='appointments.appointment', verbose_name='Agendamento')),
                ('changed_by',      models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointment_changes', to=settings.AUTH_USER_MODEL, verbose_name='Alterado por')),
            ],
            options={
                'verbose_name':        'Histórico de Agendamento',
                'verbose_name_plural': 'Histórico de Agendamentos',
                'db_table':            'appointment_history',
                'ordering':            ['-created_at'],
            },
        ),
    ]
