"""
Rotina diária de manutenção.

Reúne o que os Termos prometem que acontece sozinho: cadastros não verificados
removidos em 48 horas e Códigos de Atendimento encerrados após o vencimento.
Enquanto ninguém executava isso, a base acumulou 361 contas automatizadas e 35
sessões vencidas em aberto — promessa publicada que não estava sendo cumprida.

É um comando só para haver um agendamento só: uma tarefa diária no Cloud
Scheduler chamando um Cloud Run Job.

Uso:
    python manage.py manutencao_diaria              # apenas relata
    python manage.py manutencao_diaria --execute    # aplica
"""
import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('liddis')


class Command(BaseCommand):
    help = 'Executa as rotinas diárias de retenção previstas nos Termos de Uso.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute', action='store_true',
            help='Aplica as alterações (sem esta flag, apenas relata).',
        )

    def handle(self, *args, **options):
        executar = options['execute']
        modo = 'EXECUÇÃO' if executar else 'AUDITORIA'

        self.stdout.write('')
        self.stdout.write('#' * 60)
        self.stdout.write(f'  LIDDIS — manutenção diária [{modo}]')
        self.stdout.write(f'  {timezone.localtime():%d/%m/%Y %H:%M}')
        self.stdout.write('#' * 60)

        rotinas = (
            ('Contas não verificadas', 'clean_unverified_users', {'hours': 48}),
            ('Sessões de atendimento', 'expirar_sessoes', {}),
        )

        falhas = []
        for rotulo, comando, extras in rotinas:
            self.stdout.write(f'\n>>> {rotulo}')
            try:
                call_command(comando, execute=executar, **extras)
            except Exception as exc:
                # Uma rotina que falha não pode impedir a outra de rodar: são
                # independentes, e o agendador chama as duas de uma vez só.
                falhas.append((rotulo, exc))
                logger.error('manutencao_diaria: %s falhou — %s', comando, exc)
                self.stdout.write(self.style.ERROR(f'  Falhou: {exc}'))

        self.stdout.write('')
        self.stdout.write('#' * 60)
        if falhas:
            self.stdout.write(self.style.ERROR(
                f'  Concluída com {len(falhas)} falha(s): '
                + ', '.join(r for r, _ in falhas)
            ))
            # Sai com erro para o agendador registrar e alertar.
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS('  Manutenção concluída sem falhas.'))
