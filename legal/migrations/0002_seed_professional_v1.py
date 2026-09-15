"""
Publica a versão 1.0 dos Termos do Profissional.

O texto vive em template versionado pelo git; esta migration apenas registra a
versão como vigente, para que os aceites possam apontar para ela. Usa
get_or_create para ser idempotente entre ambientes.
"""
from datetime import date

from django.db import migrations


def publicar(apps, schema_editor):
    TermsDocument = apps.get_model('legal', 'TermsDocument')
    TermsDocument.objects.get_or_create(
        tipo='professional',
        versao='1.0',
        defaults={
            'titulo': 'Termos de Uso e Política de Privacidade do Profissional de Saúde',
            'template': 'legal/professional_v1_0.html',
            'vigente_desde': date(2026, 9, 15),
            'exige_novo_aceite': True,
            'publicado': True,
        },
    )


def despublicar(apps, schema_editor):
    TermsDocument = apps.get_model('legal', 'TermsDocument')
    # Não apaga: pode haver aceites apontando para esta versão (FK PROTECT).
    TermsDocument.objects.filter(tipo='professional', versao='1.0').update(publicado=False)


class Migration(migrations.Migration):

    dependencies = [('legal', '0001_initial')]

    operations = [migrations.RunPython(publicar, despublicar)]
