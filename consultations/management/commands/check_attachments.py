"""
Verifica se todo anexo registrado no banco tem o arquivo correspondente no storage.

Um registro sem arquivo é exatamente o que o usuário enxerga como "o anexo
sumiu": a galeria monta o link, mas o proxy responde 404.

Uso:
    python manage.py check_attachments
    python manage.py check_attachments --detalhado
    python manage.py check_attachments --marcar-ausentes  (grava legenda de aviso)
"""
from django.core.management.base import BaseCommand

from consultations.models import ConsultationImage


class Command(BaseCommand):
    help = 'Confere a existência física dos anexos no storage configurado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detalhado', action='store_true',
            help='Lista também os anexos íntegros, não só os ausentes.',
        )
        parser.add_argument(
            '--marcar-ausentes', action='store_true',
            help='Acrescenta aviso à legenda dos anexos cujo arquivo não existe.',
        )

    def handle(self, *args, **options):
        from django.conf import settings

        backend = settings.STORAGES['default']['BACKEND']
        bucket = getattr(settings, 'GCS_BUCKET_NAME', '') or '(filesystem local)'
        self.stdout.write(f'Storage : {backend}')
        self.stdout.write(f'Destino : {bucket}')
        self.stdout.write('')

        qs = ConsultationImage.objects.select_related('consultation').order_by('uploaded_at')
        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING('Nenhum anexo registrado no banco.'))
            return

        ausentes, erros, ok = [], [], 0

        for img in qs:
            nome = img.image.name
            if not nome:
                ausentes.append((img, 'campo de arquivo vazio'))
                continue
            try:
                if img.image.storage.exists(nome):
                    ok += 1
                    if options['detalhado']:
                        self.stdout.write(f'  ok      #{img.pk:<5} {nome}')
                else:
                    ausentes.append((img, 'arquivo não encontrado'))
            except Exception as exc:
                erros.append((img, f'{type(exc).__name__}: {exc}'))

        for img, motivo in ausentes:
            self.stdout.write(self.style.ERROR(
                f'  AUSENTE #{img.pk:<5} consulta={str(img.consultation_id)[:8]} '
                f'aba={img.tab:<12} {motivo}'
            ))
            self.stdout.write(f'          {img.image.name}')

        for img, motivo in erros:
            self.stdout.write(self.style.WARNING(
                f'  ERRO    #{img.pk:<5} {motivo}'
            ))

        self.stdout.write('')
        self.stdout.write(f'Total registrado : {total}')
        self.stdout.write(self.style.SUCCESS(f'Íntegros         : {ok}'))
        if ausentes:
            self.stdout.write(self.style.ERROR(f'Ausentes         : {len(ausentes)}'))
        if erros:
            self.stdout.write(self.style.WARNING(f'Falha ao checar  : {len(erros)}'))

        if options['marcar_ausentes'] and ausentes:
            marcados = 0
            for img, _motivo in ausentes:
                aviso = '[arquivo indisponível]'
                if aviso not in (img.caption or ''):
                    img.caption = f'{img.caption} {aviso}'.strip()[:255]
                    img.save(update_fields=['caption'])
                    marcados += 1
            self.stdout.write(self.style.WARNING(
                f'\n{marcados} legenda(s) marcada(s) com aviso de indisponibilidade.'
            ))

        if not ausentes and not erros:
            self.stdout.write(self.style.SUCCESS(
                '\nTodos os anexos do banco existem no storage.'
            ))
