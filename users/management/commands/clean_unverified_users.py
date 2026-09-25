"""
Management command: identifica e remove contas com e-mail não verificado.

Uso:
  # Modo auditoria (não remove nada):
  python manage.py clean_unverified_users

  # Remove contas com mais de 48 horas sem verificar (padrão):
  python manage.py clean_unverified_users --execute

  # Remove contas com mais de 24 horas:
  python manage.py clean_unverified_users --execute --hours 24

  # Exporta relatório em JSON:
  python manage.py clean_unverified_users --execute --output relatorio.json
"""
import json
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('liddis')
User = get_user_model()


class Command(BaseCommand):
    help = 'Identifica e remove contas com e-mail não verificado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Executa a remoção (sem esta flag, apenas lista)',
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=48,
            help='Remove contas não verificadas mais antigas que N horas (padrão: 48)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='',
            help='Salva relatório JSON em arquivo',
        )

    @staticmethod
    def _ids_com_dado_clinico(qs):
        """
        Ids das contas que produziram ou receberam registro clínico.

        Cobre os dois lados: quem foi paciente de uma consulta e quem a criou,
        além de sinais vitais e sessões de atendimento. Qualquer um desses
        significa uso real, e a conta não deve ser removida por rotina.
        """
        from consultations.models import Consultation, ConsultationSession, VitalSign

        ids = set(qs.values_list('pk', flat=True))
        if not ids:
            return set()

        preservar = set()
        preservar |= set(Consultation.objects.filter(patient_id__in=ids)
                         .values_list('patient_id', flat=True))
        preservar |= set(Consultation.objects.filter(created_by_id__in=ids)
                         .values_list('created_by_id', flat=True))
        preservar |= set(VitalSign.objects.filter(patient_id__in=ids)
                         .values_list('patient_id', flat=True))
        preservar |= set(ConsultationSession.objects.filter(patient_id__in=ids)
                         .values_list('patient_id', flat=True))
        preservar |= set(ConsultationSession.objects.filter(professional_id__in=ids)
                         .values_list('professional_id', flat=True))
        return preservar & ids

    def handle(self, *args, **options):
        execute    = options['execute']
        hours      = options['hours']
        output     = options['output']
        cutoff     = timezone.now() - timedelta(hours=hours)

        # Contas não verificadas: exclui superusers e ADMIN para não perder acesso
        qs = User.objects.filter(
            is_email_verified=False,
            date_joined__lt=cutoff,
            is_superuser=False,
        ).exclude(role='ADMIN').order_by('date_joined')

        # Trava de segurança: apagar um usuário leva junto, por CASCADE, suas
        # consultas, anexos e sinais vitais. Numa rotina automática isso não pode
        # depender só do e-mail não verificado — se há registro clínico, houve uso
        # real da plataforma, e a conta sai da lista independentemente do resto.
        com_dados = self._ids_com_dado_clinico(qs)
        if com_dados:
            logger.warning(
                'clean_unverified_users: %d conta(s) preservadas por terem dado clínico',
                len(com_dados),
            )
            self.stdout.write(self.style.WARNING(
                f'\n{len(com_dados)} conta(s) não verificada(s) preservada(s) '
                f'por possuírem registro clínico.'
            ))
            qs = qs.exclude(pk__in=com_dados)

        total = qs.count()

        # ── Relatório ──────────────────────────────────────────────────────────
        rows = []
        for user in qs:
            rows.append({
                'id':          str(user.pk),
                'email':       user.email,
                'username':    user.username,
                'role':        user.role,
                'date_joined': user.date_joined.isoformat(),
                'age_hours':   round((timezone.now() - user.date_joined).total_seconds() / 3600, 1),
            })

        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(f'  Auditoria de contas não verificadas — LIDDIS')
        self.stdout.write(f'  Corte: {hours}h atrás ({cutoff.strftime("%d/%m/%Y %H:%M")} BRT)')
        self.stdout.write(f'{"=" * 60}')
        self.stdout.write(f'  Total encontrado: {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('\nNenhuma conta não verificada encontrada.'))
            return

        self.stdout.write('')
        for r in rows:
            self.stdout.write(
                f'  [{r["age_hours"]:>6.1f}h]  {r["email"]:<40}  role={r["role"]}'
            )

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump({'total': total, 'cutoff_hours': hours, 'accounts': rows}, f, indent=2, ensure_ascii=False)
            self.stdout.write(f'\nRelatório salvo em: {output}')

        self.stdout.write(f'\n{"=" * 60}')

        if not execute:
            self.stdout.write(self.style.WARNING(
                f'\nMODO AUDITORIA — {total} conta(s) seriam removidas.'
                '\nExecute com --execute para remover.'
            ))
            return

        # ── Remoção ────────────────────────────────────────────────────────────
        self.stdout.write(self.style.WARNING(f'\nRemovendo {total} conta(s)...'))
        deleted_count, deleted_detail = qs.delete()
        logger.warning(
            'clean_unverified_users: %d contas removidas. Detalhe: %s',
            deleted_count, deleted_detail,
        )
        self.stdout.write(self.style.SUCCESS(
            f'{deleted_count} conta(s) removida(s) com sucesso.'
        ))
