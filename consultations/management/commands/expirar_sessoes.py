"""
Encerra sessões de atendimento cujo Código já venceu.

Os Termos prometem que o Código de Atendimento vale 24 horas. A entrada já
recusa código vencido, então nenhuma dessas sessões é utilizável — mas elas
ficam marcadas como abertas no banco, o que distorce qualquer leitura de
"atendimentos em andamento" e contraria a política de retenção.

Uso:
    python manage.py expirar_sessoes                # apenas lista
    python manage.py expirar_sessoes --execute      # encerra
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from consultations.models import ConsultationSession

logger = logging.getLogger('liddis')


class Command(BaseCommand):
    help = 'Encerra sessões de atendimento com o Código de Atendimento vencido.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute', action='store_true',
            help='Aplica o encerramento (sem esta flag, apenas lista).',
        )
        parser.add_argument(
            '--carencia', type=int, default=24,
            help=(
                'Horas de tolerância após o vencimento para sessões já abertas '
                'pelo profissional (padrão: 24). Evita interromper um atendimento '
                'que ainda esteja sendo preenchido.'
            ),
        )

    def handle(self, *args, **options):
        agora = timezone.now()
        carencia = timedelta(hours=options['carencia'])

        # Nunca usada e vencida: pode encerrar de imediato, já é inutilizável.
        pendentes = ConsultationSession.objects.filter(
            status='pending', expires_at__lt=agora,
        )
        # Já aberta pelo profissional: só depois da carência, para não cortar
        # alguém que ainda esteja com o formulário na tela.
        ativas = ConsultationSession.objects.filter(
            status='active', expires_at__lt=agora - carencia,
        )

        n_pend, n_ativ = pendentes.count(), ativas.count()
        total = n_pend + n_ativ

        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write('  Sessões de atendimento vencidas — LIDDIS')
        self.stdout.write(f'  Referência: {timezone.localtime(agora):%d/%m/%Y %H:%M}')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Nunca utilizadas e vencidas : {n_pend}')
        self.stdout.write(f'  Abertas e vencidas há +{options["carencia"]}h : {n_ativ}')
        self.stdout.write(f'  Total a encerrar            : {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('\nNenhuma sessão vencida em aberto.'))
            return

        mais_antiga = min(
            [s.expires_at for s in pendentes] + [s.expires_at for s in ativas]
        )
        self.stdout.write(
            f'  Vencimento mais antigo      : {timezone.localtime(mais_antiga):%d/%m/%Y}'
        )
        self.stdout.write('=' * 60)

        if not options['execute']:
            self.stdout.write(self.style.WARNING(
                f'\nMODO AUDITORIA — {total} sessão(ões) seriam encerradas.'
                '\nExecute com --execute para aplicar.'
            ))
            return

        encerradas = 0
        for qs in (pendentes, ativas):
            encerradas += qs.update(status='expired')

        logger.warning('expirar_sessoes: %d sessão(ões) encerradas', encerradas)
        self.stdout.write(self.style.SUCCESS(
            f'\n{encerradas} sessão(ões) encerrada(s).'
        ))
