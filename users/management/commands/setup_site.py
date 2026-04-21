from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Configura o Site do Django para que o Google OAuth funcione corretamente.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            default=None,
            help='Domínio do site (ex: localhost:8000 ou meuapp.run.app). '
                 'Se omitido, usa SITE_DOMAIN do settings/.env.',
        )

    def handle(self, *args, **options):
        from django.contrib.sites.models import Site

        domain = options['domain'] or getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
        name   = getattr(settings, 'SITE_NAME', 'LIDDIS')

        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': domain, 'name': name},
        )

        action = 'Criado' if created else 'Atualizado'
        self.stdout.write(self.style.SUCCESS(
            f'{action} Site #{site.id}: {site.domain} ({site.name})'
        ))
